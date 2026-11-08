# SPDX-License-Identifier: Apache-2.0
"""Path hotspot counts — factual aggregation only."""

from __future__ import annotations

from collections import Counter

from csweekly.models import Story


def path_hotspots(stories: list[Story], *, top_n: int = 15) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for story in stories:
        # prefer top-level / second-level dirs for readability
        for path in story.paths:
            parts = path.split("/")
            key = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
            if key:
                counter[key] += 1
    return counter.most_common(top_n)


def score_by_hotspot(stories: list[Story], hotspots: list[tuple[str, int]]) -> None:
    """Mutate relevance_score lightly from path popularity (0–1)."""
    if not hotspots:
        return
    weight = {p: n for p, n in hotspots}
    peak = max(weight.values()) or 1
    for story in stories:
        best = 0.0
        for path in story.paths:
            parts = path.split("/")
            key = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
            if key in weight:
                best = max(best, weight[key] / peak)
        story.relevance_score = round(min(1.0, 0.35 + 0.65 * best), 3)
