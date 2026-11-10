# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from csweekly.reporters.index import write_archive_index


def test_write_archive_index(tmp_path: Path):
    reports = tmp_path / "reports"
    year = reports / "2026"
    year.mkdir(parents=True)
    (year / "2026-11-07.md").write_text(
        """# CompilerSutra Weekly — #001, November 7 2026

**Reporting period:** 2026-10-30 → 2026-11-06 (UTC)

## High signal

### 1. [LLVM] example

**What changed**
Something.

**Why it matters**
Because.

## LLVM

- item
""",
        encoding="utf-8",
    )
    site = tmp_path / "site"
    archive = write_archive_index(reports, site)
    assert archive.is_file()
    assert (site / "index.html").is_file()
    assert (site / "explore" / "index.html").is_file()
    assert (site / "topics" / "llvm.html").is_file()
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "compiler changes worth knowing this week" in home.lower()
    assert "Read this week" in home or "Read latest issue" in home
    assert ">Explore<" in home
    assert ">Topics<" in home
    assert ">Subscribe<" in home
    assert "Explore by engineering domain" in home
    assert "theme-toggle" in home
    assert "data-theme" in home
    assert 'type="application/atom+xml"' in home
    assert (site / "assets" / "theme.js").is_file()
    assert (site / "assets" / "site.css").is_file()
    assert (site / "assets" / "filters.js").is_file()
    assert (site / "feed.xml").is_file()
    feed = (site / "feed.xml").read_text(encoding="utf-8")
    assert "<feed" in feed and "CompilerSutra Weekly" in feed
    about = (site / "about.html").read_text(encoding="utf-8")
    assert "Selection and" in about or "high signal" in about.lower()
    assert "Cadence" in about
    changelog = (site / "changelog.html").read_text(encoding="utf-8")
    assert "changelog-list" in changelog
    explore = (site / "explore" / "index.html").read_text(encoding="utf-8")
    assert "filters.js" in explore
    assert ">Explore<" in explore
