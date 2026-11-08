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

# Modular topic modules — each is a first-class page
TOPICS: list[dict[str, str]] = [
    {
        "id": "cpu",
        "label": "CPU",
        "blurb": "LLVM, GCC",
        "heading": "CPU compilers (LLVM, GCC)",
        "anchor": "cpu-compilers-llvm-gcc",
    },
    {
        "id": "mlir",
        "label": "IR / infra",
        "blurb": "MLIR",
        "heading": "IR & compiler infra (MLIR)",
        "anchor": "ir-compiler-infra-mlir",
    },
    {
        "id": "gpu",
        "label": "GPU",
        "blurb": "Open source only",
        "heading": "GPU compilers (open source)",
        "anchor": "gpu-compilers-open-source",
    },
    {
        "id": "ai",
        "label": "AI / DL",
        "blurb": "TVM, IREE, Triton…",
        "heading": "AI / DL compilers",
        "anchor": "ai-dl-compilers",
    },
    {
        "id": "research",
        "label": "Research",
        "blurb": "arXiv",
        "heading": "Research papers",
        "anchor": "research-papers",
    },
]


@dataclass
class IssueMeta:
    path: Path
    date: str
    window: str
    href_html: str
    md: str = ""


def list_issues(reports_dir: Path) -> list[Path]:
    files = sorted(reports_dir.glob("**/*.md"), reverse=True)
    return [p for p in files if p.name != "README.md" and p.parent.name != "archive"]


def write_archive_index(reports_dir: Path, site_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    issues_md = list_issues(reports_dir)

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
        md = path.read_text(encoding="utf-8")
        lines.append(f"| [{stem}]({rel}) | {window} |")
        year = path.parent.name
        metas.append(
            IssueMeta(
                path=path,
                date=stem,
                window=window,
                href_html=f"issues/{year}/{stem}.html",
                md=md,
            )
        )
    lines.extend(["", f"Education: [{EDU_URL}]({EDU_URL}) (external link only).", ""])
    archive = reports_dir / "README.md"
    archive.write_text("\n".join(lines), encoding="utf-8")

    assets_src = Path(__file__).resolve().parent / "static"
    for name in ("reports", "issues", "topics"):
        target = site_dir / name
        if target.exists():
            shutil.rmtree(target)
    site_dir.mkdir(parents=True, exist_ok=True)
    assets_dst = site_dir / "assets"
    if assets_src.is_dir():
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)
    shutil.copytree(reports_dir, site_dir / "reports", dirs_exist_ok=True)

    latest = metas[0] if metas else None
    (site_dir / "index.html").write_text(_page_home(metas, latest), encoding="utf-8")
    (site_dir / "archive.html").write_text(_page_archive(metas), encoding="utf-8")
    (site_dir / "about.html").write_text(_page_about(), encoding="utf-8")
    (site_dir / "topics").mkdir(parents=True, exist_ok=True)
    (site_dir / "topics" / "index.html").write_text(_page_topics_hub(), encoding="utf-8")
    for topic in TOPICS:
        (site_dir / "topics" / f"{topic['id']}.html").write_text(
            _page_topic(topic, metas), encoding="utf-8"
        )

    for meta in metas:
        out = site_dir / "issues" / meta.path.parent.name / f"{meta.date}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_page_issue(meta, meta.md), encoding="utf-8")

    (site_dir / "index.md").write_text(
        f"# {PROJECT_NAME}\n\nOpen [{PAGES_URL}]({PAGES_URL}).\n",
        encoding="utf-8",
    )
    return archive


def _topic_bar(active: str = "", *, depth: int = 0) -> str:
    prefix = "" if depth == 0 else "../" * depth
    links = []
    for t in TOPICS:
        href = f"{prefix}topics/{t['id']}.html"
        cur = ' aria-current="page"' if active == t["id"] else ""
        links.append(f'<a href="{href}"{cur}>{html.escape(t["label"])}</a>')
    hub = f'{prefix}topics/index.html'
    hub_cur = ' aria-current="page"' if active == "topics" else ""
    return f"""
  <div class="topic-bar">
    <div class="wrap" aria-label="Topics">
      <a href="{hub}"{hub_cur}>All topics</a>
      {''.join(links)}
    </div>
  </div>
"""


