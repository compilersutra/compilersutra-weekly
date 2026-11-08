# SPDX-License-Identifier: Apache-2.0
"""GitHub Releases collector (optional token raises rate limits)."""

from __future__ import annotations

from datetime import datetime, timezone

from csweekly.config import SourceConfig
from csweekly.http_util import get_json, github_token
from csweekly.models import CollectResult, EvidenceKind, Story, Window

UTC = timezone.utc


def collect_github_releases(source: SourceConfig, window: Window) -> CollectResult:
    if not source.github_repo:
        raise ValueError(f"{source.id}: github_repo required")
    url = f"https://api.github.com/repos/{source.github_repo}/releases"
    data = get_json(url, github=True, params={"per_page": source.max_releases})
    discovered = datetime.now(UTC)
    stories: list[Story] = []
    for rel in data:
        if rel.get("draft"):
            continue
        published = rel.get("published_at") or rel.get("created_at")
        if not published:
            continue
        when = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(UTC)
        if when < window.start or when >= window.end:
            continue
        tag = rel.get("tag_name") or "unknown"
        name = rel.get("name") or tag
        html = rel.get("html_url") or f"https://github.com/{source.github_repo}/releases/tag/{tag}"
        body = (rel.get("body") or "").strip().splitlines()
        fact = body[0][:240] if body else f"Release {tag}"
        stories.append(
            Story(
                id=f"gh-release:{source.github_repo}:{tag}",
                title=f"Release {name}",
                source_url=html,
                source_org=source.org,
                category=source.category,
                published_at=when,
                discovered_at=discovered,
                evidence_kind=EvidenceKind.GITHUB_RELEASE,
                summary=fact,
                related_ref=tag,
                raw={"tag": tag, "authenticated": bool(github_token())},
            )
        )
    return CollectResult(
        source_id=source.id,
        window=window,
        stories=stories,
        meta={"repo": source.github_repo, "authenticated": bool(github_token())},
    )
