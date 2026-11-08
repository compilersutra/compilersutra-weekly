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
    assert "worth understanding" in home.lower()
    assert "Read latest issue" in home
