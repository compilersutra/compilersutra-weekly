# SPDX-License-Identifier: Apache-2.0
"""Enrich stories from local git mirrors — commit body + changed paths only."""

from __future__ import annotations

import subprocess
from pathlib import Path

from csweekly.models import ChangeGroup, SignalLevel


def _git_show(repo: Path, sha: str) -> tuple[str, str, list[str]]:
    """Return (subject, body, files). Empty on failure."""
    if not sha or not repo.exists():
        return "", "", []
    try:
        subject = subprocess.check_output(
            ["git", "-C", str(repo), "log", "-1", "--format=%s", sha],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        body = subprocess.check_output(
            ["git", "-C", str(repo), "log", "-1", "--format=%b", sha],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        files = subprocess.check_output(
            ["git", "-C", str(repo), "show", "--name-only", "--format=", sha],
            text=True,
            stderr=subprocess.DEVNULL,
        ).splitlines()
        files = [f.strip() for f in files if f.strip()]
        return subject, body, files
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "", "", []


def resolve_mirror(story_paths: list[str], mirrors_dir: Path) -> Path | None:
    joined = "\n".join(story_paths)
    if joined.startswith("gcc/") or "/gcc/" in joined or "gcc/config" in joined:
        path = mirrors_dir / "gcc"
        return path if path.exists() else None
    for name in ("llvm-project", "llvm"):
        path = mirrors_dir / name
        if path.exists():
            return path
    return None


def enrich_group_from_mirrors(group: ChangeGroup, mirrors_dir: Path) -> ChangeGroup:
    """Fill deep_dive_notes / context from real commit messages when mirrors exist."""
    primary = group.stories[0] if group.stories else None
    if not primary or not primary.related_ref:
        return group

    paths = list(primary.paths)
    for s in group.stories[:5]:
        paths.extend(s.paths)
    repo = resolve_mirror(paths, mirrors_dir)
    if repo is None:
        return group

    subject, body, files = _git_show(repo, primary.related_ref)
    if not subject and not body:
        return group

    # Prefer mirror paths when story paths are thin.
    if files and len(primary.paths) < 2:
        primary.paths = files[:20]

    # Project correction from paths
    blob = "\n".join(paths + files)
    if "gcc/config" in blob or blob.startswith("gcc/"):
        group.project = "GCC"
        group.category = "gcc"
    elif "mlir/" in blob:
        group.project = "MLIR"
        group.category = "mlir"
    elif "lldb/" in blob:
        group.project = "LLDB"
    elif "clang/" in blob:
        group.project = "Clang"
        if group.category == "llvm":
            pass

    notes = dict(group.deep_dive_notes or {})
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    # Drop changelog-style trailing blocks for the prose sections.
    prose = []
    for p in paragraphs:
        if p.lower().startswith("gcc/changelog") or p.lower().startswith("differential"):
            break
        if p.startswith("* ") and "ChangeLog" in body:
            break
        prose.append(p)
    body_prose = "\n\n".join(prose[:3]).strip()

    if body_prose:
        notes["problem"] = (
            f"Upstream states: {subject}. "
            f"{prose[0][:500] if prose else ''}"
        ).strip()
        notes["implementation"] = (
            f"Primary commit `{primary.related_ref[:12]}` changes: "
            + ", ".join(files[:8] if files else primary.paths[:8])
            + "."
        )
        if len(prose) > 1:
            notes["previous_behavior"] = (
                "Inferred from the commit message (verify in the diff): "
                + prose[1][:420]
            )
        notes["example"] = (
            "See linked tests in the commit for concrete coverage. "
            "No IR/assembly is invented here."
        )
        notes["limits"] = (
            group.uncertainty_note
            or "Commit message describes intent; performance claims require "
            "benchmarks that are not assumed from this text."
        )
        notes["background"] = (
            f"{len(group.stories)} related commit(s) clustered. "
            f"Primary subject: {subject}."
        )
        test_files = [f for f in files if "test" in f.lower()]
        notes["validation"] = (
            "Tests touched: " + ", ".join(test_files[:6])
            if test_files
            else "No obvious test paths in the primary commit file list."
        )
        group.deep_dive_notes = notes
        if body_prose and (not group.why_it_matters or "Related commits" in (group.why_it_matters or "")):
            group.why_it_matters = prose[0][:280]
        if subject and group.title and len(group.title) < 20:
            group.title = subject

    # Editorial level defaults
    if group.signal == SignalLevel.DEEP_DIVE:
        group.editorial_level = "deep_dive"
    elif group.signal == SignalLevel.HIGH_SIGNAL:
        group.editorial_level = group.editorial_level or "engineering_analysis"
    elif group.signal == SignalLevel.WORTH_KNOWING:
        group.editorial_level = group.editorial_level or "quick_signal"

    return group


def enrich_issue_groups(groups: list[ChangeGroup], mirrors_dir: Path) -> None:
    for g in groups:
        enrich_group_from_mirrors(g, mirrors_dir)
