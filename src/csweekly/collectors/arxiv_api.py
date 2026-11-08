# SPDX-License-Identifier: Apache-2.0
"""arXiv API collector (Atom)."""

from __future__ import annotations

from datetime import datetime, timezone
from time import mktime
from urllib.parse import urlencode

import feedparser

from csweekly.config import SourceConfig
from csweekly.models import CollectResult, EvidenceKind, Story, Window

UTC = timezone.utc
API = "https://export.arxiv.org/api/query"


def collect_arxiv(source: SourceConfig, window: Window) -> CollectResult:
    if not source.arxiv_query:
        raise ValueError(f"{source.id}: arxiv_query required")
    params = {
        "search_query": source.arxiv_query,
        "start": 0,
        "max_results": source.arxiv_max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{API}?{urlencode(params)}"
    parsed = feedparser.parse(url)
    discovered = datetime.now(UTC)
    stories: list[Story] = []
    for entry in parsed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if not published:
            continue
        when = datetime.fromtimestamp(mktime(published), tz=UTC)
        if when < window.start or when >= window.end:
            continue
        title = " ".join((entry.get("title") or "").split())
        link = entry.get("link") or url
        summary = " ".join((entry.get("summary") or title).split())[:400]
        arxiv_id = (entry.get("id") or link).rstrip("/").split("/")[-1]
        stories.append(
            Story(
                id=f"arxiv:{arxiv_id}",
                title=title,
                source_url=link,
                source_org=source.org,
                category=source.category,
                published_at=when,
                discovered_at=discovered,
                evidence_kind=EvidenceKind.ARXIV,
                summary=summary,
                related_ref=arxiv_id,
            )
        )
    return CollectResult(
        source_id=source.id,
        window=window,
        stories=stories,
        meta={"query": source.arxiv_query, "url": url},
    )
