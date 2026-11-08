# SPDX-License-Identifier: Apache-2.0
"""Dispatch collectors by source kind. Git remains primary."""

from __future__ import annotations

from pathlib import Path

from csweekly.analyzers.areas import classify_areas
from csweekly.analyzers.importance import assign_importance
from csweekly.analyzers.taxonomy import classify_dimensions
from csweekly.collectors.arxiv_api import collect_arxiv
from csweekly.collectors.git_mirror import collect_git
from csweekly.collectors.github_releases import collect_github_releases
from csweekly.collectors.rss_feed import collect_rss
from csweekly.collectors.web_discovery import collect_web_discovery
from csweekly.config import SourceConfig, load_sources
from csweekly.models import CollectResult, Story, Window
from csweekly.processors.explain import explain_story, make_story_id


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
    if kind == "web_discovery":
        return collect_web_discovery(source, window)
    raise ValueError(f"{source.id}: unknown kind {kind!r}")


def enrich_story(story: Story) -> Story:
    # Monorepo: MLIR paths belong in the MLIR section even if collected via llvm.
    if story.category == "llvm" and story.paths and any(
        p.startswith("mlir/") for p in story.paths
    ):
        story.category = "mlir"
        story.project = "mlir"
    if not story.areas:
        story.areas = classify_areas(story.paths, story.title)
    if not story.project:
        story.project = story.category
    story.importance = assign_importance(story)
    stages, domains, tech, hardware = classify_dimensions(story)
    story.stages = stages
    story.domains = domains
    story.technical_areas = tech
    story.hardware_targets = hardware
    if not story.story_id:
        story.story_id = make_story_id(story)
    explain_story(story)
    return story


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
        for s in result.stories:
            enrich_story(s)
        results.append(result)
        stories.extend(result.stories)
    return results, stories
