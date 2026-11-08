# SPDX-License-Identifier: Apache-2.0
"""Editorial explanation layer — factual, no invented impact."""

from __future__ import annotations

import re

from csweekly.models import ChangeGroup, ChangeType, SignalLevel, Story
from csweekly.processors.editorial import clean_subject, editorial_sentence, is_noise

_WHY_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?i)\bnvvm\b|\bnvptx\b"),
        "Extends NVIDIA GPU IR / NVVM dialect support used when lowering GPU kernels.",
    ),
    (
        re.compile(r"(?i)amdgpu|amdgcn"),
        "Touches AMDGPU backend behavior — instruction selection, ABI, or codegen for AMD GPUs.",
    ),
    (
        re.compile(r"(?i)spir-?v|spirv"),
        "Touches SPIR-V translation or tooling used by portable GPU / offload stacks.",
    ),
    (
        re.compile(r"(?i)\bCIR\b|clang.?ir|matrix splat"),
        "Extends Clang IR (CIR) language/codegen coverage — relevant to frontend and HLSL/matrix lowering.",
    ),
    (
        re.compile(r"(?i)vectoriz|loop.?vector|sve\b|sve2|avx512.*vector"),
        "Affects automatic vectorization and SIMD code generation.",
    ),
    (
        re.compile(r"(?i)register.?alloc|regalloc"),
        "Touches register allocation — impacts backend quality and spill behavior.",
    ),
    (
        re.compile(r"(?i)globalisel|selectiondag|isel|instruction select"),
        "Changes instruction selection — how IR becomes machine instructions.",
    ),
    (re.compile(r"(?i)inline|inlining"), "Affects inlining decisions and resulting code size/performance tradeoffs."),
    (re.compile(r"(?i)alias.?analy"), "Changes alias analysis — foundational for many middle-end optimizations."),
    (
        re.compile(r"(?i)compile.?time|compile time"),
        "Aimed at compile-time cost (message claims this; verify in source).",
    ),
    (re.compile(r"(?i)security|cve|sanitizer"), "Related to correctness/security hardening."),
    (
        re.compile(r"(?i)\babi\b|calling.?convention"),
        "Touches ABI / calling-convention behavior — can affect interoperability.",
    ),
    (
        re.compile(r"(?i)add support|implement support|introduce support|initial support"),
        "Adds or extends target/feature support.",
    ),
    (re.compile(r"(?i)diagnostic|error message"), "Improves diagnostics seen by language users."),
    (
        re.compile(r"(?i)debug.?info|dwarf|lldb"),
        "Affects debug information or debugger experience.",
    ),
    (
        re.compile(r"(?i)offload|openmp|cuda|hip|\bgpu\b"),
        "Touches GPU/offloading code generation or runtime.",
    ),
    (
        re.compile(r"(?i)linalg|tosa|stablehlo|torch-mlir"),
        "Changes MLIR dialect/transform infrastructure used by AI and accelerator compilers.",
    ),
    (
        re.compile(r"(?i)\bmlir\b|dialect"),
        "Changes MLIR dialect or transformation infrastructure.",
    ),
    (
        re.compile(r"(?i)\bfix\b|ice|crash|assert"),
        "Correctness fix — prevents miscompile or compiler crash (per commit subject).",
    ),
    (
        re.compile(r"(?i)optimize|performance|faster"),
        "Described as an optimization/performance change in the source message.",
    ),
    (re.compile(r"(?i)legaliz"), "Changes legalization — which IR patterns a backend can handle."),
    (re.compile(r"(?i)schedule|schedul"), "Touches instruction scheduling / machine models."),
    (
        re.compile(r"(?i)vec_perm|subvector|splat"),
        "Touches vector permute / subvector lowering used by SIMD backends.",
    ),
]

