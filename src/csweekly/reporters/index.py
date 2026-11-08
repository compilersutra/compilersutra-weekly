# SPDX-License-Identifier: Apache-2.0
"""Archive index + navigable GitHub Pages site."""

from __future__ import annotations

import html
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from csweekly.brand import EDU_URL, PAGES_URL, PROJECT_NAME, REPO_URL
from csweekly.reporters.mdhtml import markdown_to_html

BUCKETS = [
    ("CPU", "LLVM, GCC"),
    ("IR / infra", "MLIR"),
    ("GPU", "Open source only"),
    ("AI / DL", "TVM, IREE, Triton…"),
    ("Research", "arXiv"),
]


@dataclass
class IssueMeta:
    path: Path
    date: str
    window: str
    href_html: str


def list_issues(reports_dir: Path) -> list[Path]:
    files = sorted(reports_dir.glob("**/*.md"), reverse=True)
    return [p for p in files if p.name != "README.md" and p.parent.name != "archive"]


def write_archive_index(reports_dir: Path, site_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    issues_md = list_issues(reports_dir)

    # Markdown archive (for git readers)
    lines = [
        f"# {PROJECT_NAME} — Archive",
        "",
        f"Site: [{PAGES_URL}]({PAGES_URL}) · Source: [{REPO_URL}]({REPO_URL})",
        "",
        "Reporting window: **Friday→Friday (UTC)** · Publish: **Saturday**.",
        "",
        "| Issue | Window |",
        "| --- | --- |",
    ]
    metas: list[IssueMeta] = []
    for path in issues_md:
        rel = path.relative_to(reports_dir).as_posix()
        window = _window_from_file(path) or "—"
        stem = path.stem
        lines.append(f"| [{stem}]({rel}) | {window} |")
        year = path.parent.name
        metas.append(
            IssueMeta(
                path=path,
                date=stem,
                window=window,
                href_html=f"issues/{year}/{stem}.html",
            )
        )
    lines.extend(
        [
            "",
            f"Education: [{EDU_URL}]({EDU_URL}) (external link only).",
            "",
        ]
    )
    archive = reports_dir / "README.md"
    archive.write_text("\n".join(lines), encoding="utf-8")

    # Build site/
    assets_src = Path(__file__).resolve().parent / "static"
    if (site_dir / "reports").exists():
        shutil.rmtree(site_dir / "reports")
    if (site_dir / "issues").exists():
        shutil.rmtree(site_dir / "issues")
    site_dir.mkdir(parents=True, exist_ok=True)
    assets_dst = site_dir / "assets"
    if assets_src.is_dir():
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)
    shutil.copytree(reports_dir, site_dir / "reports", dirs_exist_ok=True)

    latest = metas[0] if metas else None
    (site_dir / "index.html").write_text(
        _page_home(metas, latest), encoding="utf-8"
    )
    (site_dir / "archive.html").write_text(_page_archive(metas), encoding="utf-8")
    (site_dir / "about.html").write_text(_page_about(), encoding="utf-8")

    for meta in metas:
        out = site_dir / "issues" / meta.path.parent.name / f"{meta.date}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        md = meta.path.read_text(encoding="utf-8")
        out.write_text(_page_issue(meta, md), encoding="utf-8")

    (site_dir / "index.md").write_text(
        f"# {PROJECT_NAME}\n\nOpen [{PAGES_URL}]({PAGES_URL}) or the HTML `index.html`.\n",
        encoding="utf-8",
    )
    return archive


def _page_home(metas: list[IssueMeta], latest: IssueMeta | None) -> str:
    buckets = "\n".join(
        f'<div class="bucket"><strong>{html.escape(a)}</strong><span>{html.escape(b)}</span></div>'
        for a, b in BUCKETS
    )
    latest_cta = (
        f'<a class="btn btn-primary" href="{html.escape(latest.href_html)}">Read latest issue →</a>'
        if latest
        else ""
    )
    recent = metas[:6]
    items = "\n".join(
        f"""<li>
          <span class="issue-date">{html.escape(m.date)}</span>
          <a class="title" href="{html.escape(m.href_html)}">Weekly issue</a>
          <span class="issue-window">{html.escape(m.window)}</span>
        </li>"""
        for m in recent
    )
    body = f"""
  <main>
    <section class="hero">
      <div class="wrap">
        <p class="hero-kicker">Compiler ecosystem intelligence</p>
        <h1>CompilerSutra Weekly</h1>
        <p class="lede">What landed in open compilers this week — CPU, MLIR, GPU, and AI/DL stacks — with source links. Fri→Fri window, Saturday publish.</p>
        <div class="cta-row">
          {latest_cta}
          <a class="btn btn-ghost" href="archive.html">Browse archive</a>
          <a class="btn btn-ghost" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">View source</a>
        </div>
        <div class="meta-strip">
          <span>Window: Friday → Friday (UTC)</span>
          <span>Publish: Saturday</span>
          <span>Hosted on GitHub Pages</span>
        </div>
      </div>
    </section>
    <div class="wrap">
      <div class="buckets">{buckets}</div>
      <section class="panel" aria-labelledby="recent-heading">
        <h2 id="recent-heading">Recent issues</h2>
        <ul class="issue-list">
          {items or "<li><span class=\"issue-window\">No issues yet.</span></li>"}
        </ul>
      </section>
    </div>
  </main>
"""
    # Fix broken brand href generation from earlier draft
    page = _shell_fixed("CompilerSutra Weekly", body, active="home", depth=0)
    return page


