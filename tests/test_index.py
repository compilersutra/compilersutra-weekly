# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from csweekly.reporters.index import write_archive_index


def test_write_archive_index(tmp_path: Path):
    reports = tmp_path / "reports"
    year = reports / "2026"
    year.mkdir(parents=True)
    (year / "2026-11-07.md").write_text(
        """# Issue

**Reporting window:** 2026-10-30 → 2026-11-06 (UTC)

## CPU compilers (LLVM, GCC)

- **clang tweak**
  - Fact: hello

## Research papers

- **paper**
  - Fact: arxiv
""",
        encoding="utf-8",
    )
    site = tmp_path / "site"
    archive = write_archive_index(reports, site)
    assert archive.is_file()
    assert (site / "index.html").is_file()
    assert (site / "topics" / "cpu.html").is_file()
    assert (site / "topics" / "research.html").is_file()
    home = (site / "index.html").read_text(encoding="utf-8")
    assert 'href="topics/cpu.html"' in home
    assert "Open topic" in home
    cpu = (site / "topics" / "cpu.html").read_text(encoding="utf-8")
    assert "clang tweak" in cpu
    research = (site / "topics" / "research.html").read_text(encoding="utf-8")
    assert "paper" in research