_TYPE_RULES: list[tuple[re.Pattern[str], ChangeType]] = [
    (re.compile(r"(?i)fix|ice|crash|assert|bug"), ChangeType.BUG_FIX),
    (re.compile(r"(?i)add support|implement|introduce|initial support"), ChangeType.NEW_CAPABILITY),
    (re.compile(r"(?i)vectoriz|optimize|improve.*(perf|speed|latency)"), ChangeType.OPTIMIZATION),
    (re.compile(r"(?i)globalisel|codegen|isel|instruction select"), ChangeType.CODEGEN),
    (re.compile(r"(?i)clang/|parser|sema|frontend"), ChangeType.FRONTEND),
    (re.compile(r"(?i)target/|backend|amdgpu|aarch64|riscv|x86"), ChangeType.BACKEND),
    (re.compile(r"(?i)\bir\b|mlir|gimple|llvm ir"), ChangeType.IR),
    (re.compile(r"(?i)runtime|libcxx|compiler-rt|jit"), ChangeType.RUNTIME),
    (re.compile(r"(?i)cmake|build|ci|testsuite|tooling"), ChangeType.INFRASTRUCTURE),
    (re.compile(r"(?i)arxiv|paper"), ChangeType.RESEARCH),
]

_AUDIENCE = {
    "Frontend": "Frontend / Clang developers",
    "Middle-end": "Middle-end / optimization developers",
    "Backend": "Backend developers",
    "Runtime & Toolchain": "Runtime and toolchain developers",
    "GPU": "GPU compiler developers",
    "AI / ML": "AI compiler developers",
    "CPU": "CPU compiler developers",
    "Research": "Compiler researchers",
    "Vectorization": "Performance engineers",
    "Register allocation": "Backend developers",
    "Code generation": "CodeGen developers",
    "Debugging": "Debugger / debug-info developers",
}


def explain_story(story: Story) -> Story:
    subject = clean_subject(story.summary or story.title)
    story.what_changed = _what_changed(story, subject)
    why, uncertain = _why_it_matters(story, subject)
    story.why_it_matters = why
    story.impact_uncertain = uncertain
    story.who_should_care = _who_should_care(story)
    story.change_type = _change_type(story, subject).value
    story.signal = _signal_for_story(story, subject)
    return story


def explain_group(group: ChangeGroup) -> ChangeGroup:
    for s in group.stories:
        explain_story(s)
    primary = group.stories[0]
    n = len(group.stories)
    # Prefer human headline from cleaned subject, not machine group keys
    headline = clean_subject(primary.title) or clean_subject(primary.summary or "")
    if headline:
        group.title = headline[:140]
    base = editorial_sentence(group)
    if n > 1:
        group.what_changed = (
            f"{base} This groups {n} related commits as one development theme."
        )
    else:
        group.what_changed = primary.what_changed or base

    # Prefer a confident why from any member; else uncertain
    certain = [s for s in group.stories if s.why_it_matters and not s.impact_uncertain]
    if certain:
        group.why_it_matters = certain[0].why_it_matters
        group.impact_uncertain = False
    else:
        group.why_it_matters = (
            primary.why_it_matters
            or "The practical impact is not yet clear from the commit message alone."
        )
        group.impact_uncertain = True

    audience: list[str] = []
    for s in group.stories:
        for a in s.who_should_care:
            if a not in audience:
                audience.append(a)
    group.who_should_care = audience[:5] or ["Compiler engineers"]

    # Majority change type / taxonomy
    group.change_type = primary.change_type
    group.stages = _merge_lists(*(s.stages for s in group.stories))
    group.domains = _merge_lists(*(s.domains for s in group.stories))
    group.technical_areas = _merge_lists(*(s.technical_areas for s in group.stories))
    group.hardware_targets = _merge_lists(*(s.hardware_targets for s in group.stories))
    group.story_id = primary.story_id or group.id
    group.signal = max(
        (s.signal for s in group.stories),
        key=lambda sig: {
            SignalLevel.DEEP_DIVE: 3,
            SignalLevel.HIGH_SIGNAL: 2,
            SignalLevel.WORTH_KNOWING: 1,
            SignalLevel.SKIP: 0,
        }[sig],
    )
    # Multi-commit themes often deserve at least worth_knowing
    if n >= 3 and group.signal == SignalLevel.SKIP and not all(
        is_noise(s) for s in group.stories
    ):
        group.signal = SignalLevel.WORTH_KNOWING
    return group


