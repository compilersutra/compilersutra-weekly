# SPDX-License-Identifier: Apache-2.0
"""Archive index + navigable GitHub Pages site (newsletter publication)."""

from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from csweekly.brand import EDU_URL, PAGES_URL, PROJECT_NAME, REPO_URL
from csweekly.reporters.mdhtml import markdown_to_html

# Topic modules map to newsletter section headings (new + legacy)
TOPICS: list[dict[str, object]] = [
    {
        "id": "llvm",
        "label": "LLVM",
        "blurb": "Clang, backends, CodeGen",
        "headings": ["LLVM", "CPU compilers (LLVM, GCC)"],
        "anchor": "llvm",
    },
    {
        "id": "gcc",
        "label": "GCC",
        "blurb": "GIMPLE, RTL, targets",
        "headings": ["GCC"],
        "anchor": "gcc",
    },
    {
        "id": "mlir",
        "label": "MLIR",
        "blurb": "Dialects & infra",
        "headings": ["MLIR", "IR & compiler infra (MLIR)", "IR / infra"],
        "anchor": "mlir",
    },
    {
        "id": "ai",
        "label": "AI Compilers",
        "blurb": "Triton, XLA, IREE, TVM",
        "headings": ["AI Compilers", "AI / DL compilers"],
        "anchor": "ai-compilers",
    },
    {
        "id": "gpu",
        "label": "GPU",
        "blurb": "AMDGPU, ROCm, SPIR-V",
        "headings": ["GPU Compilers", "GPU compilers (open source)"],
        "anchor": "gpu-compilers",
    },
    {
        "id": "research",
        "label": "Research",
        "blurb": "Papers & notes",
        "headings": ["Research papers", "Research and New Developments"],
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
    issue_number: int | None = None
    stats: dict = field(default_factory=dict)


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
    chronological = sorted(issues_md, key=lambda p: p.stem)
    number_by_date = {p.stem: i + 1 for i, p in enumerate(chronological)}

    for path in issues_md:
        rel = path.relative_to(reports_dir).as_posix()
        window = _window_from_file(path) or "—"
        stem = path.stem
        md = path.read_text(encoding="utf-8")
        num = number_by_date.get(stem)
        label = f"#{num:03d}" if num else stem
        lines.append(f"| [{label} {stem}]({rel}) | {window} |")
        year = path.parent.name
        stats = _load_stats(path)
        metas.append(
            IssueMeta(
                path=path,
                date=stem,
                window=window,
                href_html=f"issues/{year}/{stem}.html",
                md=md,
                issue_number=num,
                stats=stats,
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
    (site_dir / "changelog.html").write_text(_page_changelog(metas), encoding="utf-8")
    (site_dir / "subscribe.html").write_text(_page_subscribe(), encoding="utf-8")
    (site_dir / "topics").mkdir(parents=True, exist_ok=True)
    (site_dir / "topics" / "index.html").write_text(_page_topics_hub(), encoding="utf-8")
    for topic in TOPICS:
        (site_dir / "topics" / f"{topic['id']}.html").write_text(
            _page_topic(topic, metas), encoding="utf-8"
        )

    for i, meta in enumerate(metas):
        prev_m = metas[i + 1] if i + 1 < len(metas) else None
        next_m = metas[i - 1] if i > 0 else None
        out = site_dir / "issues" / meta.path.parent.name / f"{meta.date}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_page_issue(meta, meta.md, prev_m, next_m), encoding="utf-8")

    (site_dir / "index.md").write_text(
        f"# {PROJECT_NAME}\n\nOpen [{PAGES_URL}]({PAGES_URL}).\n",
        encoding="utf-8",
    )
    return archive


def _load_stats(md_path: Path) -> dict:
    sibling = md_path.with_suffix(".changelog.json")
    # filename is YYYY-MM-DD.md → YYYY-MM-DD.changelog.json
    sibling = md_path.parent / f"{md_path.stem}.changelog.json"
    if not sibling.is_file():
        return {}
    try:
        data = json.loads(sibling.read_text(encoding="utf-8"))
        return data.get("stats") or {}
    except Exception:
        return {}


def _topic_bar(active: str = "", *, depth: int = 0) -> str:
    prefix = "" if depth == 0 else "../" * depth
    links = []
    for t in TOPICS:
        href = f"{prefix}topics/{t['id']}.html"
        cur = ' aria-current="page"' if active == t["id"] else ""
        links.append(f'<a href="{href}"{cur}>{html.escape(str(t["label"]))}</a>')
    hub = f"{prefix}topics/index.html"
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
    if latest:
        num = f"#{latest.issue_number:03d}" if latest.issue_number else latest.date
        projects = latest.stats.get("projects") or []
        proj_txt = " · ".join(html.escape(p) for p in projects[:6]) or "LLVM · GCC · MLIR · AI · GPU"
        latest_block = f"""
        <div class="latest-card">
          <p class="hero-kicker">Latest issue</p>
          <h2>Issue {html.escape(num)}</h2>
          <p class="latest-meta">{html.escape(latest.date)} · {html.escape(latest.window)}</p>
          <p class="latest-cover">{proj_txt}</p>
          <div class="cta-row">
            <a class="btn btn-primary" href="{html.escape(latest.href_html)}">Read latest issue →</a>
            <a class="btn btn-ghost" href="archive.html">Archive</a>
            <a class="btn btn-ghost" href="changelog.html">Complete change log</a>
          </div>
        </div>
"""
    else:
        latest_block = '<p class="topic-empty">No issues yet.</p>'

    items = _issue_rows(metas[:12], depth=0)
    body = f"""
  {_topic_bar(depth=0)}
  <main>
    <section class="hero">
      <div class="wrap">
        <h1>CompilerSutra Weekly</h1>
        <p class="tagline">What changed in compilers this week.</p>
        <p class="lede">LLVM · GCC · MLIR · AI Compilers · GPU Compilers · Toolchains · Research</p>
        {latest_block}
      </div>
    </section>
    <div class="wrap">
      <section class="panel" aria-labelledby="archive-heading">
        <h2 id="archive-heading">Previous issues</h2>
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
  <main class="wrap article-narrow">
    <p class="hero-kicker">Archive</p>
    <h1 class="page-title">All issues</h1>
    <p class="muted">Chronological newsletter archive. Each issue is a Saturday digest.</p>
    <section class="panel" style="margin-top:1.5rem">
      <ul class="issue-list">{items or "<li>No issues yet.</li>"}</ul>
    </section>
  </main>
"""
    return _shell("Archive — CompilerSutra Weekly", body, active="archive", depth=0)


def _page_topics_hub() -> str:
    cards = "\n".join(
        f"""<a class="bucket" href="{html.escape(str(t['id']))}.html">
  <strong>{html.escape(str(t['label']))}</strong>
  <span>{html.escape(str(t['blurb']))}</span>
  <span class="go">Open →</span>
</a>"""
        for t in TOPICS
    )
    body = f"""
  {_topic_bar(active="topics", depth=1)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">Topics</p>
    <h1 class="page-title">Browse by area</h1>
    <p class="muted">Jump into matching sections from published Saturday issues.</p>
    <div class="buckets">{cards}</div>
  </main>
"""
    return _shell("Topics — CompilerSutra Weekly", body, active="topics", depth=1)


def _page_topic(topic: dict[str, object], metas: list[IssueMeta]) -> str:
    headings = list(topic.get("headings") or [])
    blocks: list[str] = []
    for meta in metas:
        section_md = ""
        used = ""
        for h in headings:
            section_md = _extract_section(meta.md, str(h))
            if section_md:
                used = str(h)
                break
        if not section_md:
            continue
        section_html = markdown_to_html(f"## {used}\n\n{section_md}")
        deep = f"../{meta.href_html}"
        num = f"#{meta.issue_number:03d}" if meta.issue_number else meta.date
        blocks.append(
            f"""<section class="topic-issue-block">
  <h3><a href="{html.escape(deep)}">{html.escape(num)} · {html.escape(meta.date)}</a></h3>
  <p class="muted">{html.escape(meta.window)}</p>
  <div class="article" style="padding:0;width:auto;margin:0">{section_html}</div>
</section>"""
        )
    content = (
        "\n".join(blocks)
        if blocks
        else '<p class="topic-empty">No stories in this topic for published issues yet.</p>'
    )
    latest_link = ""
    if metas:
        latest_link = (
            f'<a class="btn btn-primary" href="../{html.escape(metas[0].href_html)}">'
            f"Jump in latest issue →</a>"
        )
    body = f"""
  {_topic_bar(active=str(topic["id"]), depth=1)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">Topic</p>
    <h1 class="page-title">{html.escape(str(topic["label"]))}</h1>
    <p class="muted">{html.escape(str(topic["blurb"]))}</p>
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
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">About</p>
    <h1 class="page-title">CompilerSutra Weekly</h1>
    <p class="muted">A Saturday newsletter covering what changed in compilers this week —
    LLVM, GCC, MLIR, AI compilers, GPU compilers, toolchains, and research.</p>
    <p class="muted">Git repository activity is the primary source. Releases, Discourse, and
    arXiv are labeled separately. No invented impact claims.</p>
    <div class="cta-row" style="margin-top:1.5rem">
      <a class="btn btn-primary" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub</a>
      <a class="btn btn-ghost" href="{html.escape(EDU_URL)}" rel="noopener noreferrer">CompilerSutra.com</a>
      <a class="btn btn-ghost" href="subscribe.html">Subscribe</a>
    </div>
  </main>
"""
    return _shell("About — CompilerSutra Weekly", body, active="about", depth=0)


def _page_subscribe() -> str:
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">Subscribe</p>
    <h1 class="page-title">Get future issues</h1>
    <p class="muted">Email delivery is not wired yet. To enable it we need a provider
    (e.g. Buttondown, Listmonk, or GitHub Discussions announcements) plus a double-opt-in
    list — we will not ship a fake signup form.</p>
    <p class="muted">Until then: watch the
    <a href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub repository</a>
    or check the <a href="archive.html">archive</a> each Saturday.
    RSS is planned as an optional feed, not the primary format.</p>
  </main>
"""
    return _shell("Subscribe — CompilerSutra Weekly", body, active="about", depth=0)


def _page_changelog(metas: list[IssueMeta]) -> str:
    """Searchable complete change log across issues."""
    datasets: list[dict] = []
    for meta in metas:
        path = meta.path.parent / f"{meta.date}.changelog.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        datasets.append(
            {
                "date": meta.date,
                "issue_number": meta.issue_number,
                "href": meta.href_html,
                "stories": data.get("stories") or [],
            }
        )
    payload = json.dumps(datasets)
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap">
    <p class="hero-kicker">Complete change log</p>
    <h1 class="page-title">Browse all collected changes</h1>
    <p class="muted">Full dataset from the collector — including items not selected for the editorial newsletter.</p>
    <div class="filters">
      <input id="q" type="search" placeholder="Search GlobalISel, AMDGPU, Triton…" aria-label="Search"/>
      <select id="project" aria-label="Project"><option value="">All projects</option></select>
      <select id="category" aria-label="Category"><option value="">All categories</option></select>
      <select id="importance" aria-label="Importance">
        <option value="">All importance</option>
        <option value="highlight">Highlight</option>
        <option value="notable">Notable</option>
        <option value="other">Other</option>
      </select>
    </div>
    <p id="count" class="muted"></p>
    <ul id="results" class="changelog-list"></ul>
  </main>
  <script>
  const DATA = {payload};
  const results = document.getElementById('results');
  const countEl = document.getElementById('count');
  const q = document.getElementById('q');
  const project = document.getElementById('project');
  const category = document.getElementById('category');
  const importance = document.getElementById('importance');
  const projects = new Set();
  const categories = new Set();
  const flat = [];
  for (const issue of DATA) {{
    for (const s of issue.stories) {{
      const proj = s.project || s.category || '';
      projects.add(proj);
      categories.add(s.category || '');
      flat.push({{...s, _date: issue.date, _href: issue.href, _num: issue.issue_number}});
    }}
  }}
  [...projects].filter(Boolean).sort().forEach(p => {{
    const o = document.createElement('option'); o.value = p; o.textContent = p; project.appendChild(o);
  }});
  [...categories].filter(Boolean).sort().forEach(c => {{
    const o = document.createElement('option'); o.value = c; o.textContent = c; category.appendChild(o);
  }});
  function render() {{
    const query = (q.value || '').toLowerCase().trim();
    const pf = project.value;
    const cf = category.value;
    const inf = importance.value;
    const hits = flat.filter(s => {{
      if (pf && (s.project || s.category) !== pf) return false;
      if (cf && s.category !== cf) return false;
      if (inf && (s.importance || 'other') !== inf) return false;
      if (!query) return true;
      const blob = [s.title, s.summary, (s.areas||[]).join(' '), s.project, s.category].join(' ').toLowerCase();
      return blob.includes(query);
    }}).slice(0, 400);
    countEl.textContent = hits.length + ' shown' + (hits.length === 400 ? ' (capped)' : '');
    results.innerHTML = hits.map(s => {{
      const areas = (s.areas && s.areas.length) ? s.areas.join(', ') : 'Other';
      const num = s._num ? ('#' + String(s._num).padStart(3,'0')) : s._date;
      return `<li>
        <a href="${{s.source_url}}" rel="noopener noreferrer"><strong>${{escapeHtml(s.title)}}</strong></a>
        <div class="meta">${{escapeHtml(s.importance||'other')}} · ${{escapeHtml(s.project||s.category||'')}} · ${{escapeHtml(areas)}} ·
          <a href="${{s._href}}">${{escapeHtml(num)}}</a></div>
      </li>`;
    }}).join('') || '<li class="topic-empty">No matches.</li>';
  }}
  function escapeHtml(t) {{
    return String(t||'').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
  }}
  [q, project, category, importance].forEach(el => el.addEventListener('input', render));
  render();
  </script>
"""
    return _shell("Change log — CompilerSutra Weekly", body, active="archive", depth=0)


def _page_issue(
    meta: IssueMeta,
    md: str,
    prev_m: IssueMeta | None,
    next_m: IssueMeta | None,
) -> str:
    content = markdown_to_html(md)
    toc_links = []
    for m in re.finditer(r'<h2 id="([^"]+)">([^<]+)</h2>', content):
        toc_links.append(
            f'<a href="#{html.escape(m.group(1))}">{html.escape(m.group(2))}</a>'
        )
    toc = (
        f'<nav class="toc" aria-label="On this page">{"".join(toc_links)}</nav>'
        if toc_links
        else ""
    )
    nav_bits = ['<a class="back" href="../../archive.html">← Archive</a>']
    if prev_m:
        nav_bits.append(
            f'<a class="back" href="../{html.escape(prev_m.path.parent.name)}/{html.escape(prev_m.date)}.html">← Prev</a>'
        )
    if next_m:
        nav_bits.append(
            f'<a class="back" href="../{html.escape(next_m.path.parent.name)}/{html.escape(next_m.date)}.html">Next →</a>'
        )
    num = f"#{meta.issue_number:03d}" if meta.issue_number else meta.date
    body = f"""
  {_topic_bar(depth=2)}
  <article class="article">
    <div class="issue-nav">{" · ".join(nav_bits)}</div>
    <p class="hero-kicker">Issue {html.escape(num)}</p>
    {toc}
    {content}
    <p class="muted" style="margin-top:2rem">
      <a href="../../changelog.html">Complete change log</a> ·
      <a href="../../archive.html">Archive</a> ·
      <a href="../../subscribe.html">Subscribe</a>
    </p>
  </article>
"""
    return _shell(f"{num} — CompilerSutra Weekly", body, active="archive", depth=2)


def _issue_rows(metas: list[IssueMeta], *, depth: int) -> str:
    prefix = "" if depth == 0 else "../" * depth
    rows = []
    for m in metas:
        href = prefix + m.href_html
        num = f"#{m.issue_number:03d}" if m.issue_number else "Weekly issue"
        rows.append(
            f"""<li>
  <a class="issue-row" href="{html.escape(href)}">
    <span class="issue-date">{html.escape(m.date)}</span>
    <span class="title">{html.escape(num)}</span>
    <span class="issue-window">{html.escape(m.window)}</span>
  </a>
</li>"""
        )
    return "\n".join(rows)


def _extract_section(md: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
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
    changelog = "changelog.html" if depth == 0 else "../" * depth + "changelog.html"
    if depth == 0:
        topics = "topics/index.html"
    elif depth == 1:
        topics = "index.html"
    else:
        topics = "../../topics/index.html"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <meta name="description" content="What changed in compilers this week — LLVM, GCC, MLIR, AI and GPU compilers."/>
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
        <a href="{changelog}">Change log</a>
        <a href="{about}"{" aria-current=\"page\"" if active=="about" else ""}>About</a>
        <a class="pill" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub</a>
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
    text = path.read_text(encoding="utf-8", errors="replace")[:1200]
    for pat in (
        r"\*\*Reporting period:\*\*\s*([^\n]+)",
        r"\*\*Reporting window:\*\*\s*([^\n]+)",
    ):
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return None
