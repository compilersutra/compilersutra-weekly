# SPDX-License-Identifier: Apache-2.0
"""Explainable importance — strict enough for a readable newsletter."""

from __future__ import annotations

import re

from csweekly.models import Importance, Story

_HIGHLIGHT = re.compile(
    r"\b("
    r"implement|introduce|add support|new backend|new pass|landed|"
    r"security|CVE|ABI|GlobalISel|vectoriz|"
    r"initial support|teach\b|learned to"
    r")\b",
    re.I,
)
_NOTABLE = re.compile(
    r"\b(fix|improve|optimize|enable|extend|migrate|rewrite|remove|rename)\b",
    re.I,
)
_NOISE = re.compile(
    r"\b(revert\b|docs?|documentation|typo|nfc|test only|update tests|clang-format)\b",
    re.I,
)


def assign_importance(story: Story) -> Importance:
    if story.evidence_kind.value == "github_release":
        return Importance.HIGHLIGHT
    text = f"{story.title}\n{story.summary}"
    areas = set(story.areas)
    if _NOISE.search(text) and not _HIGHLIGHT.search(text):
        return Importance.OTHER
    if _HIGHLIGHT.search(text):
        return Importance.HIGHLIGHT
    # Path evidence alone → notable only for core compiler surfaces
    if areas & {
        "Instruction selection",
        "Vectorization",
        "MLIR dialects",
        "IR",
        "Code generation",
        "Register allocation",
    }:
        return Importance.NOTABLE
    if _NOTABLE.search(text):
        return Importance.NOTABLE
    if areas & {"Backend", "GPU", "Frontend"} and len(story.paths) >= 3:
        return Importance.NOTABLE
    return Importance.OTHER
