# SPDX-License-Identifier: Apache-2.0
"""Normalize collected stories while preserving original raw values."""

from __future__ import annotations

from csweekly.models import Story
from csweekly.processors.dedupe import dedupe_stories

# Canonical labels; raw originals stay in story.raw / notes.
_ARCH_MAP = {
    "riscv": "RISC-V",
    "risc-v": "RISC-V",
    "risc_v": "RISC-V",
    "rv64": "RISC-V",
    "rv32": "RISC-V",
    "amdgpu": "AMDGPU",
    "nvptx": "NVPTX",
    "nvvm": "NVVM",
    "spirv": "SPIR-V",
    "spir-v": "SPIR-V",
    "aarch64": "AArch64",
    "arm64": "AArch64",
    "x86": "X86",
    "x86_64": "X86",
    "x86-64": "X86",
}

_PROJECT_MAP = {
    "llvm": "LLVM",
    "llvm-project": "LLVM",
    "mlir": "MLIR",
    "gcc": "GCC",
    "tvm": "TVM",
    "iree": "IREE",
    "triton": "Triton",
}


def _canon_token(value: str, table: dict[str, str]) -> str:
    key = value.strip().lower().replace(" ", "-")
    return table.get(key, value.strip())


def normalize_story(story: Story) -> Story:
    """Return a copy with canonical taxonomy tokens; keep raw originals."""
    out = story.model_copy(deep=True)
    raw_snapshot = {
        "title": story.title,
        "project": story.project,
        "hardware_targets": list(story.hardware_targets),
        "domains": list(story.domains),
        "stages": list(story.stages),
        "technical_areas": list(story.technical_areas),
    }
    notes = dict(out.raw or {})
    notes.setdefault("pre_normalize", raw_snapshot)
    out.raw = notes

    if out.project:
        out.project = _canon_token(out.project, _PROJECT_MAP)

    out.hardware_targets = [
        _canon_token(h, _ARCH_MAP) for h in out.hardware_targets
    ]
    # De-dupe while preserving order
    out.hardware_targets = list(dict.fromkeys(out.hardware_targets))
    out.domains = list(dict.fromkeys(d.strip() for d in out.domains if d.strip()))
    out.stages = list(dict.fromkeys(s.strip() for s in out.stages if s.strip()))
    out.technical_areas = list(
        dict.fromkeys(a.strip() for a in out.technical_areas if a.strip())
    )
    return out


def normalize_stories(stories: list[Story]) -> list[Story]:
    unique = dedupe_stories(stories)
    return [normalize_story(s) for s in unique]
