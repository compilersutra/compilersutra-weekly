# SPDX-License-Identifier: Apache-2.0
"""Evidence → write → fact-check → apply to ChangeGroup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from csweekly.ai.evidence import EvidencePack, build_evidence_pack
from csweekly.ai.factcheck import FactCheckResult, factcheck
from csweekly.ai.writer import EditorialDraft, write_development
from csweekly.models import ChangeGroup, SignalLevel


def _level_for(group: ChangeGroup) -> str:
    if group.editorial_level:
        return group.editorial_level
    if group.signal == SignalLevel.DEEP_DIVE:
        return "deep_dive"
    if group.signal == SignalLevel.HIGH_SIGNAL:
        return "engineering_analysis"
    return "quick_signal"


def apply_draft(
    group: ChangeGroup,
    draft: EditorialDraft,
    check: FactCheckResult,
    pack: EvidencePack,
) -> ChangeGroup:
    """Mutate group with verified draft fields. Source remains authority."""
    group.title = draft.title or group.title
    group.what_changed = draft.what_changed
    group.why_it_matters = draft.why_it_matters
    group.technical_context = draft.technical_implementation
    if draft.who_should_care:
        group.who_should_care = draft.who_should_care
    if draft.stages:
        group.stages = draft.stages
    if draft.domains:
        group.domains = draft.domains
    if draft.hardware_targets:
        group.hardware_targets = draft.hardware_targets
    if draft.change_type:
        group.change_type = draft.change_type
    group.editorial_level = _level_for(group)

    notes = dict(group.deep_dive_notes or {})
    notes.update(
        {
            "problem": draft.what_changed,
            "previous_behavior": draft.previous_behavior
            or "Not established from available evidence.",
            "implementation": draft.technical_implementation,
            "implications": draft.why_it_matters,
            "validation": draft.validation,
            "limits": draft.limitations
            or "Not established from available evidence.",
            "performance": draft.performance_impact,
            "confidence": draft.confidence,
            "writer": draft.writer,
            "factcheck": "pass" if check.ok else "fail",
        }
    )
    if pack.primary:
        notes["background"] = (
            f"Evidence from {pack.primary.sha[:12]} "
            f"(+{pack.primary.additions}/−{pack.primary.deletions}); "
            f"cluster size {len(pack.related_shas)}."
        )
        if pack.primary.files and group.stories:
            group.stories[0].paths = pack.primary.files[:20]
    group.deep_dive_notes = notes

    if not check.ok:
        group.impact_uncertain = True
        group.uncertainty_note = (
            "Fact-check flagged issues: "
            + "; ".join(check.unsupported_claims + check.missing_evidence)[:400]
        )
        # Strip unsafe performance wording from why_it_matters
        if not check.performance_claims_ok:
            group.why_it_matters = (
                (group.why_it_matters or "")
                + " Performance impact not established from available evidence."
            )
            notes["performance"] = "Not established from available evidence."
            group.deep_dive_notes = notes

    # Store audit trail on first story raw
    if group.stories:
        trail = {
            "ai_writer": draft.writer,
            "ai_confidence": draft.confidence,
            "factcheck": check.to_dict(),
            "evidence_notes": draft.evidence_notes,
        }
        group.stories[0].raw = {**(group.stories[0].raw or {}), **trail}
        group.stories[0].analysis_generated = True

    return group


def analyze_group(
    group: ChangeGroup,
    mirrors_dir: Path,
    *,
    use_llm: bool = True,
    factcheck_llm: bool = False,
) -> tuple[ChangeGroup, EvidencePack, EditorialDraft, FactCheckResult]:
    pack = build_evidence_pack(group, mirrors_dir)
    level = _level_for(group)
    draft = write_development(pack, level=level, use_llm=use_llm)
    check = factcheck(draft, pack, use_llm=factcheck_llm)
    # If LLM draft fails factcheck on perf, rewrite deterministically once
    if not check.ok and draft.writer == "llm":
        draft = write_development(pack, level=level, use_llm=False)
        check = factcheck(draft, pack, use_llm=False)
    apply_draft(group, draft, check, pack)
    return group, pack, draft, check


def analyze_issue_groups(
    groups: list[ChangeGroup],
    mirrors_dir: Path,
    *,
    use_llm: bool = True,
    factcheck_llm: bool = False,
    only_levels: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Analyze groups; returns audit rows for QA reports."""
    rows: list[dict[str, Any]] = []
    for g in groups:
        level = _level_for(g)
        if only_levels and level not in only_levels:
            continue
        g2, pack, draft, check = analyze_group(
            g,
            mirrors_dir,
            use_llm=use_llm,
            factcheck_llm=factcheck_llm,
        )
        rows.append(
            {
                "id": g2.story_id or g2.id,
                "title": g2.title,
                "level": level,
                "writer": draft.writer,
                "confidence": draft.confidence,
                "factcheck_ok": check.ok,
                "unsupported": check.unsupported_claims,
                "errors": pack.errors,
            }
        )
    return rows


def write_analysis_report(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in rows if r.get("factcheck_ok"))
    lines = [
        "# AI editorial analysis report",
        "",
        f"Stories analyzed: {len(rows)}",
        f"Fact-check passed: {passed}/{len(rows)}",
        "",
    ]
    for r in rows:
        mark = "✓" if r.get("factcheck_ok") else "✗"
        lines.append(
            f"- {mark} [{r.get('level')}] {r.get('title')} "
            f"(writer={r.get('writer')}, confidence={r.get('confidence')})"
        )
        if r.get("unsupported"):
            lines.append(f"  unsupported: {', '.join(r['unsupported'])}")
        if r.get("errors"):
            lines.append(f"  evidence errors: {', '.join(r['errors'])}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    sidecar = path.with_suffix(".json")
    sidecar.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return path