def _page_archive(metas: list[IssueMeta]) -> str:
    items = "\n".join(
        f"""<li>
          <span class="issue-date">{html.escape(m.date)}</span>
          <a class="title" href="{html.escape(m.href_html)}">Weekly issue</a>
          <span class="issue-window">{html.escape(m.window)}</span>
        </li>"""
        for m in metas
    )
    body = f"""
  <main class="wrap" style="padding:2.5rem 0 3rem">
    <p class="hero-kicker">Archive</p>
    <h1 style="font-family:var(--font-display);font-size:clamp(2rem,4vw,2.8rem);margin:0 0 0.5rem">All issues</h1>
    <p style="color:var(--muted);max-width:36rem">Each Saturday issue covers the prior Friday→Friday window. Open an issue to jump to CPU, MLIR, GPU, AI, and research sections.</p>
    <section class="panel" style="margin-top:1.5rem">
      <ul class="issue-list">{items or "<li>No issues yet.</li>"}</ul>
    </section>
  </main>
"""
    return _shell_fixed("Archive — CompilerSutra Weekly", body, active="archive", depth=0)


def _page_about() -> str:
    body = f"""
  <main class="wrap" style="padding:2.5rem 0 3rem;max-width:42rem">
    <p class="hero-kicker">About</p>
    <h1 style="font-family:var(--font-display);font-size:clamp(2rem,4vw,2.8rem)">Independent by design</h1>
    <p style="color:var(--muted)">CompilerSutra Weekly tracks open compiler ecosystems. It is <strong style="color:var(--ink)">not</strong> part of the CompilerSutra Vercel/Docusaurus runtime — this site is static GitHub Pages.</p>
    <ul style="color:var(--muted)">
      <li><strong style="color:var(--ink)">CPU</strong> — LLVM, GCC</li>
      <li><strong style="color:var(--ink)">IR / infra</strong> — MLIR</li>
      <li><strong style="color:var(--ink)">GPU</strong> — open source only (proprietary CUDA out of scope)</li>
      <li><strong style="color:var(--ink)">AI / DL</strong> — TVM, IREE, Triton, …</li>
      <li><strong style="color:var(--ink)">Research</strong> — arXiv</li>
    </ul>
    <div class="cta-row" style="margin-top:1.5rem">
      <a class="btn btn-primary" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub repository</a>
      <a class="btn btn-ghost" href="{html.escape(EDU_URL)}" rel="noopener noreferrer">CompilerSutra.com</a>
      <a class="btn btn-ghost" href="{html.escape(PAGES_URL)}">This Pages site</a>
    </div>
  </main>
"""
    return _shell_fixed("About — CompilerSutra Weekly", body, active="about", depth=0)


def _page_issue(meta: IssueMeta, md: str) -> str:
    content = markdown_to_html(md)
    # simple toc from h2 ids
    toc_links = []
    for m in re.finditer(r'<h2 id="([^"]+)">([^<]+)</h2>', content):
        toc_links.append(
            f'<a href="#{html.escape(m.group(1))}">{html.escape(m.group(2))}</a>'
        )
    toc = f'<nav class="toc" aria-label="On this page">{"".join(toc_links)}</nav>' if toc_links else ""
    body = f"""
  <article class="article">
    <a class="back" href="../../archive.html">← Archive</a>
    {toc}
    {content}
  </article>
"""
    return _shell_fixed(f"{meta.date} — CompilerSutra Weekly", body, active="archive", depth=2)


def _shell_fixed(title: str, body: str, *, active: str, depth: int) -> str:
    prefix = "assets" if depth == 0 else "../" * depth + "assets"
    home = "index.html" if depth == 0 else "../" * depth + "index.html"
    archive = "archive.html" if depth == 0 else "../" * depth + "archive.html"
    about = "about.html" if depth == 0 else "../" * depth + "about.html"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <meta name="description" content="Compiler ecosystem intelligence — CPU, MLIR, open GPU, AI/DL compilers, research."/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Mono:wght@400;500&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="{prefix}/site.css"/>
</head>
<body>
  <header class="site-header">
    <div class="wrap">
      <a class="brand" href="{home}">CompilerSutra <span>Weekly</span></a>
      <nav class="nav" aria-label="Primary">
        <a href="{home}"{" aria-current=\"page\"" if active=="home" else ""}>Home</a>
        <a href="{archive}"{" aria-current=\"page\"" if active=="archive" else ""}>Archive</a>
        <a href="{about}"{" aria-current=\"page\"" if active=="about" else ""}>About</a>
        <a class="pill" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub</a>
        <a class="pill" href="{html.escape(EDU_URL)}" rel="noopener noreferrer">CompilerSutra</a>
      </nav>
    </div>
  </header>
  {body}
  <footer class="site-footer">
    <div class="wrap">
      <div>© CompilerSutra · Apache-2.0 · Pages + GitHub; education site links out only</div>
      <div>
        <a href="{html.escape(PAGES_URL)}">Pages</a> ·
        <a href="{html.escape(REPO_URL)}">Source</a> ·
        <a href="{html.escape(EDU_URL)}">Learn</a>
      </div>
    </div>
  </footer>
</body>
</html>
"""


def _window_from_file(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")[:800]
    m = re.search(r"\*\*Reporting window:\*\*\s*([^\n]+)", text)
    return m.group(1).strip() if m else None
