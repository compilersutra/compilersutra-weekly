# SPDX-License-Identifier: Apache-2.0
"""Git mirror collector — primary path for LLVM / GCC monorepos.

Clones once (or uses an existing mirror), fetches, then reads commits in the
Friday→Friday window. No GitHub REST required for commit discovery.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from csweekly.collectors.filters import author_ignored, subject_ignored
from csweekly.config import SourceConfig
from csweekly.models import CollectResult, EvidenceKind, Story, Window
from csweekly.window import git_since_until

UTC = timezone.utc


def mirror_path(mirrors_root: Path, source: SourceConfig) -> Path:
    name = source.mirror_dirname or source.id
    return mirrors_root / name


def ensure_mirror(
    source: SourceConfig,
    mirrors_root: Path,
    *,
    fetch: bool = True,
) -> Path:
    """Clone ``--mirror`` if missing; optionally ``git fetch --prune``."""
    if not source.url:
        raise ValueError(f"source {source.id}: git url required")
    path = mirror_path(mirrors_root, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not (path / "HEAD").exists() and not (path / ".git").exists():
        path.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--mirror", source.url, str(path)])
    elif fetch:
        _run(["git", "fetch", "--prune"], cwd=path)
    return path


def collect_git(
    source: SourceConfig,
    window: Window,
    mirrors_root: Path,
    *,
    fetch: bool = True,
    repo_path: Path | None = None,
) -> CollectResult:
    """Collect commits for ``source`` inside ``window``."""
    repo = repo_path or ensure_mirror(source, mirrors_root, fetch=fetch)
    since, until = git_since_until(window)
    fmt = "%H%x09%cI%x09%an%x09%s"
    ref = source.default_branch
    if (repo / "HEAD").exists() and not (repo / ".git").exists():
        ref = f"refs/heads/{source.default_branch}"

    cmd = [
        "git",
        "log",
        f"--since={since}",
        f"--until={until}",
        f"--pretty=format:{fmt}",
        "--no-merges",
        f"-n{source.max_commits}",
        ref,
    ]
    try:
        out = _run(cmd, cwd=repo)
    except subprocess.CalledProcessError:
        cmd[-1] = "HEAD"
        out = _run(cmd, cwd=repo)

    stories: list[Story] = []
    discovered = datetime.now(UTC)

    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 3)
        if len(parts) < 4:
            continue
        sha, when, author, subject = parts
        subject = subject.strip()
        if author_ignored(author, source) or subject_ignored(subject, source):
            continue
        paths = _paths_for_commit(repo, sha)
        if source.path_prefixes and not _matches_prefixes(paths, source.path_prefixes):
            continue
        label = _path_label(paths, source.path_labels)
        title = f"[{label}] {subject}" if label else subject
        stories.append(
            Story(
                id=f"git:{source.id}:{sha}",
                title=title,
                source_url=_commit_url(source, sha),
                source_org=source.org,
                category=source.category,
                published_at=_parse_dt(when),
                discovered_at=discovered,
                evidence_kind=EvidenceKind.GIT_COMMIT,
                summary=f"{author}: {subject}",
                related_ref=sha,
                paths=paths[:40],
                raw={"author": author, "sha": sha},
            )
        )

    return CollectResult(
        source_id=source.id,
        window=window,
        stories=stories,
        meta={"repo": str(repo), "commit_count": len(stories)},
    )


def _paths_for_commit(repo: Path, sha: str) -> list[str]:
    out = _run(["git", "show", "--name-only", "--pretty=format:", sha], cwd=repo)
    return [p for p in out.splitlines() if p.strip()]


def _matches_prefixes(paths: list[str], prefixes: list[str]) -> bool:
    if not prefixes:
        return True
    if not paths:
        return True
    return any(any(p.startswith(pref) for pref in prefixes) for p in paths)


def _path_label(paths: list[str], labels: dict[str, str]) -> str | None:
    for pref, label in labels.items():
        if any(p.startswith(pref) for p in paths):
            return label
    return None


def _commit_url(source: SourceConfig, sha: str) -> str:
    if source.github_repo:
        return f"https://github.com/{source.github_repo}/commit/{sha}"
    if source.url and source.url.endswith(".git"):
        base = source.url[:-4]
        if "github.com" in base:
            return f"{base}/commit/{sha}"
    return f"{source.url}@{sha}"


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout
