# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timezone

from csweekly.analyzers.areas import classify_areas
from csweekly.analyzers.importance import assign_importance
from csweekly.models import EvidenceKind, Importance, Story
from csweekly.processors.editorial import (
    editorial_sentence,
    select_for_newsletter,
)
from csweekly.processors.group import group_stories
from csweekly.models import ChangeGroup

UTC = timezone.utc


def _story(i: str, title: str, paths: list[str], cat: str = "llvm") -> Story:
    now = datetime(2026, 11, 5, tzinfo=UTC)
    s = Story(
        id=i,
        title=title,
        source_url=f"https://example.com/{i}",
        source_org="LLVM",
        category=cat,
        project=cat,
        published_at=now,
        discovered_at=now,
        evidence_kind=EvidenceKind.GIT_COMMIT,
        summary=title,
        paths=paths,
        related_ref=i * 8,
    )
    s.areas = classify_areas(paths, title)
    s.importance = assign_importance(s)
    return s


def test_classify_areas_from_paths():
    areas = classify_areas(["llvm/lib/CodeGen/GlobalISel/Legalizer.cpp"], "Legalizer")
    assert "Instruction selection" in areas


def test_group_related_amdgpu():
    stories = [
        _story("a", "[AMDGPU] Fix prefetch length", ["llvm/lib/Target/AMDGPU/AMDGPU.h"]),
        _story("b", "[AMDGPU] Fix prefetch policy", ["llvm/lib/Target/AMDGPU/AMDGPU.cpp"]),
    ]
    groups = group_stories(stories)
    assert len(groups) == 1
    assert len(groups[0].stories) == 2


def test_select_prefers_highlights():
    from csweekly.processors.explain import explain_group

    stories = [
        _story("1", "Add support for new backend", ["llvm/lib/Target/Foo/Foo.cpp"]),
        _story("2", "typo in docs", ["docs/Foo.rst"]),
    ]
    for s in stories:
        s.importance = assign_importance(s)
    groups = [explain_group(g) for g in group_stories(stories)]
    selected = select_for_newsletter(groups)
    assert selected
    assert selected[0].signal.value in {"high_signal", "worth_knowing", "deep_dive"}


def test_editorial_sentence_reads_like_newsletter():
    s = _story(
        "x",
        "[AMDGPU][GlobalISel] Fold unmasked signed byte loads into D16 high loads (#236136)",
        ["llvm/lib/Target/AMDGPU/AMDGPUInstructionSelector.cpp"],
    )
    g = ChangeGroup(
        id="g",
        title=s.title,
        category="llvm",
        project="llvm",
        areas=s.areas,
        importance=s.importance,
        stories=[s],
    )
    sentence = editorial_sentence(g)
    assert sentence.endswith(".")
    assert "Fold" in sentence or "fold" in sentence.lower() or "AMDGPU" in sentence
    assert "(#236136)" not in sentence


def test_explain_has_why_and_who():
    from csweekly.pipeline import enrich_story
    s = enrich_story(_story(
        "z",
        "[AMDGPU][GlobalISel] Fold unmasked signed byte loads",
        ["llvm/lib/Target/AMDGPU/AMDGPUInstructionSelector.cpp"],
    ))
    assert s.what_changed
    assert s.why_it_matters
    assert s.who_should_care
    assert s.stages
    assert s.domains
