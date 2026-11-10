# SPDX-License-Identifier: Apache-2.0
"""Three independent discovery dimensions — evidence-based, multi-label."""

from __future__ import annotations

import re

from csweekly.models import Story

# Stable vocabulary used by pages + filters
STAGES = ("Frontend", "Middle-end", "Backend", "Runtime & Toolchain")
DOMAINS = (
    "CPU",
    "GPU",
    "AI / ML",
    "Accelerators",
    "FPGA",
    "DSP",
    "Quantum",
    "Languages",
    "Research",
)
TECH_AREAS = (
    "Language",
    "Parsing",
    "Semantics",
    "IR",
    "Analysis",
    "Optimization",
    "Vectorization",
    "Code generation",
    "Register allocation",
    "Scheduling",
    "Memory",
    "Parallelism",
    "Runtime",
    "Performance",
    "Security",
    "Debugging",
    "Tooling",
    "Research",
)

# Areas that should not dominate stage classification when stronger signals exist.
_WEAK_AREAS = frozenset({"Testing", "Documentation", "Build infrastructure", "Other"})

_PATH_STAGE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|/)(clang|flang|gcc/(c|cp|fortran)|rustc)/", re.I), "Frontend"),
    (
        re.compile(
            r"(^|/)(llvm/lib/IR|llvm/lib/Analysis|llvm/lib/Transforms|mlir|gimple)/",
            re.I,
        ),
        "Middle-end",
    ),
    (
        re.compile(
            r"(^|/)(llvm/lib/CodeGen|llvm/lib/Target|gcc/config|SelectionDAG|GlobalISel)/",
            re.I,
        ),
        "Backend",
    ),
    (
        re.compile(
            r"(^|/)(compiler-rt|libcxx|lld|lldb|runtime|jit|linker|SPIRVAPI)/",
            re.I,
        ),
        "Runtime & Toolchain",
    ),
]

_PATH_DOMAIN: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"AMDGPU|NVPTX|NVVM|SPIRV|cuda|rocm|hip|\bgpu\b", re.I), "GPU"),
    (re.compile(r"triton|xla|iree|tvm|stablehlo|inductor|tensor", re.I), "AI / ML"),
    (re.compile(r"quantum|qiskit|cirq|qubit", re.I), "Quantum"),
    (re.compile(r"\bfpga\b|\bhls\b|\bverilog\b|\bvhdl\b|\bcirct\b", re.I), "FPGA"),
    (re.compile(r"X86|AArch64|RISCV|ARM|PowerPC|gcc/config", re.I), "CPU"),
    (re.compile(r"clang|rust|swift|fortran|zig|\bCIR\b", re.I), "Languages"),
]

_AREA_MAP = {
    "Frontend": ("Frontend", ["Language", "Semantics"]),
    "Parser": ("Frontend", ["Parsing"]),
    "Semantic analysis": ("Frontend", ["Semantics"]),
    "IR": ("Middle-end", ["IR"]),
    "MLIR dialects": ("Middle-end", ["IR"]),
    "Optimization": ("Middle-end", ["Optimization"]),
    "Vectorization": ("Middle-end", ["Vectorization"]),
    "Instruction selection": ("Backend", ["Code generation"]),
    "Code generation": ("Backend", ["Code generation"]),
    "Register allocation": ("Backend", ["Register allocation"]),
    "Scheduling": ("Backend", ["Scheduling"]),
    "Backend": ("Backend", ["Code generation"]),
    "GPU": ("Backend", ["Code generation", "Parallelism"]),
    "Runtime": ("Runtime & Toolchain", ["Runtime"]),
    "Linker": ("Runtime & Toolchain", ["Tooling"]),
    "Debug information": ("Runtime & Toolchain", ["Debugging"]),
    "Diagnostics": ("Frontend", ["Language"]),
    "Build infrastructure": ("Runtime & Toolchain", ["Tooling"]),
    "Testing": ("Runtime & Toolchain", ["Tooling"]),
    "Documentation": ("Runtime & Toolchain", ["Tooling"]),
}


