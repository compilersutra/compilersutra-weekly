# SPDX-License-Identifier: Apache-2.0
"""Phase 1 editorial quality gates."""

from csweekly.ai.evidence import CommitEvidence, EvidencePack
from csweekly.ai.factcheck import factcheck_deterministic
from csweekly.ai.writer import write_deterministic
from csweekly.reporters.taxonomy_ui import evidence_confidence


def _pack() -> EvidencePack:
    primary = CommitEvidence(
        sha="abcdef1234567890",
        subject="[RISCV] Add helper for FP ABI",
        body=(
            "Add helper functions for single/double FP ABI checks.\n\n"
            "Previously callers compared enum values by hand."
        ),
        files=["llvm/lib/Target/RISCV/RISCVISelLowering.cpp"],
        functions=["isFPABI"],
        tests=["llvm/test/CodeGen/RISCV/abi.ll"],
        additions=40,
        deletions=5,
        diff_excerpt="",
    )
    return EvidencePack(
        story_id="test-riscv-abi",
        title_hint=primary.subject,
        primary=primary,
        related=[],
        related_shas=[],
        stages=["Backend"],
        domains=["CPU"],
        hardware_targets=["RISC-V"],
        errors=[],
    )


def test_deterministic_why_differs_from_what():
    draft = write_deterministic(_pack(), level="engineering_analysis")
    assert draft.what_changed.strip()
    assert draft.why_it_matters.strip()
    assert draft.what_changed.strip().lower() != draft.why_it_matters.strip().lower()
    assert draft.confidence in {"high", "medium", "low"}
    check = factcheck_deterministic(draft, _pack())
    assert check.ok


def test_evidence_confidence_labels():
    label, slug = evidence_confidence(
        {
            "deep_dive_notes": {
                "confidence": "high",
                "factcheck": "pass",
                "validation": "Tests touched: foo.",
            }
        }
    )
    assert label == "Verified"
    assert slug == "verified"
    label2, slug2 = evidence_confidence({"deep_dive_notes": {}})
    assert label2 == "Unverified"
    assert slug2 == "unverified"
