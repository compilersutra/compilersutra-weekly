# SPDX-License-Identifier: Apache-2.0
"""Editorial explanation layer — source-grounded, no invented impact."""

from __future__ import annotations

import re

from csweekly.models import ChangeGroup, ChangeType, SignalLevel, Story
from csweekly.processors.editorial import clean_subject, editorial_sentence, is_noise

# Specific (pattern, template). Templates may use {subject}, {component}, {hw}.
# Only fire when the subject/title (not test paths) establish the mechanism.
_WHY_SPECIFIC: list[tuple[re.Pattern[str], str, bool]] = [
    (
        re.compile(r"(?i)\bnvvm\.?\w*|add nvvm"),
        "Adds or extends an NVVM dialect operation ({subject}). "
        "This widens NVIDIA GPU IR available when MLIR lowers to LLVM IR — "
        "not a claim about kernel runtime performance.",
        False,
    ),
    (
        re.compile(r"(?i)matrix splat|CIR.*splat|\bCIR\b.*matrix"),
        "Extends Clang IR (CIR) coverage for matrix splat casts ({subject}). "
        "This is frontend/CIR codegen work (incl. HLSL paths when present), "
        "not middle-end auto-vectorization.",
        False,
    ),
    (
        re.compile(r"(?i)vec_perm_const|extract subvector"),
        "Changes how the RISC-V backend forms subvector extracts "
        "({subject}). Related commits in the cluster touch permute costing "
        "and vector lowering — inspect diffs before claiming perf wins.",
        False,
    ),
    (
        re.compile(r"(?i)\babi\b|calling.?convention|RISCVABI"),
        "Touches ABI / calling-convention helpers ({subject}). "
        "Wrong ABI lowers can break interoperability; this is not "
        "automatically a register-allocator change.",
        False,
    ),
    (
        re.compile(r"(?i)amdgpu|amdgcn|SIFixSGPR|D16 high"),
        "AMDGPU backend change ({subject}). Likely instruction selection, "
        "SGPR/VGPR handling, or ABI occupancy — verify in the linked diffs.",
        False,
    ),
    (
        re.compile(r"(?i)spir-?v|spirv|SPIRVTranslate"),
        "SPIR-V translation / tooling change ({subject}). Affects portable "
        "GPU / offload stacks that consume SPIR-V, not CPU backends.",
        False,
    ),
    (
        re.compile(r"(?i)loop.?vector|vectoriz(?:e|ation|er)\b"),
        "Commit subject explicitly concerns vectorization ({subject}). "
        "Do not assume measured speedups without benchmarks.",
        False,
    ),
    (
        re.compile(r"(?i)regalloc|register.?alloc"),
        "Commit subject explicitly concerns register allocation ({subject}).",
        False,
    ),
    (
        re.compile(r"(?i)globalisel|selectiondag|instruction select|\bisel\b"),
        "Instruction-selection / ISel change ({subject}): how IR becomes "
        "machine instructions for the target.",
        False,
    ),
    (
        re.compile(r"(?i)dwarf|debug.?info|lldb|DWARF"),
        "Debug-info or debugger tooling change ({subject}). Relevant to "
        "Runtime & Toolchain / debugging workflows.",
        False,
    ),
    (
        re.compile(r"(?i)RuntimeLibcalls|libcall"),
        "RuntimeLibcalls / compiler-rt interface change ({subject}). "
        "Affects how the compiler declares or emits library calls.",
        False,
    ),
]

_TYPE_RULES: list[tuple[re.Pattern[str], ChangeType]] = [
    (re.compile(r"(?i)\b(fix|ice|crash|assert|bug)\b"), ChangeType.BUG_FIX),
    (re.compile(r"(?i)add support|implement|introduce|initial support"), ChangeType.NEW_CAPABILITY),
    (re.compile(r"(?i)vectoriz|optimize|improve.*(perf|speed|latency)"), ChangeType.OPTIMIZATION),
    (re.compile(r"(?i)globalisel|codegen|isel|instruction select"), ChangeType.CODEGEN),
    (re.compile(r"(?i)clang/|parser|sema|frontend|\bCIR\b"), ChangeType.FRONTEND),
    (re.compile(r"(?i)target/|backend|amdgpu|aarch64|riscv|x86|nvvm|nvptx"), ChangeType.BACKEND),
    (re.compile(r"(?i)\bir\b|mlir|gimple|llvm ir|dialect"), ChangeType.IR),
    (re.compile(r"(?i)runtime|libcxx|compiler-rt|jit|RuntimeLibcalls"), ChangeType.RUNTIME),
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
    "Languages": "Language frontend developers",
    "Debugging": "Debugger / debug-info developers",
    "Code generation": "CodeGen developers",
}