def classify_dimensions(story: Story) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (stages, domains, technical_areas, hardware_targets)."""
    stages: list[str] = []
    domains: list[str] = []
    areas: list[str] = []
    hardware: list[str] = []
    blob = "\n".join(story.paths) + "\n" + story.title + "\n" + (story.summary or "")

    for pat, stage in _PATH_STAGE:
        if pat.search(blob) and stage not in stages:
            stages.append(stage)
    for pat, domain in _PATH_DOMAIN:
        if pat.search(blob) and domain not in domains:
            domains.append(domain)

    strong = [a for a in story.areas if a not in _WEAK_AREAS]
    weak = [a for a in story.areas if a in _WEAK_AREAS]
    for area in strong:
        mapped = _AREA_MAP.get(area)
        if mapped:
            st, techs = mapped
            if st not in stages:
                stages.append(st)
            for t in techs:
                if t not in areas:
                    areas.append(t)
    # Weak areas only contribute tooling labels; stage only if nothing else found.
    for area in weak:
        mapped = _AREA_MAP.get(area)
        if not mapped:
            continue
        st, techs = mapped
        for t in techs:
            if t not in areas:
                areas.append(t)
        if not stages and st not in stages:
            stages.append(st)

    cat = story.category
    if cat == "ai" and "AI / ML" not in domains:
        domains.append("AI / ML")
    if cat == "gpu" and "GPU" not in domains:
        domains.append("GPU")
    if cat == "research" and "Research" not in domains:
        domains.append("Research")
        if "Research" not in areas:
            areas.append("Research")
    # MLIR is infrastructure — do not force AI/ML when GPU evidence is present.
    if cat == "mlir":
        if "GPU" in domains or re.search(r"NVVM|NVPTX|AMDGPU|GPU", blob, re.I):
            if "GPU" not in domains:
                domains.append("GPU")
            if "Backend" not in stages:
                stages.append("Backend")
        elif "AI / ML" not in domains:
            domains.append("AI / ML")
    # CPU is a hardware domain — do not attach it to every LLVM/GCC frontend,
    # language, or debugger change. Require target/backend evidence.
    if cat in {"llvm", "gcc"} and "CPU" not in domains and "GPU" not in domains:
        has_cpu_target = bool(
            re.search(
                r"llvm/lib/Target/|llvm/lib/CodeGen|gcc/config|"
                r"SelectionDAG|GlobalISel|"
                r"RISCV|RISC-V|X86|AArch64|ARM|PowerPC|LoongArch",
                blob,
                re.I,
            )
        )
        is_lang_or_debug = bool(
            re.search(
                r"(^|/)(clang|flang|lldb|CIR|HLSL)/|\bDWARF\b|\bFortran\b",
                blob,
                re.I,
            )
        )
        if has_cpu_target:
            domains.append("CPU")
        elif not domains and not is_lang_or_debug:
            domains.append("CPU")
        elif is_lang_or_debug and "Languages" not in domains:
            if re.search(r"lldb|DWARF", blob, re.I):
                # Debugger / debug-info work — not a CPU-domain story by default.
                pass
            elif "Languages" not in domains:
                domains.append("Languages")

    for name, pat in (
        ("AMDGPU", r"AMDGPU|amdgcn"),
        ("NVPTX", r"NVPTX|nvptx|NVVM|nvvm"),
        ("SPIR-V", r"SPIR-?V"),
        ("RISC-V", r"RISCV|RISC-V|riscv"),
        ("AArch64", r"AArch64|aarch64"),
        ("X86", r"X86|x86"),
        ("LoongArch", r"LoongArch"),
        ("WebAssembly", r"WebAssembly|wasm"),
    ):
        if re.search(pat, blob, re.I) and name not in hardware:
            hardware.append(name)

    if not stages:
        stages = ["Middle-end"] if story.evidence_kind.value == "git_commit" else []
    if not domains and story.category == "other":
        domains = ["Languages"]
    if not areas:
        areas = ["Tooling"] if story.evidence_kind.value != "arxiv" else ["Research"]

    return stages[:4], domains[:4], areas[:6], hardware[:6]