def _page_home(metas: list[IssueMeta], latest: IssueMeta | None) -> str:
    buckets = "\n".join(
        f"""<a class="bucket" href="topics/{html.escape(t['id'])}.html">
  <strong>{html.escape(t['label'])}</strong>
  <span>{html.escape(t['blurb'])}</span>
  <span class="go">Open topic →</span>
</a>"""
        for t in TOPICS
    )
    latest_cta = (
        f'<a class="btn btn-primary" href="{html.escape(latest.href_html)}">Read latest issue →</a>'
        if latest
        else ""
    )
    items = _issue_rows(metas[:8], depth=0)
    body = f"""
  {_topic_bar(depth=0)}
  <main>
    <section class="hero">
      <div class="wrap">
        <p class="hero-kicker">Compiler ecosystem intelligence</p>
        <h1>CompilerSutra Weekly</h1>
        <p class="lede">Browse by topic or open the Saturday issue. Fri→Fri window, source-backed links only.</p>
        <div class="cta-row">
          {latest_cta}
          <a class="btn btn-ghost" href="archive.html">Archive</a>
          <a class="btn btn-ghost" href="topics/index.html">Topics</a>
        </div>
        <div class="meta-strip">
          <span>Window: Friday → Friday (UTC)</span>
          <span>Publish: Saturday</span>
        </div>
      </div>
    </section>
    <div class="wrap">
      <h2 class="section-label">Browse by topic</h2>
      <div class="buckets">{buckets}</div>
      <section class="panel" aria-labelledby="recent-heading">
        <h2 id="recent-heading">Recent issues</h2>
        <ul class="issue-list">{items if items else '<li class="topic-empty">No issues yet.</li>'}</ul>
      </section>
    </div>
  </main>
"""
    return _shell("CompilerSutra Weekly", body, active="home", depth=0)


def _page_archive(metas: list[IssueMeta]) -> str:
    items = _issue_rows(metas, depth=0)
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap" style="padding:2.5rem 0 3rem">
    <p class="hero-kicker">Archive</p>
    <h1 style="font-family:var(--font-display);font-size:clamp(2rem,4vw,2.8rem);margin:0 0 0.5rem">All issues</h1>
    <p style="color:var(--muted);max-width:36rem">Click any row. Or jump a topic from the bar above.</p>
    <section class="panel" style="margin-top:1.5rem">
      <ul class="issue-list">{items or "<li>No issues yet.</li>"}</ul>
    </section>
  </main>
"""
    return _shell("Archive — CompilerSutra Weekly", body, active="archive", depth=0)


def _page_topics_hub() -> str:
    cards = "\n".join(
        f"""<a class="bucket" href="{html.escape(t['id'])}.html">
  <strong>{html.escape(t['label'])}</strong>
  <span>{html.escape(t['blurb'])}</span>
  <span class="go">Open →</span>
</a>"""
        for t in TOPICS
    )
    body = f"""
  {_topic_bar(active="topics", depth=1)}
  <main class="wrap" style="padding:2.5rem 0 3rem">
    <p class="hero-kicker">Topics</p>
    <h1 style="font-family:var(--font-display);font-size:clamp(2rem,4vw,2.8rem);margin:0 0 0.75rem">Five modules</h1>
    <p style="color:var(--muted);max-width:36rem;margin-bottom:1.5rem">Each topic pulls matching sections from Saturday issues. Proprietary CUDA stacks stay out of scope.</p>
    <div class="buckets">{cards}</div>
  </main>
"""
    return _shell("Topics — CompilerSutra Weekly", body, active="topics", depth=1)


def _page_topic(topic: dict[str, str], metas: list[IssueMeta]) -> str:
    blocks: list[str] = []
    for meta in metas:
        section_md = _extract_section(meta.md, topic["heading"])
        if not section_md:
            continue
        section_html = markdown_to_html(f"## {topic['heading']}\n\n{section_md}")
        deep = f"../{meta.href_html}#{topic['anchor']}"
        blocks.append(
            f"""<section class="topic-issue-block">
  <h3><a href="{html.escape(deep)}">{html.escape(meta.date)} · full issue</a></h3>
  <p style="color:var(--muted);font-size:0.9rem;margin:0 0 0.75rem">{html.escape(meta.window)}</p>
  <div class="article" style="padding:0;width:auto;margin:0">{section_html}</div>