def explain_story(story: Story) -> Story:
    subject = clean_subject(story.summary or story.title)
    story.what_changed = _what_changed(story, subject)
    story.technical_context = _technical_context(story)
    why, uncertain, note = _why_it_matters(story, subject)
    story.why_it_matters = why
    story.impact_uncertain = uncertain
    story.uncertainty_note = note
    story.who_should_care = _who_should_care(story)
    story.change_type = _change_type(story, subject).value
    story.signal = _signal_for_story(story, subject)
    return story


def explain_group(group: ChangeGroup) -> ChangeGroup:
    for s in group.stories:
        explain_story(s)
    primary = group.stories[0]
    n = len(group.stories)
    headline = clean_subject(primary.title) or clean_subject(primary.summary or "")
    if headline:
        group.title = headline[:140]
    base = editorial_sentence(group)
    if n > 1:
        group.what_changed = (
            f"{base} Cluster of {n} related commits treated as one development."
        )
    else:
        group.what_changed = primary.what_changed or base

    certain = [s for s in group.stories if s.why_it_matters and not s.impact_uncertain]
    if certain:
        # Prefer why from the primary subject match, else first certain
        group.why_it_matters = primary.why_it_matters if not primary.impact_uncertain else certain[0].why_it_matters
        group.impact_uncertain = False
        group.uncertainty_note = primary.uncertainty_note
    else:
        group.why_it_matters = (
            primary.why_it_matters
            or "The practical impact is not yet clear from the commit message alone."
        )
        group.impact_uncertain = True
        group.uncertainty_note = (
            primary.uncertainty_note
            or "Broader impact is not established from commit subjects alone."
        )

    group.technical_context = primary.technical_context or _technical_context(primary)
    group.change_type = primary.change_type
    group.stages = _reconcile_stages(_merge_lists(*(s.stages for s in group.stories)), group)
    group.domains = _merge_lists(*(s.domains for s in group.stories))
    group.technical_areas = _merge_lists(*(s.technical_areas for s in group.stories))
    group.hardware_targets = _merge_lists(*(s.hardware_targets for s in group.stories))
    group.who_should_care = _who_should_care_group(group)
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
    if n >= 3 and group.signal == SignalLevel.SKIP and not all(
        is_noise(s) for s in group.stories
    ):
        group.signal = SignalLevel.WORTH_KNOWING
    return group


def build_deep_dive_notes(group: ChangeGroup) -> dict[str, str]:
    """Honest deep-dive outline from subjects only — no invented assembly/benchmarks."""
    subjects = [
        clean_subject(s.summary or s.title) or (s.title or "")[:100]
        for s in group.stories
    ]
    primary = subjects[0] if subjects else group.title
    related = [s for s in subjects[1:6] if s and s != primary]
    hw = ", ".join(group.hardware_targets[:3]) or "unspecified target"
    stages = ", ".join(group.stages) or "unclassified"
    notes = {
        "background": (
            f"This cluster is treated as one development theme because the "
            f"commits share a subject family around “{primary[:100]}”."
            + (
                f" Related subjects this week include: "
                + "; ".join(related)
                + "."
                if related
                else ""
            )
        ),
        "previous_behavior": (
            "Prior compiler behavior is not restated in the commit subjects. "
            "Read the linked diffs for the pre-change lowering / helper path."
        ),
        "problem": (
            f"The change addresses: {primary}. "
            "Treat this as the stated problem — do not invent a larger architecture thesis."
        ),
        "implementation": group.what_changed
        or "See the primary source commit for the implementation.",
        "example": (
            "No concrete IR/assembly example is emitted automatically from subjects. "
            "Open the primary source if you need a worked example."
        ),
        "implications": (
            f"{group.why_it_matters or 'Impact unclear from subjects.'} "
            f"Stage: {stages}. Hardware/target hints: {hw}."
        ),
        "limits": (
            group.uncertainty_note
            or "No performance numbers, generated assembly, or completion claims "
            "are inferred from commit subjects alone."
        ),
    }
    group.deep_dive_notes = notes
    return notes


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


def _technical_context(story: Story) -> str:
    paths = story.paths[:6]
    if not paths:
        return f"Project: {story.project or story.category}."
    roots = []
    for p in paths:
        part = p.split("/")[0] if "/" in p else p
        if part and part not in roots:
            roots.append(part)
    hint = ", ".join(roots[:4])
    area = ", ".join((story.technical_areas or story.areas or [])[:3]) or "unclassified"
    return f"Touched trees: {hint}. Technical areas: {area}."


