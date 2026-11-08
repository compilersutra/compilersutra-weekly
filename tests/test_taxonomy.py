# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from csweekly.config import load_sources
from csweekly.reporters.markdown import SECTION_GROUPS, build_issue, render_markdown
from csweekly.models import EvidenceKind, Story, Window
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def test_ai_sources_use_ai_category():
    sources = {s.id: s for s in load_sources(ROOT / "sources")}
    for sid in ("tvm", "iree", "triton", "tvm-releases"):
        assert sources[sid].category == "ai"


def test_report_groups_cpu_and_ai():
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
            published_at=now,
            discovered_at=now,
            evidence_kind=EvidenceKind.GIT_COMMIT,
            summary="fact",
        ),
        Story(
            id="2",
            title="tvm change",
            source_url="https://example.com/2",
            source_org="TVM",
            category="ai",
            published_at=now,
            discovered_at=now,
            evidence_kind=EvidenceKind.GIT_COMMIT,
            summary="fact",
        ),
    ]
    md = render_markdown(build_issue(window, stories))
    assert "CPU compilers" in md
    assert "AI / DL compilers" in md
    assert "open source only" in md.lower() or "open source" in md.lower()
    assert any("CPU" in h for h, _ in SECTION_GROUPS)
