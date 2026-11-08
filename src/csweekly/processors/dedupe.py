# SPDX-License-Identifier: Apache-2.0
"""Deduplicate stories by stable id / URL."""

from __future__ import annotations

from csweekly.models import Story


def dedupe_stories(stories: list[Story]) -> list[Story]:
    seen: set[str] = set()
    out: list[Story] = []
    for story in stories:
        keys = {story.id, story.source_url}
        if story.related_ref:
            keys.add(f"ref:{story.related_ref}")
        if keys & seen:
            continue
        seen |= keys
        out.append(story)
    return out
