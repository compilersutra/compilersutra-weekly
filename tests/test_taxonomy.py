# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from datetime import datetime, timezone

from csweekly.config import load_sources
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
        Story(
            id="1",
            title="clang change",
            source_url="https://example.com/1",
            source_org="LLVM",
            category="llvm",
            project="llvm",
            published_at=now,
            discovered_at=now,
            evidence_kind=EvidenceKind.GIT_COMMIT,
            summary="clang change",
            paths=["clang/lib/Sema/Sema.cpp"],
        ),
        Story(
            id="2",
            title="tvm change",
            source_url="https://example.com/2",
            source_org="TVM",
            category="ai",
            project="tvm",
            published_at=now,
            discovered_at=now,
            evidence_kind=EvidenceKind.GIT_COMMIT,
            summary="tvm change",
            paths=["src/relay/op/nn.cc"],
        ),
    ]
    md = render_markdown(build_issue(window, stories))
    assert "LLVM" in md
    assert "AI Compilers" in md
    assert "What changed in compilers this week" in md
    assert any(h == "LLVM" for h, _ in SECTION_ORDER)
