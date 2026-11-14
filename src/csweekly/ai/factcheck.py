# SPDX-License-Identifier: Apache-2.0
"""Verify editorial drafts against evidence packs."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from csweekly.ai.client import chat_json
from csweekly.ai.evidence import EvidencePack
from csweekly.ai.prompts import SYSTEM_FACTCHECK
from csweekly.ai.writer import EditorialDraft

_PERF_PAT = re.compile(
    r"\b(faster|speedup|speed-up|\d+\s*%|x\s+faster|improves performance|"
    r"performance improvement|regression of)\b",
    re.I,
)


class FactCheckResult(BaseModel):
    ok: bool = True
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    performance_claims_ok: bool = True
    notes: list[str] = Field(default_factory=list)
    checker: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _evidence_blob(pack: EvidencePack) -> str:
    parts: list[str] = []
    if pack.primary:
        p = pack.primary
        parts.append(p.subject)
        parts.append(p.body)
        parts.extend(p.files)
        parts.extend(p.tests)
        parts.extend(p.functions)
        parts.append(p.diff_excerpt[:8000])
    for r in pack.related:
        parts.append(r.subject)
        parts.append(r.body)
    return "\n".join(parts).lower()


def factcheck_deterministic(draft: EditorialDraft, pack: EvidencePack) -> FactCheckResult:
    result = FactCheckResult()
    if pack.errors or pack.primary is None:
        result.ok = False
        result.missing_evidence.append("primary commit evidence missing")
        return result

    blob = _evidence_blob(pack)
    text = " ".join(
        [
            draft.what_changed,
            draft.previous_behavior,
            draft.technical_implementation,
            draft.why_it_matters,
            draft.validation,
            draft.performance_impact,
        ]
    )

    # Performance gate
    if _PERF_PAT.search(draft.performance_impact or "") or _PERF_PAT.search(draft.why_it_matters or ""):
        if "benchmark" not in blob and "perf" not in blob and not re.search(r"\d+\s*%", blob):
            result.performance_claims_ok = False
            result.unsupported_claims.append(
                "performance language without benchmark evidence in pack"
            )
            result.ok = False

    # File mentions should exist in evidence when they look like paths
    for m in re.findall(r"[A-Za-z0-9_./+-]+\.(?:cpp|cc|h|hpp|td|md|c|ll|mir|mlir|rs)", text):
        if m.lower() not in blob and m not in (pack.primary.files if pack.primary else []):
            # soft warning — path may be truncated
            result.notes.append(f"path mention not in primary file list: {m}")

    if not draft.what_changed.strip():
        result.ok = False
        result.missing_evidence.append("empty what_changed")

    what_n = " ".join((draft.what_changed or "").lower().split())
    why_n = " ".join((draft.why_it_matters or "").lower().split())
    if what_n and why_n and what_n == why_n:
        result.ok = False
        result.unsupported_claims.append(
            "why_it_matters identical to what_changed — not an editorial explanation"
        )

    if not (draft.why_it_matters or "").strip():
        result.ok = False
        result.missing_evidence.append("empty why_it_matters")

    if draft.confidence not in {"high", "medium", "low"}:
        result.ok = False
        result.missing_evidence.append("confidence must be high|medium|low")

    if draft.confidence == "low" and draft.writer == "deterministic":
        result.notes.append("low confidence deterministic draft")

    if pack.primary and not pack.primary.files:
        result.missing_evidence.append("no changed files from git show")
        result.ok = False

    return result


def factcheck_with_llm(draft: EditorialDraft, pack: EvidencePack) -> FactCheckResult | None:
    user = json.dumps(
        {"draft": draft.model_dump(mode="json"), "evidence": pack.to_prompt_dict()},
        ensure_ascii=False,
    )
    data = chat_json(SYSTEM_FACTCHECK, user, temperature=0.0)
    if not data:
        return None
    try:
        result = FactCheckResult.model_validate(data)
    except Exception:
        return None
    result.checker = "llm"
    return result


def factcheck(
    draft: EditorialDraft, pack: EvidencePack, *, use_llm: bool = False
) -> FactCheckResult:
    base = factcheck_deterministic(draft, pack)
    if use_llm:
        llm = factcheck_with_llm(draft, pack)
        if llm is not None:
            # Merge: any hard fail from either side fails
            base.unsupported_claims = list(
                dict.fromkeys(base.unsupported_claims + llm.unsupported_claims)
            )
            base.missing_evidence = list(
                dict.fromkeys(base.missing_evidence + llm.missing_evidence)
            )
            base.notes.extend(llm.notes)
            base.performance_claims_ok = (
                base.performance_claims_ok and llm.performance_claims_ok
            )
            base.ok = base.ok and llm.ok and base.performance_claims_ok
            base.checker = "deterministic+llm"
    return base
