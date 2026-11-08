# SPDX-License-Identifier: Apache-2.0
"""RSS/Atom feed collector."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import mktime

import feedparser

from csweekly.config import SourceConfig
from csweekly.models import CollectResult, EvidenceKind, Story, Window

UTC = timezone.utc


def collect_rss(source: SourceConfig, window: Window) -> CollectResult:
    if not source.feed_url:
        raise ValueError(f"{source.id}: feed_url required")
    parsed = feedparser.parse(source.feed_url)
    discovered = datetime.now(UTC)
    stories: list[Story] = []
    for entry in parsed.entries:
        when = _entry_dt(entry)
        if when is None or when < window.start or when >= window.end:
            continue
        title = (entry.get("title") or "Untitled").strip()
        link = entry.get("link") or source.feed_url
        summary = (entry.get("summary") or entry.get("description") or title).strip()
        if "<" in summary:
            summary = _strip_tags(summary)
        summary = summary[:400]
        stories.append(
            Story(
                id=f"rss:{source.id}:{entry.get('id') or link}",
                title=title,
                source_url=link,
                source_org=source.org,
                category=source.category,
                published_at=when,
                discovered_at=discovered,
                evidence_kind=EvidenceKind.RSS,
                summary=summary[:400],
                related_ref=entry.get("id"),
            )
        )
    return CollectResult(
        source_id=source.id,
        window=window,
        stories=stories,
        meta={"feed": source.feed_url, "entries_seen": len(parsed.entries)},
    )


def _strip_tags(text: str) -> str:
    out = []
    skip = False
    for ch in text:
        if ch == "<":
            skip = True
            continue
        if ch == ">":
            skip = False
            continue
        if not skip:
            out.append(ch)
    return "".join(out)


def _entry_dt(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            return datetime.fromtimestamp(mktime(val), tz=UTC)
    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            return parsedate_to_datetime(raw).astimezone(UTC)
        except (TypeError, ValueError, IndexError):
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)
            except ValueError:
                continue
    return None
