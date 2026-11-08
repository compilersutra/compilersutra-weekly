# SPDX-License-Identifier: Apache-2.0
"""Git mirror collector — primary source of weekly truth.

Clones/fetches mirrors and extracts commits by **committer timestamp**
inside the Friday→Friday UTC window (end exclusive).
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from csweekly.analyzers.areas import classify_areas
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
) -> tuple[Path, list[str]]:
    """Clone ``--mirror`` if missing; optionally ``git fetch --prune``.

    Returns (path, errors).
    """
    errors: list[str] = []
    if not source.url:
        return mirrors_root / (source.mirror_dirname or source.id), [
            f"{source.id}: git url required"
        ]
    path = mirror_path(mirrors_root, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not (path / "HEAD").exists() and not (path / ".git").exists():
            path.mkdir(parents=True, exist_ok=True)
            _run(["git", "clone", "--mirror", source.url, str(path)])
        elif fetch:
            _run(["git", "fetch", "--prune"], cwd=path)
    except subprocess.CalledProcessError as exc:
        err = exc.stderr[-400:] if exc.stderr else str(exc)
        errors.append(f"{source.id}: git clone/fetch failed: {err}")
    return path, errors


def collect_git(
    source: SourceConfig,
    window: Window,
    mirrors_root: Path,
    *,
    fetch: bool = True,
    repo_path: Path | None = None,
) -> CollectResult:
    errors: list[str] = []
    if repo_path is not None:
        repo = repo_path
    else:
        repo, errors = ensure_mirror(source, mirrors_root, fetch=fetch)
        if errors and not (repo / "HEAD").exists() and not (repo / ".git").exists():
            return CollectResult(
                source_id=source.id, window=window, stories=[], meta={}, errors=errors
            )

    since, until = git_since_until(window)
    fmt = "%H%x09%cI%x09%aI%x09%an%x09%cn%x09%s"
    refs = _candidate_refs(repo, source.default_branch)
    out = ""
    used_ref = refs[0]
    last_err = ""
    for ref in refs:
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
            used_ref = ref
            break
        except subprocess.CalledProcessError as exc:
            last_err = exc.stderr[-200:] if exc.stderr else str(exc)
            continue
    else:
        errors.append(f"{source.id}: git log failed on refs {refs}: {last_err}")
        return CollectResult(
            source_id=source.id,
            window=window,
            stories=[],
            meta={"repo": str(repo)},
            errors=errors,
        )

    stories: list[Story] = []
    discovered = datetime.now(UTC)
    project = source.project or source.id

    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 5)
        if len(parts) < 6:
            continue
        sha, cwhen, awhen, author, committer, subject = parts
        subject = subject.strip()
        if author_ignored(author, source) or subject_ignored(subject, source):
            continue
        try:
            paths = _paths_for_commit(repo, sha)
        except subprocess.CalledProcessError:
            paths = []
            errors.append(f"{source.id}: failed to list paths for {sha[:12]}")
        if source.path_prefixes and not _matches_prefixes(paths, source.path_prefixes):
            continue
        if source.path_excludes and _matches_prefixes(paths, source.path_excludes):
            continue
        label = _path_label(paths, source.path_labels)
        title = f"[{label}] {subject}" if label else subject
        areas = classify_areas(paths, subject)
        commit_dt = _parse_dt(cwhen)
        stories.append(
            Story(
                id=f"git:{source.id}:{sha}",
                title=title,
                source_url=_commit_url(source, sha),
                source_org=source.org,
                category=source.category,
                project=project,
                published_at=commit_dt,
                discovered_at=discovered,
                evidence_kind=EvidenceKind.GIT_COMMIT,
                summary=subject,
                related_ref=sha,
                paths=paths[:80],
                areas=areas,
                author=author,
                committer=committer,
                raw={
                    "sha": sha,
                    "author": author,
                    "committer": committer,
                    "author_date": awhen,
                    "committer_date": cwhen,
                    "ref": used_ref,
                },
            )
        )

    return CollectResult(
        source_id=source.id,
        window=window,
        stories=stories,
        meta={
            "repo": str(repo),
            "commit_count": len(stories),
            "ref": used_ref,
            "since": since,
            "until": until,
            "date_field": "committer",
        },
        errors=errors,
    )


def _candidate_refs(repo: Path, default_branch: str) -> list[str]:
    bare = (repo / "HEAD").exists() and not (repo / ".git").exists()
    refs: list[str] = []
    if bare:
        refs.append(f"refs/heads/{default_branch}")
        for alt in ("main", "master", "trunk", "amd-staging"):
            r = f"refs/heads/{alt}"
            if r not in refs:
                refs.append(r)
    else:
        refs.append(default_branch)
        for alt in ("main", "master"):
            if alt not in refs:
                refs.append(alt)
    refs.append("HEAD")
    return refs


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