def _what_changed(story: Story, subject: str) -> str:
    if story.evidence_kind.value == "arxiv":
        return f"Research paper: {subject}."
    if story.evidence_kind.value in {"rss", "web_announcement"}:
        return f"Community/announcement item: {subject}."
    if story.evidence_kind.value == "github_release":
        return f"Release published: {subject}."
    return editorial_sentence(
        ChangeGroup(
            id=story.id,
            title=story.title,
            category=story.category,
            project=story.project or story.category,
            stories=[story],
        )
    )


def _why_it_matters(story: Story, subject: str) -> tuple[str, bool]:
    # Prefer subject/title — areas previously caused generic false matches
    # (e.g. test files named *_vector.mlir → "vectorization").
    primary = f"{subject}\n{story.title}"
    paths = "\n".join(story.paths[:12])
    for pat, msg in _WHY_RULES:
        if pat.search(primary):
            return msg, False
    for pat, msg in _WHY_RULES:
        if pat.search(paths):
            return msg, False
    if "GPU" in story.domains:
        return "Touches GPU compiler infrastructure or target lowering.", False
    if "Frontend" in story.stages and "Languages" in story.domains:
        return "Extends language frontend coverage — verify impact in the linked source.", False
    return (
        "The practical impact is not yet clear from the commit message alone.",
        True,
    )


def _who_should_care(story: Story) -> list[str]:
    out: list[str] = []
    for key in list(story.stages) + list(story.domains) + list(story.technical_areas):
        aud = _AUDIENCE.get(key)
        if aud and aud not in out:
            out.append(aud)
    if story.hardware_targets:
        for h in story.hardware_targets[:2]:
            label = f"{h} developers"
            if label not in out:
                out.append(label)
    if not out:
        out = ["Compiler engineers"]
    return out[:5]


def _change_type(story: Story, subject: str) -> ChangeType:
    blob = f"{subject}\n{story.title}\n{' '.join(story.paths[:6])}"
    for pat, ctype in _TYPE_RULES:
        if pat.search(blob):
            return ctype
    if story.evidence_kind.value == "arxiv":
        return ChangeType.RESEARCH
    return ChangeType.OTHER


def _signal_for_story(story: Story, subject: str) -> SignalLevel:
    if is_noise(story):
        return SignalLevel.SKIP
    if story.evidence_kind.value in {"arxiv", "rss", "github_release"}:
        return SignalLevel.WORTH_KNOWING
    text = f"{subject}\n{story.title}".lower()
    high = (
        "add support",
        "implement",
        "introduce",
        "new backend",
        "abi",
        "security",
        "cve",
        "vectoriz",
        "globalisel",
        "legaliz",
        "performance",
    )
    if any(t in text for t in high):
        return SignalLevel.HIGH_SIGNAL
    if story.importance.value == "highlight":
        return SignalLevel.HIGH_SIGNAL
    if story.importance.value == "notable":
        return SignalLevel.WORTH_KNOWING
    if story.areas and set(story.areas) & {
        "Instruction selection",
        "Vectorization",
        "MLIR dialects",
        "IR",
        "Code generation",
        "Register allocation",
        "GPU",
        "Backend",
    }:
        return SignalLevel.WORTH_KNOWING
    return SignalLevel.SKIP


def _merge_lists(*seqs: list[str]) -> list[str]:
    out: list[str] = []
    for seq in seqs:
        for item in seq:
            if item not in out:
                out.append(item)
    return out[:8]


def make_story_id(story: Story) -> str:
    """Stable continuity key across weeks (theme, not commit)."""
    from csweekly.processors.group import subject_key

    key = subject_key(story.title)
    proj = (story.project or story.category or "misc").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", f"{proj}-{key}").strip("-")[:80]
    return slug or f"{proj}-change"
