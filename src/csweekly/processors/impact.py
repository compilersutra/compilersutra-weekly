# SPDX-License-Identifier: Apache-2.0
"""Editorial priority score — not a performance or market-impact claim."""

from __future__ import annotations

from csweekly.models import ChangeGroup, SignalLevel


def score_impact(group: ChangeGroup) -> ChangeGroup:
    """0–10 weighted editorial priority for triage."""
    factors = {
        "technical_significance": 5.0,
        "architectural_impact": 5.0,
        "developer_relevance": 5.0,
        "scope_of_change": min(10.0, 3.0 + len(group.stories) * 1.5),
        "novelty": 5.0,
        "evidence_validation": 4.0,
    }
    title = (group.title or "").lower()
    paths = " ".join(
        p for s in group.stories for p in (s.paths or [])
    ).lower()
    blob = f"{title}\n{paths}\n{group.what_changed or ''}"

    if group.signal == SignalLevel.DEEP_DIVE:
        factors["technical_significance"] = 8.5
        factors["architectural_impact"] = 8.0
    elif group.signal == SignalLevel.HIGH_SIGNAL:
        factors["technical_significance"] = 7.0
        factors["developer_relevance"] = 7.0
    elif group.signal == SignalLevel.WORTH_KNOWING:
        factors["technical_significance"] = 4.5
        factors["developer_relevance"] = 5.5

    if any(k in blob for k in ("abi", "isel", "codegen", "lowering", "dialect")):
        factors["architectural_impact"] = min(10.0, factors["architectural_impact"] + 1.5)
    if any(k in blob for k in ("test", "unittest", "lit")):
        factors["evidence_validation"] = min(10.0, factors["evidence_validation"] + 2.0)
    if group.deep_dive_notes.get("validation"):
        factors["evidence_validation"] = min(10.0, factors["evidence_validation"] + 1.0)
    if "doc" in title and "abi" not in title:
        factors["novelty"] = 3.0
        factors["technical_significance"] = min(factors["technical_significance"], 4.0)

    weights = {
        "technical_significance": 0.25,
        "architectural_impact": 0.20,
        "developer_relevance": 0.20,
        "scope_of_change": 0.15,
        "novelty": 0.10,
        "evidence_validation": 0.10,
    }
    score = sum(factors[k] * weights[k] for k in weights)
    group.impact_factors = {k: round(v, 2) for k, v in factors.items()}
    group.impact_score = round(score, 2)
    if not group.editorial_level:
        if group.signal == SignalLevel.DEEP_DIVE:
            group.editorial_level = "deep_dive"
        elif group.signal == SignalLevel.HIGH_SIGNAL:
            group.editorial_level = "engineering_analysis"
        else:
            group.editorial_level = "quick_signal"
    return group
