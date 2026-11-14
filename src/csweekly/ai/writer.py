# SPDX-License-Identifier: Apache-2.0
"""Technical editorial drafts from evidence (+ optional LLM)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from csweekly.ai.client import chat_json
from csweekly.ai.evidence import EvidencePack, prose_from_body
from csweekly.ai.prompts import SYSTEM_EDITOR


class EditorialDraft(BaseModel):
    title: str
    what_changed: str
    previous_behavior: str = ""
    technical_implementation: str = ""
    why_it_matters: str = ""
    who_should_care: list[str] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    hardware_targets: list[str] = Field(default_factory=list)
    change_type: str = "Other"
    validation: str = ""
    performance_impact: str = "Not established from available evidence."
    limitations: str = ""
    confidence: str = "medium"
    evidence_notes: list[str] = Field(default_factory=list)
    writer: str = "deterministic"  # deterministic | llm
    raw: dict[str, Any] = Field(default_factory=dict)


def _infer_change_type(subject: str, body: str) -> str:
    blob = f"{subject}\n{body}".lower()
    if any(k in blob for k in ("fix", "bug", "crash", "assert", "miscompile")):
        return "Bug fix"
    if any(k in blob for k in ("add ", "implement", "support for", "introduce")):
        return "New capability"
    if any(k in blob for k in ("optimize", "speed", "perf", "faster")):
        return "Optimization"
    if any(k in blob for k in ("refactor", "cleanup", "nfc", "simplify")):
        return "Refactoring"
    if any(k in blob for k in ("abi", "docs", "documentation", "test", "nfc")):
        return "Infrastructure"
    return "Code generation" if "codegen" in blob or "isel" in blob else "Other"


def write_deterministic(pack: EvidencePack, *, level: str = "engineering_analysis") -> EditorialDraft:
    """Evidence-grounded draft without an LLM — still not a title summarizer."""
    primary = pack.primary
    if primary is None:
        return EditorialDraft(
            title=pack.title_hint,
            what_changed="Insufficient evidence: no primary commit available.",
            limitations="No mirror/diff evidence; do not publish as engineering analysis.",
            confidence="low",
            writer="deterministic",
        )

    prose = prose_from_body(primary.body)
    subject = primary.subject or pack.title_hint
    first = prose[0] if prose else ""
    second = prose[1] if len(prose) > 1 else ""

    files = ", ".join(primary.files[:8]) or "unlisted files"
    funcs = ", ".join(primary.functions[:8])
    tests = ", ".join(primary.tests[:6])

    what = first or (
        f"{subject}. Touches {files}."
        + (f" Notable symbols in the diff: {funcs}." if funcs else "")
    )
    if level == "quick_signal":
        what = (first or subject)[:280]

    prev = ""
    joined = f"{first}\n{second}".lower()
    if second and any(
        k in second.lower()
        for k in ("before", "previously", "instead of", "rather than", "remove", "special case")
    ):
        prev = second[:500]
    elif any(
        k in joined
        for k in ("get rid of", "remove", "instead of", "special case", "previously", "rather than")
    ):
        # Prefer the paragraph that discusses the old path
        for p in prose[:3]:
            pl = p.lower()
            if any(k in pl for k in ("remove", "special case", "instead", "previously", "get rid")):
                prev = p[:500]
                break
        if not prev:
            prev = (
                "Commit message describes replacing a previous path; "
                "confirm exact prior behavior in the linked diff."
            )

    impl_parts = [
        f"Primary `{primary.sha[:12]}` (+{primary.additions}/−{primary.deletions}).",
        f"Files: {files}.",
    ]
    if funcs:
        impl_parts.append(f"Diff-referenced symbols include: {funcs}.")
    if level == "deep_dive" and primary.diff_excerpt:
        # Keep a short factual note — do not invent IR
        impl_parts.append(
            "Diff inspected locally; see primary source for full hunks."
        )

    validation = (
        f"Tests touched: {tests}."
        if tests
        else "No obvious test paths in the primary commit file list."
    )

    audience = []
    for d in pack.domains:
        audience.append(f"{d} developers")
    for h in pack.hardware_targets:
        audience.append(f"{h} backend engineers")
    if pack.stages:
        audience.append(f"{pack.stages[0]} engineers")
    if not audience:
        audience = ["Compiler engineers"]
    audience = list(dict.fromkeys(audience))[:6]

    why = _why_it_matters_from_evidence(
        subject=subject,
        first=first,
        pack=pack,
        audience=audience,
        has_tests=bool(primary.tests),
    )

    notes = [
        f"commit:{primary.sha[:12]}",
        f"files:{len(primary.files)}",
        f"tests:{len(primary.tests)}",
    ]
    if pack.related_shas:
        notes.append(f"cluster:{len(pack.related_shas)} commits")

    confidence = "high" if (prose and primary.files) else "medium" if primary.files else "low"

    return EditorialDraft(
        title=subject.split(":", 1)[-1].strip() if subject.count(":") == 1 and len(subject) > 40 else subject,
        what_changed=what[:900],
        previous_behavior=prev[:600],
        technical_implementation=" ".join(impl_parts),
        why_it_matters=why[:500],
        who_should_care=audience,
        stages=list(pack.stages),
        domains=list(pack.domains),
        hardware_targets=list(pack.hardware_targets),
        change_type=_infer_change_type(subject, primary.body),
        validation=validation,
        performance_impact="Not established from available evidence.",
        limitations=(
            "Interpretation is limited to the commit message and inspected diff. "
            "No performance numbers or invented IR/assembly are claimed without "
            "evidence in the pack."
        ),
        confidence=confidence,
        evidence_notes=notes,
        writer="deterministic",
    )


def _norm_cmp(text: str) -> str:
    return " ".join((text or "").lower().split())


def _why_it_matters_from_evidence(
    *,
    subject: str,
    first: str,
    pack: EvidencePack,
    audience: list[str],
    has_tests: bool,
) -> str:
    """Implication/audience prose — must not clone the commit body / what_changed."""
    bits: list[str] = []
    if pack.hardware_targets:
        bits.append(
            "Affects "
            + ", ".join(pack.hardware_targets[:3])
            + " lowering / target code generation."
        )
    if pack.domains:
        bits.append(f"Matters for {pack.domains[0]} compiler engineering.")
    if pack.stages:
        bits.append(f"Lives in the {pack.stages[0]} of the pipeline.")
    if has_tests:
        bits.append("The same commit touches tests — use those as the reproduce entry point.")
    who = ", ".join(audience[:3]) or "Compiler engineers"
    bits.append(f"Primary audience: {who}.")
    why = " ".join(bits)
    # Hard guard: never publish why identical to the change description
    if first and _norm_cmp(why) == _norm_cmp(first[:500]):
        why = (
            f"Engineers should inspect the linked diff for “{subject[:72]}”; "
            f"broader product impact is not claimed beyond the evidence pack. "
            f"Audience: {who}."
        )
    if _norm_cmp(why) == _norm_cmp(subject):
        why = (
            f"Track this if you maintain related pipeline code. "
            f"Audience: {who}. Broader impact is not established beyond the source."
        )
    return why


def write_with_llm(pack: EvidencePack, *, level: str = "engineering_analysis") -> EditorialDraft | None:
    user = json.dumps(
        {
            "editorial_level": level,
            "evidence": pack.to_prompt_dict(),
            "instructions": (
                "Write using ONLY this evidence. "
                "performance_impact must remain unset/unknown unless numbers appear."
            ),
        },
        ensure_ascii=False,
    )
    data = chat_json(SYSTEM_EDITOR, user)
    if not data:
        return None
    try:
        draft = EditorialDraft.model_validate(data)
    except Exception:
        return None
    draft.writer = "llm"
    draft.raw = data
    # Hard safety: never allow LLM to invent benchmarks silently
    perf = (draft.performance_impact or "").lower()
    if any(k in perf for k in ("% ", "faster", "speedup", "x faster", "improved performance")):
        if "benchmark" not in json.dumps(pack.to_prompt_dict()).lower():
            draft.performance_impact = "Not established from available evidence."
            draft.limitations = (
                (draft.limitations or "")
                + " Performance wording stripped: no benchmark evidence in pack."
            ).strip()
    return draft


def write_development(
    pack: EvidencePack, *, level: str = "engineering_analysis", use_llm: bool = True
) -> EditorialDraft:
    if use_llm:
        llm = write_with_llm(pack, level=level)
        if llm is not None:
            return llm
    return write_deterministic(pack, level=level)
