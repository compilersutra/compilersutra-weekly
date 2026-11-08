# SPDX-License-Identifier: Apache-2.0
"""Optional web discovery for announcements outside Git.

Disabled by default. Never breaks the primary Git collector.
TinyFish / browser automation is NOT a required dependency.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from csweekly.config import SourceConfig
from csweekly.models import CollectResult, EvidenceKind, Story, Window

UTC = timezone.utc


def web_discovery_enabled() -> bool:
    return os.environ.get("CSWEEKLY_WEB_DISCOVERY", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def collect_web_discovery(source: SourceConfig, window: Window) -> CollectResult:
    """Placeholder adapter — structured APIs preferred when enabled.

    Returns empty stories unless CSWEEKLY_WEB_DISCOVERY=1. Failures are recorded
    in ``errors`` and never raised to the weekly Git pipeline.
    """
    if not web_discovery_enabled():
        return CollectResult(
            source_id=source.id,
            window=window,
            stories=[],
            meta={"skipped": True, "reason": "CSWEEKLY_WEB_DISCOVERY not enabled"},
            errors=[],
        )
    # No TinyFish hard dependency. Hook structured sources here later.
    return CollectResult(
        source_id=source.id,
        window=window,
        stories=[],
        meta={"enabled": True, "adapter": "stub"},
        errors=[
            f"{source.id}: web discovery enabled but no adapter configured "
            "(use structured APIs; TinyFish is optional)"
        ],
    )


def story_from_announcement(
    *,
    source_id: str,
    title: str,
    url: str,
    org: str,
    category: str,
    published_at: datetime | None,
    summary: str,
) -> Story:
    return Story(
        id=f"web:{source_id}:{url}",
        title=title,
        source_url=url,
        source_org=org,
        category=category,
        project=source_id,
        published_at=published_at,
        discovered_at=datetime.now(UTC),
        evidence_kind=EvidenceKind.WEB_ANNOUNCEMENT,
        summary=summary,
    )
