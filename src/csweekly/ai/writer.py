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

    # Prose-first implementation note. File lists stay in evidence metadata,
    # not the reader-facing explanation (HTML links the primary commit).
    n_files = len(primary.files)
    surface = (
        f"{n_files} LLDB API test modules"
        if any("lldb/test" in f for f in primary.files[:6])
        else f"{n_files} files"
        if n_files
        else "the inspected sources"
    )
    impl_parts = [
        (first or subject).rstrip(".") + ".",
        f"Touches {surface} (+{primary.additions}/−{primary.deletions}).",
    ]
    if funcs and level == "deep_dive":
        # Mention at most a few symbols — never dump the full symbol list inline.
        top = ", ".join(primary.functions[:3])
        impl_parts.append(f"Notable symbols include {top}.")
    if level == "deep_dive" and primary.diff_excerpt:
        impl_parts.append("Diff inspected locally; open the primary commit for full hunks.")

    validation = (
        f"Validation is carried by {len(primary.tests)} touched test path(s); "
        f"use the primary commit as the reproduce entry point."
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
    """Implication prose grounded in evidence — never taxonomy filler."""
    who = ", ".join(audience[:3]) or "Compiler engineers"
    stage = pack.stages[0] if pack.stages else ""
    domain = pack.domains[0] if pack.domains else ""
    targets = [t for t in pack.hardware_targets[:3] if t]
    files = pack.primary.files if pack.primary else []
    path_blob = " ".join(files[:12]).lower()

    # Drop CPU/backend targets the file list does not support (e.g. LLDB tests ≠ AArch64).
    if files and ("lldb/" in path_blob or path_blob.count("/test/") >= 2):
        subj = f"{subject or ''}\n{first or ''}".lower()
        keep: list[str] = []
        for t in targets:
            tl = t.lower()
            if "wasm" in tl or "webassembly" in tl:
                if "wasm" in subj or "webassembly" in subj or "wasm" in path_blob:
                    keep.append(t)
            elif tl in subj or tl in path_blob:
                keep.append(t)
        targets = keep

    bits: list[str] = []
    # Prefer a concrete engineering consequence from the commit body.
    if first:
        lead = first.strip().split("\n")[0][:180].rstrip(".")
        bits.append(f"{lead}.")
    target_bit = f" for {', '.join(targets)}" if targets else ""
    if stage and domain:
        bits.append(
            f"This is {stage.lower()} work{target_bit} with relevance to {domain} engineers."
        )
    elif stage:
        bits.append(f"This lands in the {stage.lower()}{target_bit}.")
    elif targets:
        bits.append(f"Target-relevant change{target_bit}.")
    if has_tests:
        bits.append("Changed tests are the reproduce entry point.")
    bits.append(f"Primary audience: {who}.")
    why = " ".join(bits)

    if first and _norm_cmp(why) == _norm_cmp(first[:500]):
        why = (
            f"Engineers maintaining related {stage or 'pipeline'} code should inspect "
            f"“{subject[:72]}” in the linked diff; broader impact is not claimed beyond "
            f"the evidence pack. Audience: {who}."
        )
    if _norm_cmp(why) == _norm_cmp(subject):
        why = (
            f"Track this if you maintain related {stage or 'pipeline'} code. "
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
