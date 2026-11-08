# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from csweekly.reporters.index import write_archive_index


def test_write_archive_index(tmp_path: Path):
    reports = tmp_path / "reports"
    year = reports / "2026"
    year.mkdir(parents=True)
    (year / "2026-11-07.md").write_text(
        "# Issue\n\n**Reporting window:** 2026-10-30 → 2026-11-06 (UTC)\n\n## CPU compilers (LLVM, GCC)\n\n- **hi**\n",
        encoding="utf-8",
    )
    # seed assets like repo layout
    assets = Path(__file__).resolve().parents[1] / "site" / "assets"
    site = tmp_path / "site"
    if assets.is_dir():
        import shutil
        (site / "assets").parent.mkdir(parents=True, exist_ok=True)
    archive = write_archive_index(reports, site)
    assert archive.is_file()
    assert (site / "index.html").is_file()
    assert (site / "archive.html").is_file()
    assert (site / "about.html").is_file()
    assert (site / "issues" / "2026" / "2026-11-07.html").is_file()
    html = (site / "index.html").read_text(encoding="utf-8")
    assert "CompilerSutra" in html
    assert "Archive" in html
    assert "compilersutra/compilersutra-weekly" in html
