# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from datetime import datetime, timezone

from csweekly.config import load_sources
from csweekly.pipeline import enrich_story
from csweekly.reporters.markdown import SECTION_ORDER, build_issue, render_markdown
from csweekly.models import EvidenceKind, Story, Window

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def test_ai_sources_use_ai_category():
    sources = {s.id: s for s in load_sources(ROOT / "sources")}
    for sid in ("tvm", "iree", "triton", "tvm-releases"):
        assert sources[sid].category == "ai"


def test_report_groups_llvm_and_ai():
    window = Window(
        start=datetime(2026, 10, 30, tzinfo=UTC),
        end=datetime(2026, 11, 6, tzinfo=UTC),
    )
    now = datetime(2026, 11, 5, tzinfo=UTC)
    stories = [
        enrich_story(
            Story(
                id="1",
                title="[Clang] Implement matrix splat cast",
                source_url="https://example.com/1",
                source_org="LLVM",
                category="llvm",
                project="llvm",
                published_at=now,
                discovered_at=now,
                evidence_kind=EvidenceKind.GIT_COMMIT,
                summary="Implement matrix splat cast",
                paths=["clang/lib/CodeGen/CGExpr.cpp"],
            )
        ),
        enrich_story(
            Story(
                id="2",
                title="Add support for new Triton GPU pass",
                source_url="https://example.com/2",
                source_org="TVM",
                category="ai",
                project="triton",
                published_at=now,
                discovered_at=now,
                evidence_kind=EvidenceKind.GIT_COMMIT,
                summary="Add support for new Triton GPU pass",
                paths=["lib/Conversion/TritonGPUToLLVM/Pass.cpp"],
            )
        ),
    ]
    issue = build_issue(window, stories)
    md = render_markdown(issue)
    assert "What changed" in md or "why it matters" in md.lower() or "Why it matters" in md
    assert "The compiler changes worth understanding" in md
    assert any(h[0] == "LLVM" for h in SECTION_ORDER)
