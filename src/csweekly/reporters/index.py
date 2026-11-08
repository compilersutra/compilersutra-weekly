# SPDX-License-Identifier: Apache-2.0
"""Archive index + lightweight GitHub Pages site."""

from __future__ import annotations

import re
import shutil
from pathlib import Path


def list_issues(reports_dir: Path) -> list[Path]:
    files = sorted(reports_dir.glob("**/*.md"), reverse=True)
    return [p for p in files if p.name != "README.md" and p.parent.name != "archive"]


def write_archive_index(reports_dir: Path, site_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    issues = list_issues(reports_dir)
    lines = [
        "# CompilerSutra Weekly — Archive",
        "",
        "Independent compiler ecosystem intelligence. Reporting window: **Friday→Friday (UTC)**; publish day: **Saturday**.",
        "",
        "| Issue | Window (from masthead) |",
        "| --- | --- |",
    ]
    for path in issues:
        rel = path.relative_to(reports_dir).as_posix()
        window = _window_from_file(path) or "—"
        lines.append(f"| [{path.stem}]({rel}) | {window} |")
    lines.extend(
        [
            "",
            "Source: [compilersutra-weekly](https://github.com/aabhinavg1/compilersutra-weekly).",
            "Education site: [compilersutra.com](https://www.compilersutra.com/) (links out only).",
            "",
        ]
    )
    archive = reports_dir / "README.md"
    archive.write_text("\n".join(lines), encoding="utf-8")

    # Static site copy for GitHub Pages
    site_dir.mkdir(parents=True, exist_ok=True)
    if (site_dir / "reports").exists():
        shutil.rmtree(site_dir / "reports")
    shutil.copytree(reports_dir, site_dir / "reports", dirs_exist_ok=True)
    index = site_dir / "index.md"
    index.write_text(
        "\n".join(
            [
                "# CompilerSutra Weekly",
                "",
                "Open-source compiler ecosystem intelligence (LLVM, MLIR, GCC, TVM, GPU compilers, research).",
                "",
                "- [Issue archive](reports/)",
                "- [Source repository](https://github.com/aabhinavg1/compilersutra-weekly)",
                "",
                "Schedule: collect Fri→Fri (UTC), publish Saturday.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    # GitHub Pages can render markdown with relative links if using docs/ or md plugins;
    # also write a simple HTML landing for zero-config Pages.
    (site_dir / "index.html").write_text(
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>CompilerSutra Weekly</title>
  <style>
    :root { color-scheme: light dark; }
    body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem auto; max-width: 52rem; line-height: 1.5; padding: 0 1rem; }
    a { color: inherit; }
    code { font-size: 0.95em; }
  </style>
</head>
<body>
  <h1>CompilerSutra Weekly</h1>
  <p>Open-source compiler ecosystem intelligence. Friday→Friday (UTC) window, Saturday publish.</p>
  <ul>
    <li><a href="reports/">Issue archive</a></li>
    <li><a href="https://github.com/aabhinavg1/compilersutra-weekly">Source repository</a></li>
    <li><a href="https://www.compilersutra.com/">CompilerSutra</a> (education site — external link only)</li>
  </ul>
</body>
</html>
""",
        encoding="utf-8",
    )
    return archive


def _window_from_file(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")[:800]
    m = re.search(r"\*\*Reporting window:\*\*\s*([^\n]+)", text)
    return m.group(1).strip() if m else None
