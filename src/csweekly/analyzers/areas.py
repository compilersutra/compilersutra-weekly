# SPDX-License-Identifier: Apache-2.0
"""Classify commits by changed-file paths (not message keywords alone)."""

from __future__ import annotations

import re

_PATH_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|/)(clang|clang-tools-extra)/", re.I), "Frontend"),
    (re.compile(r"(^|/)flang/", re.I), "Frontend"),
    (re.compile(r"(^|/)lldb/", re.I), "Debug information"),
    (re.compile(r"(^|/)lld/", re.I), "Linker"),
    (re.compile(r"(^|/)mlir/", re.I), "MLIR dialects"),
    (re.compile(r"(^|/)llvm/lib/IR/", re.I), "IR"),
    (re.compile(r"(^|/)llvm/lib/Transforms/", re.I), "Optimization"),
    (re.compile(r"(^|/)llvm/lib/Analysis/", re.I), "Optimization"),
    # Avoid false positives from filenames like mulf_vector.mlir or Matrix*.
    (re.compile(r"LoopVector|Vectorize|vectoriz", re.I), "Vectorization"),
    (re.compile(r"(^|/)llvm/lib/CodeGen/GlobalISel/", re.I), "Instruction selection"),
    (re.compile(r"(^|/)llvm/lib/CodeGen/SelectionDAG/", re.I), "Instruction selection"),
    (re.compile(r"(^|/)llvm/lib/CodeGen/", re.I), "Code generation"),
    # Require RegAlloc / RegisterInfo — bare "Register" matches too many ABI helpers.
    # Avoid matching "Register" inside unrelated names (e.g. helper Register* APIs outside RA).
    (re.compile(r"(?i)(^|/)RegAlloc|RegisterCoalescer|register.?alloc"), "Register allocation"),
    (re.compile(r"Schedule|Scheduler|MachineScheduler", re.I), "Scheduling"),
    (re.compile(r"(^|/)llvm/lib/Target/", re.I), "Backend"),
    (re.compile(r"AMDGPU|NVPTX|NVVM|SPIRV|DirectX|cuda|rocm|hip", re.I), "GPU"),
    (re.compile(r"(^|/)compiler-rt/|(^|/)libcxx|(^|/)libunwind", re.I), "Runtime"),
    (re.compile(r"Diagnostic|diag", re.I), "Diagnostics"),
    (re.compile(r"(^|/)cmake/|\.yml$|\.yaml$|BUILD\.bazel|CMakeLists", re.I), "Build infrastructure"),
    (re.compile(r"(^|/)test/|(^|/)unittests/|\.ll$|\.mlir$", re.I), "Testing"),
    (re.compile(r"(^|/)docs/|\.md$|\.rst$", re.I), "Documentation"),
    (re.compile(r"(^|/)gcc/(cp|c|fortran|ada|go|d)/", re.I), "Frontend"),
    (re.compile(r"(^|/)gcc/(gimple|tree-|pass)", re.I), "Optimization"),
    (re.compile(r"(^|/)gcc/config/", re.I), "Backend"),
    (re.compile(r"triton|iree|tvm|xla|stablehlo|inductor", re.I), "GPU"),
]


def classify_areas(paths: list[str], subject: str = "") -> list[str]:
    found: list[str] = []
    blob = "\n".join(paths) + "\n" + subject
    for pattern, area in _PATH_RULES:
        if pattern.search(blob) and area not in found:
            found.append(area)
    if not found:
        found.append("Other")
    return found[:6]