def _why_it_matters(story: Story, subject: str) -> tuple[str, bool, str]:
    primary = f"{subject}\n{story.title}"
    component = _path_component(story)
    hw = ", ".join(story.hardware_targets[:2]) or ""
    for pat, tmpl, uncertain in _WHY_SPECIFIC:
        if pat.search(primary):
            msg = tmpl.format(subject=subject[:100], component=component, hw=hw)
            note = (
                "Impact beyond the commit subject is not independently verified."
                if uncertain
                else "Explanation grounded in the commit subject; open the source for details."
            )
            return msg, uncertain, note

    # Soft path hints only after subject miss — still include the subject.
    path_blob = "\n".join(story.paths[:8])
    if re.search(r"(?i)NVVM|NVPTX", path_blob):
        return (
            f"Touches NVVM/NVPTX paths while landing “{subject[:90]}”. "
            "Treat as GPU IR / target-lowering work unless the diff shows otherwise.",
            False,
            "Path-based GPU hint; verify in the linked source.",
        )
    if re.search(r"(?i)AMDGPU", path_blob):
        return (
            f"Touches AMDGPU paths while landing “{subject[:90]}”.",
            False,
            "Path-based AMDGPU hint; verify in the linked source.",
        )

    note = "Broader impact is not established from the commit message alone."
    return (
        f"Source subject: “{subject[:120]}”. "
        f"Apparent component: {component}. {note}",
        True,
        note,
    )


def _path_component(story: Story) -> str:
    for p in story.paths:
        for pref, name in (
            ("llvm/lib/Target/AMDGPU/", "AMDGPU backend"),
            ("llvm/lib/Target/RISCV/", "RISC-V backend"),
            ("llvm/lib/Target/X86/", "X86 backend"),
            ("llvm/lib/Target/AArch64/", "AArch64 backend"),
            ("llvm/lib/Target/SPIRV/", "SPIR-V backend"),
            ("llvm/lib/CodeGen/", "LLVM CodeGen"),
            ("clang/lib/CIR/", "Clang CIR"),
            ("clang/", "Clang frontend"),
            ("mlir/Dialect/LLVMIR/NVVM", "MLIR NVVM dialect"),
            ("mlir/", "MLIR"),
            ("gcc/config/", "GCC target backend"),
            ("gcc/", "GCC"),
            ("lldb/", "LLDB"),
        ):
            if p.startswith(pref) or pref.rstrip("/") in p:
                return name
    return story.project or story.category or "compiler"


def _who_should_care(story: Story) -> list[str]:
    # Audience follows primary stage + domain only — not every technical area.
    keys = list(story.stages[:2]) + list(story.domains[:2])
    if "Debugging" in story.technical_areas or any(
        "lldb" in p or "Debug" in p for p in story.paths[:6]
    ):
        keys.append("Debugging")
    out: list[str] = []
    for key in keys:
        aud = _AUDIENCE.get(key)
        if aud and aud not in out:
            out.append(aud)
    for h in story.hardware_targets[:2]:
        label = f"{h} developers"
        if label not in out:
            out.append(label)
    return (out or ["Compiler engineers"])[:4]


def _who_should_care_group(group: ChangeGroup) -> list[str]:
    fake = Story(
        id=group.id,
        title=group.title,
        source_url="",
        source_org="",
        category=group.category,
        project=group.project,
        discovered_at=group.stories[0].discovered_at,
        evidence_kind=group.stories[0].evidence_kind,
        summary=group.title,
        stages=group.stages,
        domains=group.domains,
        technical_areas=group.technical_areas,
        hardware_targets=group.hardware_targets,
        paths=group.stories[0].paths,
    )
    return _who_should_care(fake)


def _reconcile_stages(stages: list[str], group: ChangeGroup) -> list[str]:
    """Drop weak Runtime tags when the primary change is clearly frontend/backend IR."""
    paths = "\n".join(p for s in group.stories for p in s.paths[:8])
    title = group.title + "\n" + (group.stories[0].summary or "")
    strong_fe = bool(re.search(r"(?i)clang/|CIR|flang/|gcc/(c|cp|fortran)/", paths + title))
    strong_be = bool(
        re.search(r"(?i)lib/Target/|CodeGen/|NVVM|AMDGPU|gcc/config/", paths + title)
    )
    strong_rt = bool(
        re.search(r"(?i)lldb/|lld/|compiler-rt/|libcxx|RuntimeLibcalls", paths + title)
    )
    out = list(stages)
    if "Runtime & Toolchain" in out and not strong_rt and (strong_fe or strong_be):
        out = [s for s in out if s != "Runtime & Toolchain"]
    if strong_fe and "Frontend" not in out:
        out.insert(0, "Frontend")
    if strong_be and "Backend" not in out and "Middle-end" in out:
        # NVVM dialect often middle-end IR + GPU backend interest
        if re.search(r"(?i)NVVM|NVPTX|AMDGPU|Target/", paths):
            out.append("Backend")
    return out[:4]


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
        "nvvm",
        "vec_perm",
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
