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

## LLVM

**clang tweak**

fact about clang

[`abc123`](https://example.com/1)

## Research papers

- **paper**
  - [Paper](https://arxiv.org/abs/1)
""",
        encoding="utf-8",
    )
    site = tmp_path / "site"
    archive = write_archive_index(reports, site)
    assert archive.is_file()
    assert (site / "index.html").is_file()
    assert (site / "changelog.html").is_file()
    assert (site / "topics" / "llvm.html").is_file()
    assert (site / "topics" / "research.html").is_file()
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "What changed in compilers this week" in home
    assert "Read latest issue" in home
    llvm = (site / "topics" / "llvm.html").read_text(encoding="utf-8")
    assert "clang tweak" in llvm
    research = (site / "topics" / "research.html").read_text(encoding="utf-8")
    assert "paper" in research