</section>"""
        )
    content = (
        "\n".join(blocks)
        if blocks
        else '<p class="topic-empty">No stories in this topic for published issues yet. Check the latest Saturday issue or come back next week.</p>'
    )
    latest_link = ""
    if metas:
        latest_link = (
            f'<a class="btn btn-primary" href="../{html.escape(metas[0].href_html)}'
            f'#{html.escape(topic["anchor"])}">Jump in latest issue →</a>'
        )
    body = f"""
  {_topic_bar(active=topic["id"], depth=1)}
  <main class="wrap" style="padding:2.5rem 0 3rem">
    <p class="hero-kicker">Topic</p>
    <h1 style="font-family:var(--font-display);font-size:clamp(2rem,4vw,2.8rem);margin:0 0 0.35rem">{html.escape(topic["label"])}</h1>
    <p style="color:var(--muted);margin:0 0 1.25rem">{html.escape(topic["blurb"])} · {html.escape(topic["heading"])}</p>
    <div class="cta-row" style="margin-bottom:1.75rem">
      {latest_link}
      <a class="btn btn-ghost" href="index.html">All topics</a>
      <a class="btn btn-ghost" href="../archive.html">Archive</a>
    </div>
    {content}
  </main>
"""
    return _shell(
        f'{topic["label"]} — CompilerSutra Weekly',
        body,
        active="topics",
        depth=1,
    )


def _page_about() -> str:
    rows = "\n".join(
        f'<li><a href="topics/{html.escape(t["id"])}.html"><strong style="color:var(--ink)">{html.escape(t["label"])}</strong></a> — {html.escape(t["blurb"])}</li>'
        for t in TOPICS
    )
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap" style="padding:2.5rem 0 3rem;max-width:42rem">
    <p class="hero-kicker">About</p>
    <h1 style="font-family:var(--font-display);font-size:clamp(2rem,4vw,2.8rem)">Independent by design</h1>
    <p style="color:var(--muted)">Static GitHub Pages. CompilerSutra.com only links here — no research workers on Vercel.</p>
    <ul style="color:var(--muted)">{rows}</ul>
    <div class="cta-row" style="margin-top:1.5rem">
      <a class="btn btn-primary" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub</a>
      <a class="btn btn-ghost" href="{html.escape(EDU_URL)}" rel="noopener noreferrer">CompilerSutra.com</a>
      <a class="btn btn-ghost" href="topics/index.html">Browse topics</a>
    </div>
  </main>
"""
    return _shell("About — CompilerSutra Weekly", body, active="about", depth=0)


def _page_issue(meta: IssueMeta, md: str) -> str:
    content = markdown_to_html(md)
    toc_links = []
    for m in re.finditer(r'<h2 id="([^"]+)">([^<]+)</h2>', content):
        toc_links.append(
            f'<a href="#{html.escape(m.group(1))}">{html.escape(m.group(2))}</a>'
        )
    # ensure topic chips for our five modules
    topic_chips = " ".join(
        f'<a href="../../topics/{html.escape(t["id"])}.html">{html.escape(t["label"])}</a>'
        for t in TOPICS
    )
    toc = (
        f'<nav class="toc" aria-label="On this page">{"".join(toc_links)}</nav>'
        if toc_links
        else ""
    )
    body = f"""
  {_topic_bar(depth=2)}
  <article class="article">
    <a class="back" href="../../archive.html">← Archive</a>
    <div class="toc" aria-label="Topics">{topic_chips}</div>
    {toc}
    {content}
  </article>
"""
    return _shell(f"{meta.date} — CompilerSutra Weekly", body, active="archive", depth=2)


def _issue_rows(metas: list[IssueMeta], *, depth: int) -> str:
    prefix = "" if depth == 0 else "../" * depth
    rows = []
    for m in metas:
        href = prefix + m.href_html if not m.href_html.startswith("../") else m.href_html
        rows.append(
            f"""<li>
  <a class="issue-row" href="{html.escape(href)}">
    <span class="issue-date">{html.escape(m.date)}</span>
    <span class="title">Weekly issue</span>
    <span class="issue-window">{html.escape(m.window)}</span>
  </a>
</li>"""
        )
    return "\n".join(rows)


def _extract_section(md: str, heading: str) -> str:
    """Return markdown body under ``## heading`` until next ##."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE
    )
    m = pattern.search(md)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^##\s+", md[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(md)
    return md[start:end].strip()


def _shell(title: str, body: str, *, active: str, depth: int) -> str:
    prefix = "assets" if depth == 0 else "../" * depth + "assets"
    home = "index.html" if depth == 0 else "../" * depth + "index.html"
    archive = "archive.html" if depth == 0 else "../" * depth + "archive.html"
    about = "about.html" if depth == 0 else "../" * depth + "about.html"
    topics = "topics/index.html" if depth == 0 else ("index.html" if depth == 1 else "../../topics/index.html")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <meta name="description" content="Compiler ecosystem intelligence — browse CPU, MLIR, GPU, AI/DL, research."/>
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
        <a href="{topics}"{" aria-current=\"page\"" if active=="topics" else ""}>Topics</a>
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
      <div>© CompilerSutra · Apache-2.0</div>
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
