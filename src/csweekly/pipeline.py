# SPDX-License-Identifier: Apache-2.0
"""Dispatch collectors by source kind."""

from __future__ import annotations

from pathlib import Path

from csweekly.collectors.arxiv_api import collect_arxiv
from csweekly.collectors.git_mirror import collect_git
from csweekly.collectors.github_releases import collect_github_releases
from csweekly.collectors.rss_feed import collect_rss
from csweekly.config import SourceConfig, load_sources
from csweekly.models import CollectResult, Story, Window


def collect_source(
    source: SourceConfig,
    window: Window,
    *,
    mirrors_dir: Path,
    fetch: bool = True,
    repo_path: Path | None = None,
) -> CollectResult:
    kind = source.kind
    if kind == "git":
        return collect_git(
            source, window, mirrors_dir, fetch=fetch, repo_path=repo_path
        )
    if kind == "github_releases":
        return collect_github_releases(source, window)
    if kind == "rss":
        return collect_rss(source, window)
    if kind == "arxiv":
        return collect_arxiv(source, window)
    raise ValueError(f"{source.id}: unknown kind {kind!r}")


def collect_all(
    window: Window,
    *,
    sources_dir: Path | None = None,
    mirrors_dir: Path = Path("data/mirrors"),
    only: set[str] | None = None,
    fetch: bool = True,
    repo_path: Path | None = None,
    kinds: set[str] | None = None,
) -> tuple[list[CollectResult], list[Story]]:
    sources = load_sources(sources_dir)
    sources = [s for s in sources if s.enabled]
    if only:
        sources = [s for s in sources if s.id in only]
    if kinds:
        sources = [s for s in sources if s.kind in kinds]
    results: list[CollectResult] = []
    stories: list[Story] = []
    for source in sources:
        result = collect_source(
            source,
            window,
            mirrors_dir=mirrors_dir,
            fetch=fetch,
            repo_path=repo_path if source.kind == "git" else None,
        )
        results.append(result)
        stories.extend(result.stories)
    return results, stories
