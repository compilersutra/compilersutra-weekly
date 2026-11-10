# SPDX-License-Identifier: Apache-2.0
from datetime import date
from pathlib import Path

from csweekly.collectors.git_mirror import collect_git
from csweekly.config import SourceConfig
from csweekly.processors.dedupe import dedupe_stories
from csweekly.reporters.markdown import build_issue, render_markdown
from csweekly.window import friday_friday_window

FIX = Path(__file__).parent / "fixtures" / "tiny_repo"


def _source(**kwargs):
    base = dict(
        id="llvm",
        name="LLVM",
        org="LLVM Project",
        category="llvm",
        kind="git",
        url="https://github.com/llvm/llvm-project.git",
        github_repo="llvm/llvm-project",
        default_branch="main",
        max_commits=50,
    )
    base.update(kwargs)
    return SourceConfig.model_validate(base)


def test_collect_window_filters_old_commits():
    window = friday_friday_window(as_of=date(2026, 11, 5))
    result = collect_git(_source(), window, Path("data/mirrors"), fetch=False, repo_path=FIX)
    subjects = {s.raw["sha"] and s.summary for s in result.stories}
    text = " | ".join(s.summary for s in result.stories)
    assert "too old" not in text
    assert "improve Foo" in text
    assert len(result.stories) == 3


def test_mlir_path_filter():
    window = friday_friday_window(as_of=date(2026, 11, 5))
    result = collect_git(
        _source(id="mlir", category="mlir", path_prefixes=["mlir/"]),
        window,
        Path("data/mirrors"),
        fetch=False,
        repo_path=FIX,
    )
    assert len(result.stories) == 1
    assert "mlir" in result.stories[0].summary.lower() or "Ops" in result.stories[0].title


def test_dedupe_and_report():
    window = friday_friday_window(as_of=date(2026, 11, 5))
    a = collect_git(_source(), window, Path("."), fetch=False, repo_path=FIX)
    b = collect_git(_source(), window, Path("."), fetch=False, repo_path=FIX)
    merged = dedupe_stories(a.stories + b.stories)
    assert len(merged) == len(a.stories)
    issue = build_issue(window, merged)
    md = render_markdown(issue)
    assert "Reporting period" in md or "Reporting window" in md
    assert "2026-11-07" in md
