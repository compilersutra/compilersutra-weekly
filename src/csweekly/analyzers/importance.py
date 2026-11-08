# SPDX-License-Identifier: Apache-2.0
"""Explainable importance — never invent impact."""

from __future__ import annotations

import re

from csweekly.models import Importance, Story

_HIGHLIGHT = re.compile(
    r"\b(implement|introduce|add support|new backend|landed|release|security|"
    r"CVE|ABI break|new pass|GlobalISel|vectoriz|performance)\b",
    re.I,
)
_NOTABLE = re.compile(
    r"\b(fix|improve|optimize|refactor|enable|extend|migrate|rewrite)\b",
    re.I,
)
_DOCS_TEST = re.compile(r"\b(docs?|documentation|typo|nfc|test only|update tests)\b", re.I)


def assign_importance(story: Story) -> Importance:
    if story.evidence_kind.value in {"github_release"}:
        return Importance.HIGHLIGHT
    text = f"{story.title}\n{story.summary}"
    areas = set(story.areas)
    if _DOCS_TEST.search(text) and areas <= {"Documentation", "Testing", "Other"}:
        return Importance.OTHER
    if _HIGHLIGHT.search(text) or areas & {
        "Backend",
        "GPU",
        "Instruction selection",
        "Vectorization",
        "MLIR dialects",
        "IR",
    }:
        if _HIGHLIGHT.search(text):
            return Importance.HIGHLIGHT
        return Importance.NOTABLE
    if _NOTABLE.search(text) or len(story.paths) >= 8:
        return Importance.NOTABLE
    return Importance.OTHER
