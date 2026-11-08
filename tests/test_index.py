# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from csweekly.reporters.index import write_archive_index


def test_write_archive_index(tmp_path: Path):
    reports = tmp_path / "reports"
    year = reports / "2026"
    year.mkdir(parents=True)
    (year / "2026-11-07.md").write_text(
        "# Issue\n\n**Reporting window:** 2026-10-30 → 2026-11-06 (UTC)\n",
        encoding="utf-8",
    )
    site = tmp_path / "site"
    archive = write_archive_index(reports, site)
    assert archive.is_file()
    assert "2026-11-07" in archive.read_text(encoding="utf-8")
    assert (site / "index.html").is_file()
    assert (site / "reports" / "2026" / "2026-11-07.md").is_file()
