# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timezone
from pathlib import Path

from csweekly.ai.evidence import EvidencePack, CommitEvidence, build_evidence_pack
from csweekly.ai.factcheck import factcheck_deterministic
from csweekly.ai.writer import write_deterministic, EditorialDraft
from csweekly.models import ChangeGroup, EvidenceKind, Story


def _story(sha: str, paths: list[str]) -> Story:
    return Story(
        id=f"gcc:{sha}",
        title="RISC-V: Extract subvectors via vec_perm_const",
        source_url=f"https://example.com/{sha}",
        source_org="GCC",
        category="gcc",
        project="GCC",
        discovered_at=datetime.now(timezone.utc),
        evidence_kind=EvidenceKind.GIT_COMMIT,
        summary="RISC-V: Extract subvectors via vec_perm_const",
        related_ref=sha,
        paths=paths,
    )


def test_deterministic_writer_uses_commit_body_not_title_only():
    pack = EvidencePack(
        story_id="t1",
        title_hint="short",
        stages=["Backend"],
        domains=["CPU"],
        hardware_targets=["RISC-V"],
        related_shas=["abc"],
        primary=CommitEvidence(
            sha="abc123",
            subject="RISC-V: Extract subvectors via vec_perm_const",
            body=(
                "This patch adds a const-perm recognizer for subvector extractions.\n\n"
                "With that, we can remove special cases and rely on generic handling."
            ),
            files=["gcc/config/riscv/riscv-v.cc", "gcc/testsuite/gcc.target/riscv/x.c"],
            additions=10,
            deletions=20,
            functions=["expand_vec_perm_const", "shuffle_extract_patterns"],
            tests=["gcc/testsuite/gcc.target/riscv/x.c"],
            diff_excerpt="@@ expand_vec_perm_const @@\n+shuffle_extract_patterns();\n",
        ),
    )
    draft = write_deterministic(pack, level="deep_dive")
    assert "const-perm" in draft.what_changed or "subvector" in draft.what_changed
    assert "riscv-v.cc" in draft.technical_implementation
    assert "Not established" in draft.performance_impact
    assert draft.writer == "deterministic"


def test_factcheck_rejects_perf_without_benchmark():
    pack = EvidencePack(
        story_id="t2",
        title_hint="x",
        primary=CommitEvidence(
            sha="deadbeef",
            subject="tweak",
            body="cleanup",
            files=["a.cpp"],
        ),
    )
    draft = EditorialDraft(
        title="tweak",
        what_changed="cleanup",
        why_it_matters="Makes the compiler 20% faster",
        performance_impact="20% faster on SPECint",
    )
    check = factcheck_deterministic(draft, pack)
    assert check.ok is False
    assert check.performance_claims_ok is False


def test_build_evidence_from_gcc_mirror():
    mirrors = Path("data/mirrors")
    if not (mirrors / "gcc").exists():
        return
    sha = "8ce5e39048138fb92ebebc4a72114d9e55fa7a91"
    group = ChangeGroup(
        id="g1",
        title="Extract subvectors",
        category="gcc",
        project="GCC",
        stories=[
            _story(
                sha,
                [
                    "gcc/config/riscv/riscv-v.cc",
                    "gcc/config/riscv/autovec.md",
                ],
            )
        ],
        stages=["Backend"],
        domains=["CPU"],
        hardware_targets=["RISC-V"],
    )
    pack = build_evidence_pack(group, mirrors)
    assert pack.primary is not None
    assert pack.primary.subject
    assert any("riscv" in f for f in pack.primary.files)
