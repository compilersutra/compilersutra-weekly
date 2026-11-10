# SPDX-License-Identifier: Apache-2.0
"""Publication site: homepage, topics discovery, issue pages."""

from __future__ import annotations

import html
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from csweekly.analyzers.taxonomy import DOMAINS, STAGES, TECH_AREAS
from csweekly.brand import (
    BRAND_TAG,
    CADENCE,
    CONTACT_NOTE,
    EDU_URL,
    HERO_KICKER,
    HERO_LEDE,
    HERO_TITLE,
    ISSUES_URL,
    META_DESCRIPTION,
    PAGES_URL,
    PROJECT_NAME,
    REPO_URL,
)
from csweekly.reporters.mdhtml import markdown_to_html
from csweekly.reporters.taxonomy_ui import (
    format_issue_date,
    taxonomy_badges_html,
    taxonomy_line,
)

TOPICS: list[dict[str, object]] = [
    {
        "id": "llvm",
        "label": "LLVM",
        "blurb": "Optimization · IR · CodeGen · Clang · backends",
        "about": (
            "LLVM is a project ecosystem spanning Clang/CIR frontends, middle-end IR "
            "and transforms, and many CPU/GPU backends. Treat it as infrastructure — "
            "not a single stage or domain."
        ),
        "stages": ["Frontend", "Middle-end", "Backend", "Runtime & Toolchain"],
        "domains": ["CPU", "GPU", "Languages"],
        "headings": ["LLVM", "Clang", "High signal", "By topic"],
        "domain": "CPU",
    },
    {
        "id": "gcc",
        "label": "GCC",
        "blurb": "GIMPLE · RTL · middle-end · targets",
        "about": (
            "GCC covers language frontends, GIMPLE/RTL middle-end work, and a large "
            "set of CPU (and some accelerator) backends. Changes here often affect "
            "ABI, vectorization, and target-specific codegen."
        ),
        "stages": ["Frontend", "Middle-end", "Backend"],
        "domains": ["CPU", "Languages"],
        "headings": ["GCC", "By topic"],
        "domain": "CPU",
    },
    {
        "id": "mlir",
        "label": "MLIR",
        "blurb": "Dialects · transformations · infrastructure",
        "about": (
            "MLIR is a multi-level IR framework used by AI compilers, GPU stacks, "
            "and hardware generators. A dialect change may be middle-end IR work, "
            "GPU lowering, or both — classify from the change, not the repo name."
        ),
        "stages": ["Middle-end", "Backend"],
        "domains": ["AI / ML", "GPU", "Accelerators"],
        "headings": ["MLIR", "By topic"],
        "domain": "AI / ML",
    },
    {
        "id": "ai",
        "label": "AI Compilers",
        "blurb": "Triton · XLA · IREE · TVM · MLIR",
        "about": (
            "AI / ML compilers lower models onto CPUs, GPUs, and accelerators. "
            "Follow this topic for Triton, XLA, IREE, TVM and related stacks."
        ),
        "stages": ["Middle-end", "Backend", "Runtime & Toolchain"],
        "domains": ["AI / ML", "GPU", "Accelerators"],
        "headings": ["AI Compilers", "By topic"],
        "domain": "AI / ML",
    },
    {
        "id": "gpu",
        "label": "GPU",
        "blurb": "AMDGPU · NVPTX · SPIR-V · offloading",
        "about": (
            "GPU compiler work spans NVPTX/NVVM, AMDGPU, SPIR-V, and offload "
            "runtimes. Prefer Backend + GPU labels when the change is target lowering."
        ),
        "stages": ["Backend", "Runtime & Toolchain", "Middle-end"],
        "domains": ["GPU"],
        "headings": ["GPU Compilers", "By topic"],
        "domain": "GPU",
    },
    {
        "id": "research",
        "label": "Research",
        "blurb": "Papers, benchmarks, technical notes",
        "about": (
            "Selected papers, RFCs, and technical discussions that help explain "
            "where compiler research is heading — not a literature dump."
        ),
        "stages": [],
        "domains": ["Research"],
        "headings": ["Worth reading", "Research papers"],
        "domain": "Research",
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
    groups: list[dict] = field(default_factory=list)


def list_issues(reports_dir: Path) -> list[Path]:
    """Published issues only — drafts/collecting editions never appear on the site."""
    from csweekly.edition import is_publicly_visible
    from datetime import date as _date

    files = sorted(reports_dir.glob("**/*.md"), reverse=True)
    out: list[Path] = []
    for p in files:
        if p.name == "README.md" or p.parent.name == "archive":
            continue
        try:
            published_on = _date.fromisoformat(p.stem)
        except ValueError:
            continue
        if is_publicly_visible(published_on):
            out.append(p)
    return out


def write_archive_index(reports_dir: Path, site_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    issues_md = list_issues(reports_dir)
    chronological = sorted(issues_md, key=lambda p: p.stem)
    number_by_date = {p.stem: i + 1 for i, p in enumerate(chronological)}

    lines = [
        f"# {PROJECT_NAME} — Archive",
        "",
        f"Site: [{PAGES_URL}]({PAGES_URL}) · Source: [{REPO_URL}]({REPO_URL})",
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
        num = number_by_date.get(stem)
        label = f"#{num:03d}" if num else stem
        lines.append(f"| [{label} {stem}]({rel}) | {window} |")
        payload = _load_changelog(path)
        metas.append(
            IssueMeta(
                path=path,
                date=stem,
                window=window,
                href_html=f"issues/{path.parent.name}/{stem}.html",
                md=md,
                issue_number=num,
                stats=payload.get("stats") or {},
                groups=payload.get("groups") or payload.get("high_signal") or [],
            )
        )
    lines.extend(["", f"Education: [{EDU_URL}]({EDU_URL}).", ""])
    archive = reports_dir / "README.md"
    archive.write_text("\n".join(lines), encoding="utf-8")

    assets_src = Path(__file__).resolve().parent / "static"
    for name in ("reports", "issues", "topics", "explore"):
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
    (site_dir / "feed.xml").write_text(_atom_feed(metas), encoding="utf-8")
    (site_dir / "topics").mkdir(parents=True, exist_ok=True)
    (site_dir / "topics" / "index.html").write_text(_page_topics_hub(metas), encoding="utf-8")
    for topic in TOPICS:
        (site_dir / "topics" / f"{topic['id']}.html").write_text(
            _page_topic(topic, metas), encoding="utf-8"
        )

    # Discovery dimensions
    explore = site_dir / "explore"
    explore.mkdir(parents=True, exist_ok=True)
    (explore / "index.html").write_text(_page_explore_hub(metas), encoding="utf-8")
    for stage in STAGES:
        slug = _slug(stage)
        (explore / f"stage-{slug}.html").write_text(
            _page_dimension("stage", stage, metas), encoding="utf-8"
        )
    for domain in DOMAINS:
        slug = _slug(domain)
        (explore / f"domain-{slug}.html").write_text(
            _page_dimension("domain", domain, metas), encoding="utf-8"
        )
    for area in TECH_AREAS:
        slug = _slug(area)
        (explore / f"area-{slug}.html").write_text(
            _page_dimension("area", area, metas), encoding="utf-8"
        )

    for i, meta in enumerate(metas):
        prev_m = metas[i + 1] if i + 1 < len(metas) else None
        next_m = metas[i - 1] if i > 0 else None
        out = site_dir / "issues" / meta.path.parent.name / f"{meta.date}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_page_issue(meta, meta.md, prev_m, next_m), encoding="utf-8")

    (site_dir / "index.md").write_text(
        f"# {PROJECT_NAME}\n\nOpen [{PAGES_URL}]({PAGES_URL}).\n", encoding="utf-8"
    )
    return archive


def _load_changelog(md_path: Path) -> dict:
    sibling = md_path.parent / f"{md_path.stem}.changelog.json"
    if not sibling.is_file():
        return {}
    try:
        return json.loads(sibling.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _topic_bar(active: str = "", *, depth: int = 0) -> str:
    prefix = "" if depth == 0 else "../" * depth
    links = []
    for t in TOPICS:
        href = f"{prefix}topics/{t['id']}.html"
        cur = ' aria-current="page"' if active == t["id"] else ""
        links.append(f'<a href="{href}"{cur}>{html.escape(str(t["label"]))}</a>')
    return f"""
  <div class="subnav" aria-label="Secondary">
    <div class="wrap">
      <a href="{prefix}explore/stage-frontend.html">Frontend</a>
      <a href="{prefix}explore/stage-middle-end.html">Middle-end</a>
      <a href="{prefix}explore/stage-backend.html">Backend</a>
      <a href="{prefix}explore/stage-runtime-toolchain.html">Runtime</a>
      <a href="{prefix}explore/domain-cpu.html">CPU</a>
      <a href="{prefix}explore/domain-gpu.html">GPU</a>
      <a href="{prefix}explore/domain-ai-ml.html">AI / ML</a>
      <a href="{prefix}topics/index.html"{' aria-current="page"' if active=='topics' else ''}>Projects</a>
      {''.join(links)}
    </div>
  </div>
"""


def _page_home(metas: list[IssueMeta], latest: IssueMeta | None) -> str:
    payload = _load_changelog(latest.path) if latest else {}
    featured = ""
    recent = ""
    latest_block = '<p class="topic-empty">No issues yet.</p>'
    if latest:
        num = f"#{latest.issue_number:03d}" if latest.issue_number else latest.date
        high = list(payload.get("high_signal") or [])
        dive = payload.get("deep_dive")
        hs_total = int(latest.stats.get("high_signal") or (len(high) + (1 if dive else 0)))
        wk = int(latest.stats.get("worth_knowing") or 0)
        pub_human = format_issue_date(latest.date)
        bullets = payload.get("week_overview") or []
        # Prefer short “what / why” lines over long commit-title dumps
        overview_items = []
        for b in bullets[:5]:
            overview_items.append(f"<li>{html.escape(b)}</li>")
        overview = (
            "<ul class='overview-list'>" + "".join(overview_items) + "</ul>"
            if overview_items
            else ""
        )
        latest_block = f"""
        <div class="latest-card">
          <p class="hero-kicker">Issue {html.escape(num)} · {html.escape(pub_human)}</p>
          <h2>This week&rsquo;s engineering highlights</h2>
          <p class="latest-cover">{hs_total} high-signal · {wk} worth knowing</p>
          <p class="muted">{html.escape(HERO_LEDE)}</p>
          {overview}
          <div class="cta-row">
            <a class="btn btn-primary" href="{html.escape(latest.href_html)}">Read this week&rsquo;s issue →</a>
            <a class="btn btn-ghost" href="subscribe.html">Subscribe (RSS)</a>
          </div>
        </div>
"""
        feat = dive or (high[0] if high else None)
        feat_id = (feat or {}).get("story_id") or (feat or {}).get("id")
        if feat:
            why = html.escape((feat.get("why_it_matters") or "")[:280])
            notes = feat.get("deep_dive_notes") or {}
            problem = html.escape((notes.get("problem") or feat.get("what_changed") or "")[:320])
            src = "#"
            stories = feat.get("stories") or []
            if stories:
                src = html.escape(stories[0].get("source_url") or "#")
            featured = f"""
      <section class="wrap" style="padding:2rem 0 0.5rem" aria-labelledby="featured-heading">
        <h2 id="featured-heading" class="section-label">Deep dive</h2>
        <article class="feature-card">
          <h2>{html.escape((feat.get("title") or "")[:140])}</h2>
          {taxonomy_badges_html(feat)}
          <p class="secondary"><strong>Problem.</strong> {problem}</p>
          <p class="secondary"><strong>Why engineers should care.</strong> {why}</p>
          <div class="cta-row" style="margin-top:0.85rem">
            <a class="btn btn-primary" href="{html.escape(latest.href_html)}#deep-dive">Full technical analysis →</a>
            <a class="btn btn-ghost" href="{src}" rel="noopener noreferrer">Primary source</a>
          </div>
        </article>
      </section>
"""
        # Do not repeat the featured deep-dive in the grid
        grid_src = [
            g
            for g in high
            if ((g.get("story_id") or g.get("id")) != feat_id)
        ][:6]
        shown = len(grid_src)
        remain = max(0, len(high) - shown)
        cards = "".join(_group_html_card(g, depth=0) for g in grid_src)
        if cards:
            count_note = (
                f"Showing {shown} of {len(high)} high-signal developments"
                + (f" · {remain} more in the issue" if remain else "")
                + f" · {hs_total} total including deep dive"
            )
            recent = f"""
      <section class="wrap" style="padding:1.5rem 0 0.5rem" aria-labelledby="latest-dev">
        <h2 id="latest-dev" class="section-label">This week&rsquo;s engineering highlights</h2>
        <p class="muted">{html.escape(count_note)}</p>
        <div class="story-grid">{cards}</div>
        <p class="muted" style="margin-top:0.85rem">
          <a href="{html.escape(latest.href_html)}">Open the full issue for every selected story →</a>
        </p>
      </section>
"""

    domain_cards = "\n".join(
        f"""<a class="bucket" href="topics/{html.escape(str(t['id']))}.html">
  <strong>{html.escape(str(t['label']))}</strong>
  <span>{html.escape(str(t['blurb']))}</span>
</a>"""
        for t in TOPICS
        if t["id"] in {"llvm", "gcc", "mlir", "gpu", "ai", "research"}
    )
    items = _issue_rows(metas[:10], depth=0)
    body = f"""
  <main>
    <section class="hero">
      <div class="wrap">
        <p class="hero-kicker">CompilerSutra Weekly</p>
        <h1>{html.escape(HERO_TITLE)}</h1>
        <p class="lede">LLVM · GCC · MLIR · GPU · AI Compilers — {html.escape(HERO_LEDE)}</p>
        {latest_block}
      </div>
    </section>
    {featured}
    {recent}
    <div class="wrap" style="padding-top:2rem">
      <h2 class="section-label">Explore by engineering domain</h2>
      <p class="muted" style="margin-bottom:0.85rem">
        Independent filters for project, compiler stage, and hardware —
        <a href="explore/index.html">open Explore</a>.
      </p>
      <div class="buckets">{domain_cards}</div>
      <section class="panel" aria-labelledby="archive-heading">
        <h2 id="archive-heading">Archive</h2>
        <ul class="issue-list">{items if items else '<li class="topic-empty">No issues yet.</li>'}</ul>
      </section>
    </div>
  </main>
"""
    return _shell("CompilerSutra Weekly", body, active="home", depth=0)


def _page_topics_hub(metas: list[IssueMeta]) -> str:
    latest = metas[0] if metas else None
    counts = latest.stats.get("by_domain") or {} if latest else {}
    # Also count groups by category from latest changelog
    cat_counts: dict[str, int] = defaultdict(int)
    if latest:
        for g in latest.groups:
            cat = (g.get("category") or "").lower()
            cat_counts[cat] += 1
            for d in g.get("domains") or []:
                counts[d] = counts.get(d, 0) + 1

    cards = []
    for t in TOPICS:
        tid = str(t["id"])
        # map topic id → category count
        key = {"llvm": "llvm", "gcc": "gcc", "mlir": "mlir", "ai": "ai", "gpu": "gpu", "research": "research"}.get(tid, tid)
        n = cat_counts.get(key, 0)
        if tid == "llvm":
            n += cat_counts.get("clang", 0)
        label = str(t["label"])
        if tid == "research" and latest:
            n = int(latest.stats.get("research") or 0)
            latest_line = (
                f"<span class='go'>{n} papers/items in latest issue →</span>"
                if n
                else f"<span class='go'>Open {html.escape(label)} →</span>"
            )
        elif latest and n:
            latest_line = f"<span class='go'>{n} curated in latest · Open {html.escape(label)} →</span>"
        else:
            latest_line = f"<span class='go'>Open {html.escape(label)} →</span>"
        cards.append(
            f"""<a class="bucket" href="{html.escape(tid)}.html">
  <strong>{html.escape(label)}</strong>
  <span>{html.escape(str(t['blurb']))}</span>
  {latest_line}
</a>"""
        )
    body = f"""
  {_topic_bar(active="topics", depth=1)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">Topics</p>
    <h1 class="page-title">Follow a topic</h1>
    <p class="muted">Counts come from the latest curated issue — not every raw commit.</p>
    <div class="buckets">{''.join(cards)}</div>
    <p class="muted"><a href="../explore/index.html">Or explore by stage / domain / technical area →</a></p>
  </main>
"""
    return _shell("Topics — CompilerSutra Weekly", body, active="topics", depth=1)


def _page_explore_hub(metas: list[IssueMeta]) -> str:
    stage_links = " ".join(
        f'<a class="chip" href="stage-{html.escape(_slug(s))}.html">{html.escape(s)}</a>'
        for s in STAGES
    )
    domain_links = " ".join(
        f'<a class="chip" href="domain-{html.escape(_slug(d))}.html">{html.escape(d)}</a>'
        for d in DOMAINS
    )
    area_links = " ".join(
        f'<a class="chip" href="area-{html.escape(_slug(a))}.html">{html.escape(a)}</a>'
        for a in TECH_AREAS
    )
    flat: list[dict] = []
    for meta in metas:
        payload = _load_changelog(meta.path)
        for g in payload.get("groups") or meta.groups or []:
            flat.append(
                {
                    "title": g.get("title"),
                    "why": g.get("why_it_matters"),
                    "what": g.get("what_changed"),
                    "stages": g.get("stages") or [],
                    "domains": g.get("domains") or [],
                    "areas": g.get("technical_areas") or [],
                    "project": g.get("project") or g.get("category") or "",
                    "change_type": g.get("change_type") or "",
                    "signal": g.get("signal") or "",
                    "href": f"../{meta.href_html}",
                    "issue": f"#{meta.issue_number:03d}" if meta.issue_number else meta.date,
                    "source": ((g.get("stories") or [{}])[0].get("source_url") or "#"),
                }
            )
    payload_json = json.dumps(flat)
    body = f"""
  {_topic_bar(active="explore", depth=1)}
  <main class="wrap">
    <p class="hero-kicker">Explore</p>
    <h1 class="page-title">Discover across stages, domains and projects</h1>
    <p class="muted">Combine filters. Example: Backend + GPU + Code generation + LLVM.
      Shareable via the URL query string.</p>
    <div class="filters explore-filters" id="explore-filters">
      <input id="q" type="search" placeholder="Search titles, why, projects…" aria-label="Search"/>
      <select id="stage" aria-label="Compiler stage"><option value="">All stages</option>
        {''.join(f'<option value="{html.escape(s)}">{html.escape(s)}</option>' for s in STAGES)}
      </select>
      <select id="domain" aria-label="Domain"><option value="">All domains</option>
        {''.join(f'<option value="{html.escape(d)}">{html.escape(d)}</option>' for d in DOMAINS)}
      </select>
      <select id="area" aria-label="Technical area"><option value="">All areas</option>
        {''.join(f'<option value="{html.escape(a)}">{html.escape(a)}</option>' for a in TECH_AREAS)}
      </select>
      <select id="project" aria-label="Project"><option value="">All projects</option></select>
    </div>
    <div class="chip-row" id="active-filters" aria-live="polite"></div>
    <p id="count" class="muted"></p>
    <div id="results" class="story-grid"></div>
    <h2 id="stages" class="section-label" style="margin-top:2.5rem">Browse by stage</h2>
    <div class="chip-row">{stage_links}</div>
    <h2 id="domains" class="section-label">Browse by domain</h2>
    <div class="chip-row">{domain_links}</div>
    <h2 id="areas" class="section-label">Browse by technical area</h2>
    <div class="chip-row">{area_links}</div>
  </main>
  <script src="../assets/filters.js" defer></script>
  <script>
  window.CSW_EXPLORE = {payload_json};
  document.addEventListener('DOMContentLoaded', function () {{
    if (window.CSW && window.CSW.mountExplore) window.CSW.mountExplore(window.CSW_EXPLORE);
  }});
  </script>
"""
    return _shell("Explore — CompilerSutra Weekly", body, active="explore", depth=1)


def _page_dimension(kind: str, label: str, metas: list[IssueMeta]) -> str:
    attr = {"stage": "stages", "domain": "domains", "area": "technical_areas"}[kind]
    cards = []
    for meta in metas[:6]:
        matches = []
        for g in meta.groups:
            vals = g.get(attr) or []
            if label in vals:
                matches.append(g)
        if not matches:
            continue
        num = f"#{meta.issue_number:03d}" if meta.issue_number else meta.date
        items = "".join(
            f"<li><strong>{html.escape((g.get('title') or '')[:100])}</strong>"
            f"<div class='meta'>{html.escape((g.get('why_it_matters') or '')[:160])}</div></li>"
            for g in matches[:8]
        )
        cards.append(
            f"""<section class="topic-issue-block">
  <h3><a href="../{html.escape(meta.href_html)}">{html.escape(num)} · {html.escape(meta.date)}</a></h3>
  <ul class="story-mini">{items}</ul>
</section>"""
        )
    content = "\n".join(cards) or '<p class="topic-empty">No curated stories in this dimension yet.</p>'
    body = f"""
  {_topic_bar(active="explore", depth=1)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">{html.escape(kind)}</p>
    <h1 class="page-title">{html.escape(label)}</h1>
    <p class="muted">Curated stories tagged with this {html.escape(kind)} across recent issues.</p>
    <div class="cta-row" style="margin-bottom:1.5rem">
      <a class="btn btn-ghost" href="index.html">All dimensions</a>
      <a class="btn btn-ghost" href="../changelog.html">Change log</a>
    </div>
    {content}
  </main>
"""
    return _shell(f"{label} — CompilerSutra Weekly", body, active="explore", depth=1)


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
        groups = [
            g
            for g in meta.groups
            if (g.get("category") == topic["id"])
            or (topic["id"] == "llvm" and g.get("category") in {"llvm", "clang"})
            or (topic["id"] == "gpu" and "GPU" in (g.get("domains") or []))
            or (
                topic["id"] == "ai"
                and (
                    g.get("category") == "ai"
                    or "AI / ML" in (g.get("domains") or [])
                )
            )
            or (str(topic.get("domain")) in (g.get("domains") or []) and topic["id"] not in {"llvm", "gcc"})
        ]
        if groups:
            cards = "".join(_group_html_card(g, depth=1) for g in groups[:10])
            num = f"#{meta.issue_number:03d}" if meta.issue_number else meta.date
            blocks.append(
                f"""<section class="topic-issue-block">
  <h3><a href="../{html.escape(meta.href_html)}">{html.escape(num)} · full issue</a></h3>
  <p class="muted">Latest developments · {html.escape(meta.window)}</p>
  <div class="story-grid">{cards}</div>
</section>"""
            )
            continue
        if not section_md:
            continue
        section_html = markdown_to_html(f"## {used}\n\n{section_md}")
        num = f"#{meta.issue_number:03d}" if meta.issue_number else meta.date
        blocks.append(
            f"""<section class="topic-issue-block">
  <h3><a href="../{html.escape(meta.href_html)}">{html.escape(num)}</a></h3>
  <div class="article" style="padding:0;width:auto;margin:0">{section_html}</div>
</section>"""
        )
    content = "\n".join(blocks) or '<p class="topic-empty">No stories yet.</p>'
    stage_chips = " ".join(
        f'<a class="chip" href="../explore/stage-{html.escape(_slug(s))}.html">{html.escape(s)}</a>'
        for s in (topic.get("stages") or [])
    )
    domain_chips = " ".join(
        f'<a class="chip" href="../explore/domain-{html.escape(_slug(d))}.html">{html.escape(d)}</a>'
        for d in (topic.get("domains") or [])
    )
    related = ""
    if stage_chips or domain_chips:
        related = f"""
    <section class="panel">
      <h2 class="section-label" style="font-size:1.1rem">Related discovery</h2>
      <p class="muted">Related stages</p>
      <div class="chip-row">{stage_chips or '<span class="muted">—</span>'}</div>
      <p class="muted">Related domains</p>
      <div class="chip-row">{domain_chips or '<span class="muted">—</span>'}</div>
    </section>
"""
    body = f"""
  {_topic_bar(active=str(topic["id"]), depth=1)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">Topic · project ecosystem</p>
    <h1 class="page-title">{html.escape(str(topic["label"]))}</h1>
    <p class="muted">{html.escape(str(topic.get("about") or topic["blurb"]))}</p>
    {related}
    <h2 class="section-label">Latest developments</h2>
    {content}
  </main>
"""
    return _shell(f'{topic["label"]} — CompilerSutra Weekly', body, active="topics", depth=1)


def _group_html_card(g: dict, *, depth: int = 0, compact: bool = False) -> str:
    title = html.escape((g.get("title") or "")[:120])
    why = html.escape((g.get("why_it_matters") or "Impact not yet clear.")[:200])
    what = html.escape((g.get("what_changed") or "")[:160])
    tax = taxonomy_line(g)
    url = "#"
    stories = g.get("stories") or []
    if stories:
        url = html.escape(stories[0].get("source_url") or "#")
    if compact:
        return f"""<article class="story-row">
  <h4><a href="{url}" rel="noopener noreferrer">{title}</a></h4>
  <p class="secondary">{why}</p>
  <div class="meta">{tax}</div>
</article>"""
    what_block = f'<p class="secondary">{what}</p>' if what else ""
    return f"""<article class="story-card">
  <h4><a href="{url}" rel="noopener noreferrer">{title}</a></h4>
  {taxonomy_badges_html(g)}
  {what_block}
  <p>{why}</p>
  <div class="meta"><a href="{url}" rel="noopener noreferrer">Investigate source →</a></div>
</article>"""


def _page_archive(metas: list[IssueMeta]) -> str:
    items = _issue_rows(metas, depth=0)
    latest = metas[0] if metas else None
    next_note = (
        f'<p class="muted">Latest: #{latest.issue_number:03d} ({html.escape(latest.date)}). '
        f"{html.escape(CADENCE)}</p>"
        if latest and latest.issue_number
        else f'<p class="muted">{html.escape(CADENCE)}</p>'
    )
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">Archive</p>
    <h1 class="page-title">All issues</h1>
    {next_note}
    <div class="cta-row" style="margin-bottom:1rem">
      <a class="btn btn-ghost" href="subscribe.html">Subscribe (RSS)</a>
      <a class="btn btn-ghost" href="feed.xml">Atom feed</a>
    </div>
    <section class="panel" style="margin-top:0.5rem">
      <ul class="issue-list">{items or "<li>No issues yet.</li>"}</ul>
    </section>
  </main>
"""
    return _shell("Archive — CompilerSutra Weekly", body, active="archive", depth=0)


def _page_about() -> str:
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">About</p>
    <h1 class="page-title">How this weekly works</h1>
    <p class="muted">CompilerSutra Weekly is a curated brief of compiler changes.
    We explain <em>what changed</em>, <em>why it might matter</em>, and
    <em>who should care</em> — and we mark uncertainty when the source is thin.</p>

    <h2 class="section-label">Cadence</h2>
    <p class="muted">{html.escape(CADENCE)} Issues stay at stable URLs under
    <code>issues/YYYY/YYYY-MM-DD.html</code>.</p>

    <h2 class="section-label">Publishing lifecycle</h2>
    <p class="muted">Raw data accumulates all week and is <strong>never</strong> the
    public newsletter by itself. Pipeline:</p>
    <ol class="muted">
      <li><strong>Collect</strong> (Sat→Fri) — idempotent raw facts into an edition</li>
      <li><strong>Freeze</strong> (end of Friday) — close the period</li>
      <li><strong>Process / review</strong> — normalize, cluster, editorial queue</li>
      <li><strong>Validate → publish</strong> (Saturday) — one immutable curated issue</li>
    </ol>
    <p class="muted">While the next issue is collecting, the site continues to show the
    last published issue. Late items after freeze go to the next edition or an
    explicit addendum — published issues are not silently rewritten.</p>

    <h2 class="section-label">Sources</h2>
    <p class="muted">Primary: git mirrors of tracked projects (LLVM/Clang, GCC, MLIR paths,
    selected GPU/AI stacks). Secondary: GitHub releases, selected RFCs/discussions,
    and compiler-relevant arXiv items when present in the collect window.</p>

    <h2 class="section-label">Selection and “high signal”</h2>
    <p class="muted">Commits are grouped by related subjects/paths into development themes.
    Heuristics promote items that look like new support, ABI, codegen, correctness, or
    multi-commit themes. Noise (reverts, NFC-only, test-only) is demoted. The newsletter
    is curated from that set — not every collected commit.</p>
    <p class="muted">We do <strong>not</strong> invent benchmarks, performance numbers,
    or completion status. If impact is unclear from the subject/paths, we say so.</p>

    <h2 class="section-label">Labels</h2>
    <p class="muted"><strong>Stage</strong> (Frontend / Middle-end / Backend / Runtime &amp; Toolchain),
    <strong>domain</strong> (CPU, GPU, AI/ML, …), <strong>hardware</strong> (when paths/subjects
    name a target), and <strong>audience</strong> are assigned independently from evidence.
    SPIR-V may appear as a hardware/target chip when the change is SPIR-V-specific.
    “Papers” in the nav is research reading; Explore’s Research domain is the same label
    used as a filter over stories.</p>

    <h2 class="section-label">Who maintains this</h2>
    <p class="muted">Published by CompilerSutra under Apache-2.0.
    {html.escape(CONTACT_NOTE)}</p>

    <div class="cta-row" style="margin-top:1.5rem">
      <a class="btn btn-primary" href="subscribe.html">Subscribe (RSS)</a>
      <a class="btn btn-ghost" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub</a>
      <a class="btn btn-ghost" href="{html.escape(ISSUES_URL)}" rel="noopener noreferrer">Report a correction</a>
      <a class="btn btn-ghost" href="{html.escape(EDU_URL)}" rel="noopener noreferrer">CompilerSutra.com</a>
    </div>
  </main>
"""
    return _shell("About — CompilerSutra Weekly", body, active="about", depth=0)


def _page_subscribe() -> str:
    feed = "feed.xml"
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">Subscribe</p>
    <h1 class="page-title">Follow new issues</h1>
    <p class="muted">{html.escape(CADENCE)}</p>
    <p class="muted">Email delivery is not wired yet — we will not ship a fake signup form.
    Use the Atom feed in any reader, or watch the GitHub repo.</p>
    <div class="cta-row" style="margin-top:1.25rem">
      <a class="btn btn-primary" href="{feed}">Atom feed</a>
      <a class="btn btn-ghost" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">Watch on GitHub</a>
      <a class="btn btn-ghost" href="archive.html">Browse archive</a>
    </div>
    <p class="muted" style="margin-top:1.5rem">Feed URL:
      <code>{html.escape(PAGES_URL.rstrip('/'))}/feed.xml</code></p>
  </main>
"""
    return _shell("Subscribe — CompilerSutra Weekly", body, active="about", depth=0)


def _page_changelog(metas: list[IssueMeta]) -> str:
    datasets = []
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
                "groups": data.get("groups") or [],
            }
        )
    # Static preview so the page is useful without JS / before script runs
    preview_rows: list[str] = []
    for issue in datasets[:2]:
        for s in (issue.get("stories") or [])[:25]:
            title = html.escape((s.get("title") or "")[:140])
            url = html.escape(s.get("source_url") or "#")
            sig = html.escape(str(s.get("signal") or s.get("importance") or ""))
            proj = html.escape(str(s.get("project") or s.get("category") or ""))
            num = (
                f"#{int(issue['issue_number']):03d}"
                if issue.get("issue_number")
                else issue.get("date")
            )
            href = html.escape(str(issue.get("href") or "archive.html"))
            preview_rows.append(
                f"<li><a href='{url}' rel='noopener noreferrer'><strong>{title}</strong></a>"
                f"<div class='meta'>{sig} · {proj} · <a href='{href}'>{html.escape(str(num))}</a></div></li>"
            )
            if len(preview_rows) >= 40:
                break
        if len(preview_rows) >= 40:
            break
    if preview_rows:
        static_list = "\n".join(preview_rows)
        count_seed = f"{len(preview_rows)} shown (filter to refine)"
    else:
        static_list = '<li class="topic-empty">No collected stories yet. Run a collect/report cycle first.</li>'
        count_seed = "0 shown"
    payload = json.dumps(datasets)
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap">
    <p class="hero-kicker">Complete change log</p>
    <h1 class="page-title">Search the collected dataset</h1>
    <p class="muted">Includes items not selected for the editorial newsletter.
      Filters need JavaScript; a preview is listed below either way.</p>
    <div class="filters">
      <input id="q" type="search" placeholder="Search RISC-V, vectorization, MLIR, AMDGPU…" aria-label="Search"/>
      <select id="project" aria-label="Project"><option value="">All projects</option></select>
      <select id="domain" aria-label="Domain"><option value="">All domains</option></select>
      <select id="stage" aria-label="Stage"><option value="">All stages</option></select>
      <select id="importance" aria-label="Signal">
        <option value="">All signals</option>
        <option value="high_signal">High signal</option>
        <option value="worth_knowing">Worth knowing</option>
        <option value="highlight">Highlight</option>
        <option value="notable">Notable</option>
        <option value="other">Other</option>
      </select>
    </div>
    <p id="count" class="muted">{html.escape(count_seed)}</p>
    <ul id="results" class="changelog-list">
      {static_list}
    </ul>
  </main>
  <script>
  const DATA = {payload};
  const results = document.getElementById('results');
  const countEl = document.getElementById('count');
  const q = document.getElementById('q');
  const project = document.getElementById('project');
  const domain = document.getElementById('domain');
  const stage = document.getElementById('stage');
  const importance = document.getElementById('importance');
  const projects = new Set();
  const domains = new Set();
  const stages = new Set();
  const flat = [];
  for (const issue of DATA) {{
    for (const s of issue.stories) {{
      projects.add(s.project || s.category || '');
      (s.domains||[]).forEach(d => domains.add(d));
      (s.stages||[]).forEach(d => stages.add(d));
      flat.push({{...s, _date: issue.date, _href: issue.href, _num: issue.issue_number}});
    }}
  }}
  [...projects].filter(Boolean).sort().forEach(p => {{
    const o=document.createElement('option'); o.value=p; o.textContent=p; project.appendChild(o);
  }});
  [...domains].filter(Boolean).sort().forEach(p => {{
    const o=document.createElement('option'); o.value=p; o.textContent=p; domain.appendChild(o);
  }});
  [...stages].filter(Boolean).sort().forEach(p => {{
    const o=document.createElement('option'); o.value=p; o.textContent=p; stage.appendChild(o);
  }});
  function render() {{
    const query=(q.value||'').toLowerCase().trim();
    const hits = flat.filter(s => {{
      if (project.value && (s.project||s.category)!==project.value) return false;
      if (domain.value && !(s.domains||[]).includes(domain.value)) return false;
      if (stage.value && !(s.stages||[]).includes(stage.value)) return false;
      if (importance.value) {{
        const sig = s.signal || s.importance || 'other';
        if (sig !== importance.value) return false;
      }}
      if (!query) return true;
      const blob = [s.title,s.summary,s.what_changed,s.why_it_matters,(s.who_should_care||[]).join(' '),
        (s.areas||[]).join(' '),(s.technical_areas||[]).join(' '),s.project,s.category].join(' ').toLowerCase();
      return blob.includes(query);
    }}).slice(0,400);
    countEl.textContent = hits.length ? (hits.length + ' shown') : 'No matches for these filters.';
    results.innerHTML = hits.map(s => {{
      const why = s.why_it_matters || '';
      const num = s._num ? ('#'+String(s._num).padStart(3,'0')) : s._date;
      return `<li>
        <a href="${{s.source_url}}" rel="noopener noreferrer"><strong>${{esc(s.title)}}</strong></a>
        <div class="meta">${{esc(s.signal||s.importance||'')}} · ${{esc(s.project||s.category||'')}} ·
          ${{esc(why).slice(0,140)}} · <a href="${{s._href}}">${{esc(num)}}</a></div>
      </li>`;
    }}).join('') || '<li class="topic-empty">No matches for these filters.</li>';
  }}
  function esc(t){{return String(t||'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
  [q,project,domain,stage,importance].forEach(el=>el.addEventListener('input',render));
  if (flat.length) render();
  </script>
"""
    return _shell("Change log — CompilerSutra Weekly", body, active="archive", depth=0)


def _atom_feed(metas: list[IssueMeta]) -> str:
    """Atom feed of published issues for readers/subscribe."""
    base = PAGES_URL.rstrip("/")
    updated = metas[0].date if metas else "1970-01-01"
    entries = []
    for m in metas[:52]:
        num = f"#{m.issue_number:03d}" if m.issue_number else m.date
        link = f"{base}/{m.href_html}"
        title = f"CompilerSutra Weekly {num} ({m.date})"
        summary = m.window or "Weekly compiler brief"
        # Prefer first briefing bullets from changelog when present
        payload = _load_changelog(m.path)
        bullets = payload.get("week_overview") or []
        if bullets:
            summary = " · ".join(bullets[:3])
        entries.append(
            f"""  <entry>
    <title>{html.escape(title)}</title>
    <link href="{html.escape(link)}" rel="alternate" type="text/html"/>
    <id>{html.escape(link)}</id>
    <updated>{html.escape(m.date)}T12:00:00Z</updated>
    <summary>{html.escape(summary[:500])}</summary>
  </entry>"""
        )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{html.escape(PROJECT_NAME)}</title>
  <subtitle>{html.escape(META_DESCRIPTION)}</subtitle>
  <link href="{html.escape(base)}/feed.xml" rel="self" type="application/atom+xml"/>
  <link href="{html.escape(base)}/" rel="alternate" type="text/html"/>
  <id>{html.escape(base)}/</id>
  <updated>{html.escape(updated)}T12:00:00Z</updated>
  <author><name>CompilerSutra</name><uri>{html.escape(EDU_URL)}</uri></author>
  <rights>Apache-2.0</rights>
{chr(10).join(entries)}
</feed>
"""


def _page_issue(meta: IssueMeta, md: str, prev_m: IssueMeta | None, next_m: IssueMeta | None) -> str:
    payload = _load_changelog(meta.path)
    num = f"#{meta.issue_number:03d}" if meta.issue_number else meta.date
    if payload.get("high_signal") or payload.get("groups"):
        content = _render_issue_html(meta, payload)
        toc_ids = [
            ("briefing", "Five-minute briefing"),
            ("featured", "Featured"),
            ("worth-knowing", "Worth knowing"),
            ("themes", "Themes"),
            ("worth-reading", "Research"),
            ("deep-dive", "Deep dive"),
            ("topic-index", "Topic index"),
        ]
        toc_links = "".join(f'<a href="#{i}">{html.escape(l)}</a>' for i, l in toc_ids)
        toc = f'<nav class="toc" aria-label="On this page">{toc_links}</nav>'
    else:
        content = markdown_to_html(md)
        toc_links = [
            f'<a href="#{html.escape(m.group(1))}">{html.escape(m.group(2))}</a>'
            for m in re.finditer(r'<h2 id="([^"]+)">([^<]+)</h2>', content)
        ]
        toc = f'<nav class="toc" aria-label="On this page">{"".join(toc_links)}</nav>' if toc_links else ""
    nav_bits = ['<a class="back" href="../../archive.html">← Archive</a>']
    if prev_m:
        nav_bits.append(
            f'<a class="back" href="../{html.escape(prev_m.path.parent.name)}/{html.escape(prev_m.date)}.html">← Prev</a>'
        )
    if next_m:
        nav_bits.append(
            f'<a class="back" href="../{html.escape(next_m.path.parent.name)}/{html.escape(next_m.date)}.html">Next →</a>'
        )
    body = f"""
  {_topic_bar(depth=2)}
  <article class="article issue-article">
    <div class="issue-nav">{" · ".join(nav_bits)}</div>
    <p class="hero-kicker">Issue {html.escape(num)}</p>
    <h1 class="page-title">CompilerSutra Weekly — {html.escape(num)}</h1>
    <p class="muted">Published {html.escape(meta.date)} · Window {html.escape(meta.window)}</p>
    <p class="muted">{html.escape(CADENCE)}</p>
    {toc}
    {content}
  </article>
"""
    return _shell(f"{num} — CompilerSutra Weekly", body, active="home", depth=2)


def _render_issue_html(meta: IssueMeta, payload: dict) -> str:
    parts: list[str] = []
    overview = payload.get("week_overview") or []
    if overview:
        items = "".join(f"<li>{html.escape(b)}</li>" for b in overview)
        parts.append(
            f'<section id="briefing" class="issue-section">'
            f"<h2>Five-minute briefing</h2>"
            f'<p class="muted">Start here if you only have a few minutes.</p>'
            f'<ul class="overview-list">{items}</ul></section>'
        )

    high = payload.get("high_signal") or []
    deep = payload.get("deep_dive")
    featured = list(high[:4])
    if deep and not any((g.get("story_id") or g.get("id")) == (deep.get("story_id") or deep.get("id")) for g in featured):
        featured = [deep] + featured[:3]
    if featured:
        cards = "".join(_issue_story_card(g, prominent=True) for g in featured)
        parts.append(
            f'<section id="featured" class="issue-section">'
            f"<h2>Featured developments</h2>"
            f'<p class="muted">What changed, why it matters, and where to read the source.</p>'
            f'<div class="story-stack">{cards}</div></section>'
        )

    worth = payload.get("worth_knowing") or []
    # Avoid reprinting featured IDs
    feat_ids = {(g.get("story_id") or g.get("id")) for g in featured}
    worth = [g for g in worth if (g.get("story_id") or g.get("id")) not in feat_ids]
    if worth:
        rows = "".join(_issue_story_card(g, prominent=False) for g in worth)
        parts.append(
            f'<section id="worth-knowing" class="issue-section">'
            f"<h2>Worth knowing</h2>"
            f'<p class="muted">Shorter notes for changes that still deserve a look.</p>'
            f'<div class="story-stack compact">{rows}</div></section>'
        )

    moving = payload.get("moving_stories") or {}
    if moving:
        blocks = []
        for track, items in sorted(moving.items()):
            lis_parts = []
            for raw in items:
                m = re.search(r"\[\[story:([^\]]+)\]\]", str(raw))
                visible = re.sub(r"\s*\[\[story:[^\]]+\]\]", "", str(raw)).strip()
                if m:
                    lis_parts.append(
                        f'<li><a href="#{html.escape(m.group(1))}">{html.escape(visible)}</a></li>'
                    )
                else:
                    lis_parts.append(f"<li>{html.escape(visible)}</li>")
            blocks.append(
                f"<h3>{html.escape(str(track))}</h3><ul class='theme-index'>{''.join(lis_parts)}</ul>"
            )
        parts.append(
            f'<section id="themes" class="issue-section">'
            f"<h2>Themes this week</h2>"
            f'<p class="muted">Same stories as above, grouped by project. Useful for scanning.</p>'
            f"{''.join(blocks)}</section>"
        )

    reading = _extract_section(meta.md, "Research and reading") or _extract_section(
        meta.md, "Worth reading"
    )
    if reading:
        parts.append(
            f'<section id="worth-reading" class="issue-section">'
            f"<h2>Research and reading</h2>"
            f"{markdown_to_html(reading)}</section>"
        )

    if deep:
        parts.append(_deep_dive_html(deep))

    # Topic index from groups — compact, link to anchors
    groups = payload.get("groups") or payload.get("high_signal") or []
    if groups:
        parts.append(_topic_index_html(groups))

    parts.append(
        '<section id="further" class="issue-section">'
        "<h2>Further reading</h2>"
        '<ul class="overview-list">'
        '<li><a href="../../changelog.html">Complete collected dataset</a></li>'
        '<li><a href="../../explore/index.html">Explore by stage / domain / area</a></li>'
        '<li><a href="../../topics/index.html">Topic pages</a></li>'
        '<li><a href="../../archive.html">Archive</a></li>'
        "</ul>"
        '<p class="muted" style="margin-top:1.5rem">CompilerSutra Weekly explains '
        "<em>why you should care</em> — we do not invent benchmarks or completion status.</p>"
        "</section>"
    )
    return "\n".join(parts)


def _story_anchor(g: dict) -> str:
    sid = g.get("story_id") or g.get("id") or _slug(g.get("title") or "story")
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(sid))[:80]


def _issue_story_card(g: dict, *, prominent: bool) -> str:
    anchor = _story_anchor(g)
    title = html.escape((g.get("title") or "")[:140])
    what = html.escape(g.get("what_changed") or "")
    ctx = html.escape(g.get("technical_context") or "")
    why = html.escape(g.get("why_it_matters") or "Impact not yet clear from the source alone.")
    who = html.escape(", ".join(g.get("who_should_care") or []) or "Compiler engineers")
    uncertain = html.escape(g.get("uncertainty_note") or "")
    level = html.escape(g.get("editorial_level") or ("engineering_analysis" if prominent else "quick_signal"))
    score = g.get("impact_score")
    score_bit = f" · editorial priority {score:.1f}/10" if isinstance(score, (int, float)) else ""
    stories = g.get("stories") or []
    primary = stories[0] if stories else {}
    primary_url = html.escape(primary.get("source_url") or "#")
    primary_sha = html.escape((primary.get("related_ref") or "")[:8])
    related = []
    for s in stories[1:6]:
        sha = html.escape((s.get("related_ref") or "")[:8])
        url = html.escape(s.get("source_url") or "#")
        related.append(f'<a href="{url}" rel="noopener noreferrer"><code>{sha}</code></a>')
    related_block = ""
    if related:
        related_block = (
            f'<details class="related-commits"><summary>Related commits '
            f"({len(stories) - 1})</summary><p>{' · '.join(related)}</p></details>"
        )
    cls = "story-card issue-story" if prominent else "story-row"
    files = []
    for s in stories[:3]:
        for p in (s.get("paths") or [])[:4]:
            if p not in files:
                files.append(p)
    files_p = ""
    if prominent and files:
        files_p = (
            '<p class="muted"><strong>Implementation surface.</strong> '
            + html.escape(", ".join(files[:6]))
            + "</p>"
        )
    unc_p = (
        f'<p class="muted"><em>Limitations.</em> {uncertain}</p>'
        if uncertain and (prominent or g.get("impact_uncertain"))
        else ""
    )
    if prominent:
        body = f"""  <p><strong>Change.</strong> {what}</p>
  <p class="muted"><strong>Context.</strong> {ctx}</p>
  <p><strong>Why it matters.</strong> {why}</p>
  <p class="muted"><strong>Who should care.</strong> {who}</p>
  {files_p}
  {unc_p}"""
    else:
        body = f"""  <p class="secondary">{why}</p>
  {unc_p if g.get("impact_uncertain") else ""}"""
    return f"""<article class="{cls}" id="{html.escape(anchor)}">
  <h3>{title}</h3>
  {taxonomy_badges_html(g, include_type=True)}
{body}
  <p class="meta">Level: {level}{html.escape(score_bit)} · Primary source:
    <a href="{primary_url}" rel="noopener noreferrer"><code>{primary_sha or 'link'}</code></a></p>
  {related_block}
</article>"""


def _deep_dive_html(g: dict) -> str:
    notes = g.get("deep_dive_notes") or {}
    title = html.escape((g.get("title") or "")[:160])
    anchor = _story_anchor(g)

    def n(key: str, fallback: str = "") -> str:
        return html.escape(notes.get(key) or fallback)

    sources = []
    for s in (g.get("stories") or [])[:8]:
        sha = html.escape((s.get("related_ref") or "")[:8])
        url = html.escape(s.get("source_url") or "#")
        summary = html.escape((s.get("summary") or "")[:120])
        sources.append(
            f'<li><a href="{url}" rel="noopener noreferrer"><code>{sha}</code></a> — {summary}</li>'
        )
    hw = html.escape(", ".join((g.get("hardware_targets") or [])[:3]) or "see paths")
    return f"""<section id="deep-dive" class="issue-section deep-dive">
  <h2>Deep dive</h2>
  <article class="feature-card" id="{html.escape(anchor)}-dive">
    <h3>{title}</h3>
    {taxonomy_badges_html(g)}
    <ol class="deep-list">
      <li><strong>Problem</strong> — {n("problem")}</li>
      <li><strong>Previous behavior</strong> — {n("previous_behavior")}</li>
      <li><strong>Change</strong> — {n("implementation", g.get("what_changed") or "")}</li>
      <li><strong>Implementation surface</strong> — {n("background", "See primary commit file list.")}</li>
      <li><strong>Target impact</strong> — {hw}</li>
      <li><strong>Validation</strong> — {n("validation", n("example"))}</li>
      <li><strong>Why it matters</strong> — {n("implications", g.get("why_it_matters") or "")}</li>
      <li><strong>Limitations</strong> — {n("limits", g.get("uncertainty_note") or "")}</li>
    </ol>
    <h4>Evidence (primary sources)</h4>
    <ul>{''.join(sources)}</ul>
  </article>
</section>"""


def _topic_index_html(groups: list[dict]) -> str:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for g in groups:
        cat = (g.get("category") or "other").lower()
        if cat == "llvm":
            paths = " ".join(
                " ".join(s.get("paths") or []) for s in (g.get("stories") or [])[:1]
            )
            if "clang/" in paths:
                cat = "clang"
        buckets[cat].append(g)
    order = [
        ("llvm", "LLVM"),
        ("clang", "Clang"),
        ("gcc", "GCC"),
        ("mlir", "MLIR"),
        ("ai", "AI Compilers"),
        ("gpu", "GPU"),
        ("other", "Other"),
    ]
    blocks = []
    for key, label in order:
        items = buckets.get(key) or []
        if not items:
            continue
        lis = []
        for g in items[:8]:
            anchor = _story_anchor(g)
            title = html.escape((g.get("title") or "")[:100])
            stage = html.escape(", ".join((g.get("stages") or [])[:2]) or "—")
            domain = html.escape(", ".join((g.get("domains") or [])[:2]) or "—")
            lis.append(
                f'<li><a href="#{anchor}">{title}</a> '
                f'<span class="meta">{stage} · {domain}</span></li>'
            )
        blocks.append(f"<h3>{label}</h3><ul class='theme-index'>{''.join(lis)}</ul>")
    if not blocks:
        return ""
    return (
        f'<section id="topic-index" class="issue-section">'
        f"<h2>Topic index</h2>"
        f'<p class="muted">Jump links only — details are in the sections above.</p>'
        f"{''.join(blocks)}</section>"
    )


def _issue_rows(metas: list[IssueMeta], *, depth: int) -> str:
    prefix = "" if depth == 0 else "../" * depth
    rows = []
    for m in metas:
        href = prefix + m.href_html
        num = f"#{m.issue_number:03d}" if m.issue_number else "Weekly issue"
        hs = m.stats.get("high_signal")
        wk = m.stats.get("worth_knowing")
        bits = []
        if hs:
            bits.append(f"{hs} high-signal")
        if wk:
            bits.append(f"{wk} worth knowing")
        extra = (" · " + " · ".join(bits)) if bits else ""
        human = format_issue_date(m.date)
        rows.append(
            f"""<li>
  <a class="issue-row" href="{html.escape(href)}">
    <span class="issue-date">{html.escape(human)}</span>
    <span class="title">{html.escape(num)}{html.escape(extra)}</span>
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


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _shell(title: str, body: str, *, active: str, depth: int) -> str:
    prefix = "assets" if depth == 0 else "../" * depth + "assets"
    home = "index.html" if depth == 0 else "../" * depth + "index.html"
    archive = "archive.html" if depth == 0 else "../" * depth + "archive.html"
    about = "about.html" if depth == 0 else "../" * depth + "about.html"
    changelog = "changelog.html" if depth == 0 else "../" * depth + "changelog.html"
    subscribe = "subscribe.html" if depth == 0 else "../" * depth + "subscribe.html"
    feed = "feed.xml" if depth == 0 else "../" * depth + "feed.xml"
    research = f"{'../' * depth}topics/research.html" if depth else "topics/research.html"
    if depth == 0:
        topics, explore, stages = "topics/index.html", "explore/index.html", "explore/index.html#stages"
    elif depth == 1:
        if active == "explore":
            topics, explore, stages = "../topics/index.html", "index.html", "index.html#stages"
        elif active in {t["id"] for t in TOPICS} or active == "topics":
            topics, explore, stages = "index.html", "../explore/index.html", "../explore/index.html#stages"
        else:
            topics, explore, stages = "../topics/index.html", "../explore/index.html", "../explore/index.html#stages"
    else:
        topics, explore, stages = "../../topics/index.html", "../../explore/index.html", "../../explore/index.html#stages"

    def cur(name: str) -> str:
        return ' aria-current="page"' if active == name else ""

    topic_active = active in {"topics"} | {t["id"] for t in TOPICS}
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(META_DESCRIPTION)}"/>
  <meta name="color-scheme" content="dark light"/>
  <link rel="alternate" type="application/atom+xml" title="{html.escape(PROJECT_NAME)}" href="{feed}"/>
  <script>
  (function(){{try{{var t=localStorage.getItem('csw-theme');
  if(t!=='light'&&t!=='dark')t=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';
  document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();
  </script>
  <script src="{prefix}/theme.js" defer></script>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="{prefix}/site.css"/>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-header">
    <div class="wrap">
      <a class="brand" href="{home}">CompilerSutra <span>Weekly</span><span class="brand-tag">{html.escape(BRAND_TAG)}</span></a>
      <nav class="nav-desktop" aria-label="Primary">
        <a href="{home}"{cur("home")}>Latest</a>
        <a href="{explore}"{" aria-current=\"page\"" if active=="explore" else ""}>Explore</a>
        <a href="{topics}"{" aria-current=\"page\"" if topic_active else ""}>Topics</a>
        <a href="{research}">Papers</a>
        <a href="{archive}"{cur("archive")}>Archive</a>
        <a href="{subscribe}">Subscribe</a>
        <a href="{about}"{cur("about")}>About</a>
      </nav>
      <div class="header-actions">
        <a class="icon-btn" href="{html.escape(REPO_URL)}" rel="noopener noreferrer" title="GitHub">GitHub</a>
        <button type="button" class="icon-btn" id="theme-toggle" aria-pressed="false" aria-label="Switch to light theme">Theme</button>
        <button type="button" class="icon-btn nav-toggle" id="nav-toggle" aria-expanded="false" aria-controls="mobile-nav" aria-label="Open menu">Menu</button>
      </div>
    </div>
    <div class="mobile-nav" id="mobile-nav" hidden>
      <div class="wrap" aria-label="Mobile">
        <a href="{home}">Latest</a>
        <a href="{explore}">Explore</a>
        <a href="{topics}">Topics</a>
        <a href="{research}">Papers</a>
        <a href="{archive}">Archive</a>
        <a href="{subscribe}">Subscribe</a>
        <a href="{about}">About</a>
        <a href="{changelog}">Change log</a>
        <a href="{feed}">Atom feed</a>
        <a href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub</a>
        <a href="{html.escape(EDU_URL)}" rel="noopener noreferrer">CompilerSutra</a>
      </div>
    </div>
  </header>
  <div id="main">
  {body}
  </div>
  <footer class="site-footer">
    <div class="wrap">
      <div>© CompilerSutra · Apache-2.0 · {html.escape(CADENCE)}</div>
      <div>
        <a href="{subscribe}">Subscribe</a> ·
        <a href="{feed}">Feed</a> ·
        <a href="{changelog}">Change log</a> ·
        <a href="{html.escape(REPO_URL)}">Source</a> ·
        <a href="{html.escape(ISSUES_URL)}">Corrections</a>
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
