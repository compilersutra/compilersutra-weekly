# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timezone

from csweekly.analyzers.taxonomy import classify_dimensions
from csweekly.models import EvidenceKind, Story
from csweekly.reporters.taxonomy_ui import format_issue_date, taxonomy_badges_html


def test_format_issue_date_clean():
    assert format_issue_date("2026-11-07") == "7 Nov 2026"
    assert "&#" not in format_issue_date("2026-11-07")


def test_badges_have_dimension_labels():
    html = taxonomy_badges_html(
        {
            "project": "GCC",
            "stages": ["Backend"],
            "domains": ["CPU"],
            "hardware_targets": ["RISC-V"],
        }
    )
    assert "tax-project" in html
    assert "tax-stage" in html
    assert "tax-domain" in html
    assert "tax-target" in html
    assert "BackendBackend" not in html.replace(" ", "")


def test_frontend_not_forced_cpu():
    story = Story(
        id="x",
        title="[CIR] matrix splat",
        source_url="https://example.com",
        source_org="LLVM",
        category="llvm",
        project="llvm",
        discovered_at=datetime.now(timezone.utc),
        evidence_kind=EvidenceKind.GIT_COMMIT,
        summary="matrix splat",
        paths=["clang/lib/CIR/CodeGen/CIRGenExprScalar.cpp"],
        areas=["Frontend"],
    )
    stages, domains, _, hw = classify_dimensions(story)
    assert "Frontend" in stages
    assert "CPU" not in domains
    assert "Languages" in domains or not domains
