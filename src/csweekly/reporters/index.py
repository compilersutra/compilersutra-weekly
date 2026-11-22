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
    CLOUDFLARE_WEB_ANALYTICS_TOKEN,
    CONTACT_NOTE,
    EDU_URL,
    HERO_KICKER,
    HERO_LEDE,
    HERO_TITLE,
    ISSUES_URL,
    META_DESCRIPTION,
    NEWSLETTER_FORM_LABEL,
    NEWSLETTER_FORM_URL,
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
        "| Edition | Window |",
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
    for stale in ("feed.xml", "feed.xsl"):
        old = site_dir / stale
        if old.is_file():
            old.unlink()
        asset_old = assets_dst / stale
        if asset_old.is_file():
            asset_old.unlink()
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
    _write_sitemap_and_robots(site_dir, metas)
    return archive


def _abs_page_url(rel: str) -> str:
    base = PAGES_URL.rstrip("/")
    path = rel.lstrip("/")
    if path in {"", "index.html"}:
        return f"{base}/"
    return f"{base}/{path}"


def _write_sitemap_and_robots(site_dir: Path, metas: list[IssueMeta]) -> None:
    """Emit sitemap.xml + robots.txt for Search Console.

    Keep this lean: only stable public pages Google can fetch quickly.
    Exclude changelog.html (multi‑MB interactive dataset) — it often causes
    "Sitemap can be read, but has errors" when Googlebot times out.
    """
    latest_mod = metas[0].date if metas else None
    # (path, lastmod)
    urls: list[tuple[str, str | None]] = [
        ("index.html", latest_mod),
        ("archive.html", latest_mod),
        ("about.html", latest_mod),
        ("subscribe.html", latest_mod),
        ("topics/index.html", latest_mod),
        ("explore/index.html", latest_mod),
    ]
    for topic in TOPICS:
        urls.append((f"topics/{topic['id']}.html", latest_mod))
    for stage in STAGES:
        urls.append((f"explore/stage-{_slug(stage)}.html", latest_mod))
    # Domains that usually have content in editions; skip empty niche shells.
    for domain in ("CPU", "GPU", "AI / ML", "Languages", "Research"):
        urls.append((f"explore/domain-{_slug(domain)}.html", latest_mod))
    for meta in metas:
        urls.append((meta.href_html, meta.date))

    seen: set[str] = set()
    body_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for rel, lastmod in urls:
        loc = _abs_page_url(rel)
        if loc in seen:
            continue
        seen.add(loc)
        body_parts.append("  <url>")
        body_parts.append(f"    <loc>{html.escape(loc)}</loc>")
        if lastmod:
            body_parts.append(f"    <lastmod>{html.escape(lastmod)}</lastmod>")
        body_parts.append("  </url>")
    body_parts.append("</urlset>")
    body_parts.append("")
    (site_dir / "sitemap.xml").write_text("\n".join(body_parts), encoding="utf-8")

    sitemap_abs = _abs_page_url("sitemap.xml")
    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /changelog.html\n"
        "\n"
        f"Sitemap: {sitemap_abs}\n"
    )
    (site_dir / "robots.txt").write_text(robots, encoding="utf-8")


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
    from csweekly.reporters.taxonomy_ui import project_color_key

    payload = _load_changelog(latest.path) if latest else {}
    featured = ""
    recent = ""
    latest_block = '<p class="topic-empty">No editions yet.</p>'
    if latest:
        num = f"#{latest.issue_number:03d}" if latest.issue_number else latest.date
        high = list(payload.get("high_signal") or [])
        dive = payload.get("deep_dive")
        hs_listed = len(high)
        dive_n = 1 if dive else 0
        # Prefer explicit listed+dive accounting over the aggregated high_signal stat.
        hs_stat = int(latest.stats.get("high_signal") or 0)
        wk = int(latest.stats.get("worth_knowing") or 0)
        pub_human = format_issue_date(latest.date)
        from csweekly.reporters.publication import briefing_cards_from_payload

        home_cards = briefing_cards_from_payload(payload, limit=5)
        if home_cards:
            overview = (
                "<div class='briefing-grid home-briefing'>"
                + "".join(
                    "<article class='briefing-card compact'>"
                    f"<p class='brief-kicker'>{html.escape(c['kicker'])}</p>"
                    f"<h3>{html.escape(c['headline'])}</h3>"
                    f"<p class='brief-takeaway'>{html.escape(c['takeaway'])}</p>"
                    "</article>"
                    for c in home_cards
                )
                + "</div>"
            )
        else:
            bullets = payload.get("week_overview") or []
            overview = (
                "<ol class='briefing-list'>"
                + "".join(f"<li class='briefing-item'>{html.escape(b)}</li>" for b in bullets[:5])
                + "</ol>"
                if bullets
                else ""
            )
        cover_bits = [f"{hs_listed} listed high-signal"]
        if dive_n:
            cover_bits.append(f"{dive_n} deep dive")
        if hs_stat and hs_stat != hs_listed + dive_n:
            cover_bits.append(f"{hs_stat} curated total")
        cover_bits.append(f"{wk} worth knowing")
        latest_block = f"""
        <div class="latest-card">
          <p class="hero-kicker">Latest edition · {html.escape(num)} · {html.escape(pub_human)}</p>
          <h2>Edition {html.escape(num)}</h2>
          <div class="stat-row" aria-label="Edition counts">
            <div class="stat"><strong>{hs_listed}</strong><span>High signal</span></div>
            <div class="stat"><strong>{dive_n}</strong><span>Deep dive</span></div>
            <div class="stat"><strong>{wk}</strong><span>Worth knowing</span></div>
          </div>
          <p class="latest-cover">{html.escape(" · ".join(cover_bits))}</p>
          <p class="muted">{html.escape(HERO_LEDE)}</p>
          {overview}
          <div class="cta-row">
            <a class="btn btn-primary" href="{html.escape(latest.href_html)}">Read this week&rsquo;s edition →</a>
            <a class="btn btn-ghost" href="{html.escape(NEWSLETTER_FORM_URL)}" rel="noopener noreferrer" target="_blank">{html.escape(NEWSLETTER_FORM_LABEL)}</a>
          </div>
        </div>
"""
        feat = dive or (high[0] if high else None)
        feat_id = (feat or {}).get("story_id") or (feat or {}).get("id")
        if feat:
            notes = feat.get("deep_dive_notes") or {}
            change = html.escape((feat.get("what_changed") or "")[:320])
            why_raw = (notes.get("implications") or feat.get("why_it_matters") or "")[:280]
            why = html.escape(why_raw)
            src = "#"
            stories = feat.get("stories") or []
            if stories:
                src = html.escape(stories[0].get("source_url") or "#")
            proj = project_color_key(str(feat.get("project") or feat.get("category") or ""))
            featured = f"""
      <section class="wrap" style="padding:2rem 0 0.5rem" aria-labelledby="featured-heading">
        <h2 id="featured-heading" class="section-label">Deep dive</h2>
        <article class="feature-card" data-project="{html.escape(proj)}">
          <p class="card-kicker">Featured technical analysis</p>
          <h2>{html.escape((feat.get("title") or "")[:140])}</h2>
          {taxonomy_badges_html(feat)}
          <div class="callout callout-insight"><strong>What changed.</strong> {change}</div>
          <div class="callout callout-verified"><strong>Why engineers should care.</strong> {why}</div>
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
        remain = max(0, hs_listed - shown)
        cards = "".join(_group_html_card(g, depth=0) for g in grid_src)
        if cards:
            count_note = (
                f"Showing {shown} of {hs_listed} listed high-signal developments"
                + (f" · {remain} more in the full edition" if remain else "")
                + (" · deep dive featured above" if dive else "")
            )
            recent = f"""
      <section class="wrap" style="padding:1.5rem 0 0.5rem" aria-labelledby="latest-dev">
        <h2 id="latest-dev" class="section-label">This week&rsquo;s engineering highlights</h2>
        <p class="muted">{html.escape(count_note)}</p>
        <div class="story-grid">{cards}</div>
        <p class="muted" style="margin-top:0.85rem">
          <a href="{html.escape(latest.href_html)}">Open the full edition for every selected story →</a>
        </p>
      </section>
"""

    domain_cards = "\n".join(
        f"""<a class="bucket eco-bucket eco-{html.escape(str(t['id']))}" href="topics/{html.escape(str(t['id']))}.html">
  <strong>{html.escape(str(t['label']))}</strong>
  <span>{html.escape(str(t['blurb']))}</span>
</a>"""
        for t in TOPICS
        if t["id"] in {"llvm", "gcc", "mlir", "gpu", "ai", "research"}
    )
    items = _issue_rows(metas[:10], depth=0)
    body = f"""
  <main id="main">
    <section class="hero">
      <div class="wrap">
        <p class="hero-kicker">CompilerSutra Weekly</p>
        <h1>{html.escape(HERO_TITLE)}</h1>
        <p class="lede">{html.escape(HERO_LEDE)}</p>
        <div class="eco-row" aria-label="Compiler ecosystems">
          <span class="eco-pill eco-llvm">LLVM</span>
          <span class="eco-pill eco-gcc">GCC</span>
          <span class="eco-pill eco-mlir">MLIR</span>
          <span class="eco-pill eco-gpu">GPU</span>
          <span class="eco-pill eco-ai">AI Compilers</span>
          <span class="eco-pill eco-research">Research</span>
        </div>
      </div>
    </section>
    <div class="wrap" style="padding-top:1.75rem">
      <section class="panel" aria-labelledby="archive-heading">
        <h2 id="archive-heading">Archive</h2>
        <ul class="issue-list">{items if items else '<li class="topic-empty">No editions yet.</li>'}</ul>
      </section>
      <h2 class="section-label" style="margin-top:2rem">Explore by engineering domain</h2>
      <p class="muted" style="margin-bottom:0.85rem">
        Independent filters for project, compiler stage, and hardware —
        <a href="explore/index.html">open Explore</a>.
      </p>
      <div class="buckets">{domain_cards}</div>
    </div>
    <section class="wrap" style="padding:2rem 0 0.5rem" aria-labelledby="this-week-heading">
      <h2 id="this-week-heading" class="section-label">This week&rsquo;s edition</h2>
      {latest_block}
    </section>
    {featured}
    {recent}
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
                f"<span class='go'>{n} papers/items in latest edition →</span>"
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
    <p class="muted">Counts come from the latest curated edition — not every raw commit.</p>
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
    <p class="muted">Curated stories tagged with this {html.escape(kind)} across recent editions.</p>
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
  <h3><a href="../{html.escape(meta.href_html)}">{html.escape(num)} · full edition</a></h3>
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
    from csweekly.reporters.taxonomy_ui import project_color_key

    title = html.escape((g.get("title") or "")[:120])
    why = html.escape((g.get("why_it_matters") or "Impact not yet clear.")[:200])
    what = html.escape((g.get("what_changed") or "")[:160])
    tax = taxonomy_line(g)
    proj = project_color_key(str(g.get("project") or g.get("category") or ""))
    url = "#"
    stories = g.get("stories") or []
    if stories:
        url = html.escape(stories[0].get("source_url") or "#")
    if compact:
        return f"""<article class="story-row" data-project="{html.escape(proj)}">
  <h4><a href="{url}" rel="noopener noreferrer">{title}</a></h4>
  <p class="secondary">{why}</p>
  <div class="meta">{tax}</div>
</article>"""
    what_block = (
        f'<p class="card-summary"><strong>What changed.</strong> {what}</p>' if what else ""
    )
    return f"""<article class="story-card" data-project="{html.escape(proj)}">
  {taxonomy_badges_html(g)}
  <h4><a href="{url}" rel="noopener noreferrer">{title}</a></h4>
  {what_block}
  <p class="card-summary"><strong>Why it matters.</strong> {why}</p>
  <div class="card-meta-row"><a href="{url}" rel="noopener noreferrer">Primary source →</a></div>
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
    <h1 class="page-title">All editions</h1>
    {next_note}
    <div class="cta-row" style="margin-bottom:1rem">
      <a class="btn btn-ghost" href="{html.escape(NEWSLETTER_FORM_URL)}" rel="noopener noreferrer" target="_blank">{html.escape(NEWSLETTER_FORM_LABEL)}</a>
    </div>
    <section class="panel" style="margin-top:0.5rem">
      <ul class="issue-list">{items or "<li>No editions yet.</li>"}</ul>
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
    <p class="muted">{html.escape(CADENCE)} Editions stay at stable URLs under
    <code>issues/YYYY/YYYY-MM-DD.html</code>.</p>

    <h2 class="section-label">Publishing lifecycle</h2>
    <p class="muted">Raw data accumulates all week and is <strong>never</strong> the
    public newsletter by itself. Pipeline:</p>
    <ol class="muted">
      <li><strong>Collect</strong> (Sat→Fri) — idempotent raw facts into an edition</li>
      <li><strong>Freeze</strong> (end of Friday) — close the period</li>
      <li><strong>Process / review</strong> — normalize, cluster, editorial queue</li>
      <li><strong>Validate → publish</strong> (Saturday) — one immutable curated edition</li>
    </ol>
    <p class="muted">While the next edition is collecting, the site continues to show the
    last published edition. Late items after freeze go to the next edition or an
    explicit addendum — published editions are not silently rewritten.</p>

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
      <a class="btn btn-primary" href="{html.escape(NEWSLETTER_FORM_URL)}" rel="noopener noreferrer" target="_blank">{html.escape(NEWSLETTER_FORM_LABEL)}</a>
      <a class="btn btn-ghost" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub</a>
      <a class="btn btn-ghost" href="{html.escape(ISSUES_URL)}" rel="noopener noreferrer">Report a correction</a>
      <a class="btn btn-ghost" href="{html.escape(EDU_URL)}" rel="noopener noreferrer">CompilerSutra.com</a>
    </div>
  </main>
"""
    return _shell("About — CompilerSutra Weekly", body, active="about", depth=0)


def _page_subscribe() -> str:
    form = html.escape(NEWSLETTER_FORM_URL)
    body = f"""
  <main class="wrap article-narrow">
    <p class="hero-kicker">Subscribe</p>
    <h1 class="page-title">Get each Saturday edition</h1>
    <p class="lede">{html.escape(HERO_LEDE)}</p>
    <p class="muted">{html.escape(CADENCE)} Approximate reading time: 5–10 minutes.</p>

    <h2 class="section-label">Email signup</h2>
    <p class="muted">Use the <strong>same Google Form</strong> as
    <a href="{html.escape(EDU_URL)}" rel="noopener noreferrer">compilersutra.com</a>
    (Weekly Compiler Notes). Enter your email and submit — no separate list for this site.</p>
    <div class="cta-row" style="margin-top:1rem">
      <a class="btn btn-primary" href="{form}" rel="noopener noreferrer"
         target="_blank">{html.escape(NEWSLETTER_FORM_LABEL)}</a>
      <a class="btn btn-ghost" href="archive.html">Browse archive</a>
    </div>
    <ol class="muted subscribe-steps" style="margin-top:1rem">
      <li>Open the Google Form (button above).</li>
      <li>Enter your email and submit.</li>
      <li>You are on the CompilerSutra notes list used across the main site.</li>
    </ol>

    <h2 class="section-label">What you receive</h2>
    <ul class="muted">
      <li>One curated edition per week (Saturday publish on this site)</li>
      <li>High-signal stories + worth knowing + optional deep dive</li>
      <li>Primary source links (commits / papers) — not a raw commit dump</li>
    </ul>
  </main>
"""
    return _shell("Subscribe — CompilerSutra Weekly", body, active="subscribe", depth=0)


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


def _page_issue(meta: IssueMeta, md: str, prev_m: IssueMeta | None, next_m: IssueMeta | None) -> str:
    payload = _load_changelog(meta.path)
    num = f"#{meta.issue_number:03d}" if meta.issue_number else meta.date
    if payload.get("high_signal") or payload.get("groups"):
        content = _render_issue_html(meta, payload)
        toc_candidates = [
            ("top-three", "Top 3"),
            ("briefing", "Briefing"),
            ("featured", "Featured"),
            ("deep-dive", "Under the hood"),
            ("lessons", "Lessons"),
            ("worth-knowing", "Watchlist"),
            ("themes", "Themes"),
            ("worth-reading", "Research"),
            ("topic-index", "Index"),
        ]
        # Only link sections that actually rendered (e.g. skip Research when empty).
        toc_ids = [(i, l) for i, l in toc_candidates if f'id="{i}"' in content]
        toc_links = "".join(f'<a href="#{i}">{html.escape(l)}</a>' for i, l in toc_ids)
        toc = f'<nav class="toc" aria-label="On this page">{toc_links}</nav>' if toc_ids else ""
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
    projects = payload.get("stats", {}).get("projects") or ["LLVM", "GCC", "MLIR", "GPU"]
    chips = "".join(
        f'<span class="hero-chip">{html.escape(str(p).upper() if len(str(p)) <= 4 else str(p).title())}</span>'
        for p in projects[:6]
    )
    body = f"""
  {_topic_bar(depth=2)}
  <article class="article issue-article" id="main">
    <div class="issue-nav">{" · ".join(nav_bits)}</div>
    <header class="issue-hero">
      <p class="hero-kicker">CompilerSutra Weekly · Edition {html.escape(num)}</p>
      <h1 class="page-title">The week in compiler engineering</h1>
      <p class="hero-date muted">{html.escape(format_issue_date(meta.date))} · {html.escape(meta.window)}</p>
      <div class="hero-chips" aria-label="Projects covered">{chips}</div>
      <p class="lede">Understand what changed in LLVM, GCC, MLIR and GPU compilers,
        why it matters, and how it works under the hood.</p>
    </header>
    {toc}
    <div class="issue-body">
    {content}
    </div>
  </article>
"""
    return _shell(f"{num} — CompilerSutra Weekly", body, active="home", depth=2)


def _render_issue_html(meta: IssueMeta, payload: dict) -> str:
    from csweekly.brand import EDITORIAL_INVARIANT
    from csweekly.reporters.publication import (
        briefing_cards_from_payload,
        coverage_tier,
        editorial_score_legend,
        engineering_lessons,
        watchlist_bucket,
        WATCHLIST_LABELS,
    )

    parts: list[str] = []
    cards = briefing_cards_from_payload(payload, limit=5)
    if cards:
        parts.append(_top_three_html(cards[:3]))
        parts.append(_briefing_cards_html(cards))

    high = payload.get("high_signal") or []
    deep = payload.get("deep_dive")
    featured = list(high[:4])
    deep_id = (deep or {}).get("story_id") or (deep or {}).get("id")
    featured = [
        g
        for g in featured
        if (g.get("story_id") or g.get("id")) != deep_id
    ][:4]
    if featured:
        cards_html = "".join(_issue_story_card(g, prominent=True) for g in featured)
        parts.append(
            f'<section id="featured" class="issue-section section-featured">'
            f"<h2>Featured engineering changes</h2>"
            f'<p class="section-lede muted">Technical details and primary commits.</p>'
            f'<div class="story-grid">{cards_html}</div>'
            f"</section>"
        )

    if deep:
        parts.append(_deep_dive_html(deep))

    lesson_src = ([deep] if deep else []) + featured
    lessons = engineering_lessons([g for g in lesson_src if g], limit=4)
    if lessons:
        parts.append(_lessons_html(lessons))

    worth = payload.get("worth_knowing") or []
    feat_ids = {(g.get("story_id") or g.get("id")) for g in featured}
    if deep_id:
        feat_ids.add(deep_id)
    worth = [g for g in worth if (g.get("story_id") or g.get("id")) not in feat_ids]
    quick = [g for g in worth if coverage_tier(g) != "watchlist"]
    watch = [g for g in worth if coverage_tier(g) == "watchlist"]

    signal_blocks = []
    if quick:
        signal_blocks.append(
            "<h3 class='signal-tier'>Quick signals</h3>"
            '<p class="muted">Relevant, partially investigated — open the commit for details.</p>'
            f'<div class="watch-rows">{"".join(_watch_row(g) for g in quick)}</div>'
        )
    if watch:
        buckets: dict[str, list] = {
            "needs_inspection": [],
            "potentially_important": [],
            "low_priority": [],
        }
        for g in watch:
            buckets[watchlist_bucket(g)].append(g)
        for key in ("needs_inspection", "potentially_important", "low_priority"):
            items = buckets[key]
            if not items:
                continue
            signal_blocks.append(
                f"<h3 class='signal-tier'>{html.escape(WATCHLIST_LABELS[key])}</h3>"
                f'<div class="watch-rows">{"".join(_watch_row(g) for g in items)}</div>'
            )
    if signal_blocks:
        parts.append(
            f'<section id="worth-knowing" class="issue-section section-signals">'
            f"<h2>What engineers should watch</h2>"
            f'<p class="section-lede muted">Unresolved or lightly inspected signals — '
            f"expand a row for source and context.</p>"
            f"{''.join(signal_blocks)}</section>"
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
            f'<p class="muted">Project index only — details are in the sections above.</p>'
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
        '<li><a href="../../topics/research.html">Research papers</a></li>'
        '<li><a href="../../archive.html">Archive</a></li>'
        "</ul>"
        f'<p class="muted" style="margin-top:1.5rem"><strong>Editorial invariant.</strong> '
        f"{html.escape(EDITORIAL_INVARIANT)} "
        "We do not invent benchmarks or completion status.</p>"
        "</section>"
    )
    return "\n".join(parts)


def _top_three_html(cards: list[dict]) -> str:
    items = []
    for c in cards[:3]:
        num = f"{c['index'] + 1:02d}"
        # Complete reason — never mid-sentence clip; briefing carries what-changed.
        reason = (c.get("reason") or c.get("takeaway") or "").strip()
        meta_bits = []
        proj = str(c.get("project") or "")
        if proj:
            meta_bits.append(proj.upper() if len(proj) <= 4 else str(proj).title())
        if c.get("stage"):
            meta_bits.append(str(c["stage"]).replace("Runtime & Toolchain", "Runtime"))
        for t in (c.get("targets") or [])[:1]:
            meta_bits.append(str(t))
        cat = " · ".join(meta_bits) or "Compiler"
        items.append(
            f"""<article class="top3-card">
  <span class="brief-num">{html.escape(num)}</span>
  <div>
    <p class="info-kind">Why it matters</p>
    <h3><a href="#{html.escape(c["anchor"])}">{html.escape(c["headline"])}</a></h3>
    <p class="top3-reason">{html.escape(reason)}</p>
    <p class="brief-meta-line"><span>{html.escape(cat)}</span>
      <a class="brief-jump" href="#briefing">In briefing ↓</a></p>
  </div>
</article>"""
        )
    return (
        '<section id="top-three" class="issue-section section-top3">'
        "<h2>The 3 changes worth knowing</h2>"
        '<p class="section-lede muted">Editorial selection — why these three deserve attention. '
        "Technical detail follows in the briefing.</p>"
        f'<div class="top3-grid">{"".join(items)}</div></section>'
    )


def _lessons_html(lessons: list[dict]) -> str:
    items = []
    for i, lesson in enumerate(lessons, 1):
        items.append(
            f"""<article class="lesson-card">
  <span class="brief-num">{i:02d}</span>
  <div>
    <h3><a href="#{html.escape(lesson["anchor"])}">{html.escape(lesson["headline"])}</a></h3>
    <p class="brief-line">{html.escape(lesson["lesson"])}</p>
  </div>
</article>"""
        )
    return (
        '<section id="lessons" class="issue-section section-lessons">'
        "<h2>Engineering lessons</h2>"
        '<p class="section-lede muted">What developers can take from this week’s '
        "changes — grounded in the primary commits.</p>"
        f'<div class="lesson-list">{"".join(items)}</div></section>'
    )


def _watch_row(g: dict) -> str:
    from csweekly.processors.editorial import _clip_words
    from csweekly.reporters.publication import (
        editorial_headline,
        engineering_takeaway,
        sanitize_group_for_display,
    )
    from csweekly.reporters.taxonomy_ui import evidence_confidence

    g = sanitize_group_for_display(g)
    anchor = _story_anchor(g)
    title = html.escape(editorial_headline(g))
    why = html.escape(_clip_words(engineering_takeaway(g), 180))
    limits = html.escape(
        (g.get("uncertainty_note") or "Broader impact is not established from the commit message alone.")
    )
    ev_label, ev_slug = evidence_confidence(g)
    stories = g.get("stories") or []
    primary = stories[0] if stories else {}
    sha = html.escape((primary.get("related_ref") or "")[:8] or "link")
    url = html.escape(primary.get("source_url") or "#")
    proj = str(g.get("project") or g.get("category") or "")
    stage = ((g.get("stages") or [""])[0] or "").replace("Runtime & Toolchain", "Runtime")
    component = " · ".join(
        b
        for b in (
            proj.upper() if len(proj) <= 4 else proj.title(),
            stage,
            *((g.get("hardware_targets") or [])[:1]),
        )
        if b
    )
    return f"""<details class="watch-row" id="{html.escape(anchor)}" data-evidence="{html.escape(ev_slug)}">
  <summary>
    <span class="watch-summary-main">
      <span class="watch-title">{title}</span>
      <span class="watch-meta">{html.escape(component)}</span>
    </span>
    <span class="watch-status evidence-dot evidence-{html.escape(ev_slug)}">{html.escape(ev_label)}</span>
    <span class="watch-chevron" aria-hidden="true"></span>
  </summary>
  <div class="watch-expand">
    <p class="brief-line">{why}</p>
    <p class="muted"><strong>Limitations.</strong> {limits}</p>
    <p class="meta">Source: <a href="{url}" rel="noopener noreferrer"><code>{sha}</code></a></p>
  </div>
</details>"""


def _briefing_cards_html(cards: list[dict]) -> str:
    from csweekly.processors.editorial import _clip_words

    top_ids = {c.get("anchor") for c in cards[:3]}
    items = []
    for c in cards:
        meta_bits = []
        proj = str(c.get("project") or "")
        if proj:
            meta_bits.append(proj.upper() if len(proj) <= 4 else str(proj).title())
        if c.get("stage"):
            stage = str(c["stage"]).replace("Runtime & Toolchain", "Runtime")
            meta_bits.append(stage)
        for t in (c.get("targets") or [])[:1]:
            meta_bits.append(str(t))
        ev = html.escape(c.get("evidence_label") or "Unverified")
        ev_slug = html.escape(c.get("evidence_slug") or "unverified")
        sha = html.escape(c.get("sha") or "link")
        src = html.escape(c.get("source_url") or "#")
        num = f"{c['index'] + 1:02d}"
        # Prefer what-changed summary; never replay the Top 3 reason line.
        summary = _clip_words(c.get("summary") or "", 200)
        extra = ""
        if c.get("anchor") not in top_ids:
            takeaway = _clip_words(c.get("takeaway") or "", 140)
            # Skip if takeaway is just summary + boilerplate.
            if (
                takeaway
                and takeaway != summary
                and not takeaway.startswith(summary[: min(48, len(summary))])
            ):
                extra = f'<p class="brief-line brief-why">{html.escape(takeaway)}</p>'
        meta_line = " · ".join(meta_bits)
        items.append(
            f"""<article class="brief-card" data-evidence="{ev_slug}">
  <span class="brief-num" aria-hidden="true">{html.escape(num)}</span>
  <div class="brief-body">
    <p class="info-kind info-kind-tech">What changed</p>
    <h3><a href="#{html.escape(c["anchor"])}">{html.escape(c["headline"])}</a></h3>
    <p class="brief-line">{html.escape(summary)}</p>
    {extra}
    <p class="brief-meta-line">
      <span>{html.escape(meta_line)}</span>
      <span class="evidence-dot evidence-{ev_slug}">{ev}</span>
      <a href="{src}" rel="noopener noreferrer"><code>{sha}</code></a>
      <a class="brief-jump" href="#{html.escape(c["anchor"])}">Story →</a>
    </p>
  </div>
</article>"""
        )
    n = len(cards)
    return (
        f'<section id="briefing" class="issue-section section-briefing">'
        f'<div class="section-head">'
        f"<h2>Five-minute briefing</h2>"
        f'<p class="section-count muted">{n} stor{"y" if n == 1 else "ies"}</p>'
        f"</div>"
        f'<p class="section-lede muted">Technical explanation — what the patches change, '
        f"with primary sources.</p>"
        f'<div class="brief-cards">{"".join(items)}</div></section>'
    )


def _story_anchor(g: dict) -> str:
    sid = g.get("story_id") or g.get("id") or _slug(g.get("title") or "story")
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(sid))[:80]


def _issue_story_card(g: dict, *, prominent: bool, watchlist: bool = False) -> str:
    from csweekly.reporters.publication import (
        editorial_headline,
        engineering_takeaway,
        featured_summary,
        sanitize_group_for_display,
        score_caption,
    )
    from csweekly.reporters.taxonomy_ui import evidence_confidence, project_color_key

    g = sanitize_group_for_display(g)
    anchor = _story_anchor(g)
    title = html.escape(editorial_headline(g))
    what = html.escape(featured_summary(g, limit=320))
    why = html.escape(engineering_takeaway(g))
    uncertain = html.escape(g.get("uncertainty_note") or "")
    score = g.get("impact_score")
    pick = score_caption(score if isinstance(score, (int, float)) else None)
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
    proj = project_color_key(str(g.get("project") or g.get("category") or ""))
    cls = "story-card issue-story" if prominent else "story-row"
    if watchlist:
        cls += " watchlist-item"
    files = []
    for s in stories[:3]:
        for p in (s.get("paths") or [])[:4]:
            if p not in files:
                files.append(p)
    from csweekly.reporters.publication import implementation_explanation, primary_commit

    details_bits = []
    impl = implementation_explanation(g)
    commit = primary_commit(g)
    sha = html.escape(commit.get("short") or "commit")
    curl = html.escape(commit.get("url") or "#")
    size = html.escape(commit.get("size") or "")
    size_bit = f" · {size}" if size else ""
    details_bits.append(f"<p><strong>Implementation.</strong> {html.escape(impl)}</p>")
    details_bits.append(
        f'<p class="dive-commit">Primary commit: '
        f'<a href="{curl}" rel="noopener noreferrer"><code>{sha}</code></a>{size_bit}</p>'
    )
    if files:
        details_bits.append(
            f'<p class="muted"><strong>Surface.</strong> '
            f'{html.escape(str(len(files)))} listed paths'
            f'{" (expand source for full tree)" if len(files) >= 4 else ""}.</p>'
        )
    who = ", ".join(g.get("who_should_care") or [])
    if who:
        details_bits.append(f"<p><strong>Who should care.</strong> {html.escape(who)}</p>")
    if uncertain:
        details_bits.append(
            f'<div class="callout callout-warning"><strong>Limitations.</strong> {uncertain}</div>'
        )
    details = (
        '<details class="story-details"><summary>Technical details</summary>'
        f"{''.join(details_bits)}</details>"
    )
    ev_label, ev_slug = evidence_confidence(g)
    # Compact labels: project · stage · target (no badge wall)
    fields_proj = (g.get("project") or g.get("category") or "").strip()
    fields_stage = ((g.get("stages") or [""])[0] or "").replace("Runtime & Toolchain", "Runtime")
    fields_target = ((g.get("hardware_targets") or [""])[0] or "")
    label_bits = [b for b in (fields_proj.upper() if len(fields_proj) <= 4 else fields_proj.title(),
                              fields_stage, fields_target) if b]
    label_line = html.escape(" · ".join(label_bits))
    if prominent:
        size_show = f" · {size}" if size else ""
        # Keep editorial score out of the card face — details only, if present.
        if pick:
            details_bits.insert(
                0, f'<p class="muted featured-rank">{html.escape(pick)}</p>'
            )
            details = (
                '<details class="story-details"><summary>Technical details</summary>'
                f"{''.join(details_bits)}</details>"
            )
        body = f"""  <header class="featured-head">
    <span class="badge tax-evidence evidence-{html.escape(ev_slug)}">{html.escape(ev_label)}</span>
    <p class="card-labels">{label_line}</p>
  </header>
  <p class="info-kind info-kind-tech">Technical explanation</p>
  <h3>{title}</h3>
  <p class="what-changed">{what}</p>
  <p class="meta card-source">
    <a href="{primary_url}" rel="noopener noreferrer"><code>{primary_sha or 'link'}</code></a>{size_show}
  </p>
  {details}"""
    elif watchlist:
        body = f"""  <p class="card-labels">{label_line}</p>
  <p class="secondary">{why}</p>
  <p class="muted watchlist-note">Source not fully inspected — confirm in the linked commit.</p>
  <p class="meta"><a href="{primary_url}" rel="noopener noreferrer"><code>{primary_sha or 'link'}</code></a>
    · <span class="evidence-dot evidence-{html.escape(ev_slug)}">{html.escape(ev_label)}</span></p>"""
    else:
        body = f"""  <p class="card-labels">{label_line}</p>
  <p class="secondary">{why}</p>
  <p class="meta"><a href="{primary_url}" rel="noopener noreferrer"><code>{primary_sha or 'link'}</code></a>
    · <span class="evidence-dot evidence-{html.escape(ev_slug)}">{html.escape(ev_label)}</span></p>"""
    return f"""<article class="{cls}" id="{html.escape(anchor)}" data-project="{html.escape(proj)}" data-evidence="{html.escape(ev_slug)}">
  {body}
  {related_block if prominent else ""}
</article>"""


def _deep_dive_html(g: dict) -> str:
    from csweekly.reporters.publication import (
        deep_dive_sections,
        editorial_headline,
        primary_commit,
        sanitize_group_for_display,
    )
    from csweekly.reporters.taxonomy_ui import evidence_confidence, project_color_key

    g = sanitize_group_for_display(g)
    title = html.escape(editorial_headline(g))
    anchor = _story_anchor(g)
    commit = primary_commit(g)
    sources = []
    for s in (g.get("stories") or [])[:8]:
        sha = html.escape((s.get("related_ref") or "")[:8])
        url = html.escape(s.get("source_url") or "#")
        summary = html.escape((s.get("summary") or "")[:120])
        sources.append(
            f'<li><a href="{url}" rel="noopener noreferrer"><code>{sha}</code></a> — {summary}</li>'
        )
    hw = ", ".join((g.get("hardware_targets") or [])[:3]) or "see paths"
    notes = g.get("deep_dive_notes") or {}
    ev_label, ev_slug = evidence_confidence(g)
    proj = project_color_key(str(g.get("project") or g.get("category") or ""))
    section_html = []
    sha = html.escape(commit.get("short") or "commit")
    url = html.escape(commit.get("url") or "#")
    size = html.escape(commit.get("size") or "")
    commit_link = (
        f'<a href="{url}" rel="noopener noreferrer"><code>{sha}</code></a>'
    )
    for sid, heading, body in deep_dive_sections(g):
        if sid == "implementation":
            size_bit = f" · {size}" if size else ""
            # Drop trailing "Open the primary commit…" — the hyperlink covers that.
            prose = re.sub(
                r"\s*Open the primary commit for the exact hunks[^.]*\.\s*$",
                "",
                body,
            ).strip()
            body_html = (
                f"<p>{html.escape(prose)}</p>"
                f'<p class="dive-commit">Primary commit: {commit_link}{size_bit}</p>'
            )
        elif sid == "reproduce" and commit.get("short"):
            # Turn bare sha mentions into the same hyperlink.
            linked = html.escape(body)
            if commit.get("short"):
                linked = linked.replace(
                    html.escape(commit["short"]),
                    commit_link,
                )
            body_html = f"<p>{linked}</p>"
        else:
            body_html = f"<p>{html.escape(body)}</p>"
        section_html.append(
            f'<div class="dive-section" id="dive-{html.escape(sid)}">'
            f"<h4>{html.escape(heading)}</h4>"
            f"{body_html}</div>"
        )
    dive_labels = " · ".join(
        b
        for b in (
            (g.get("project") or g.get("category") or "").upper()
            if len(str(g.get("project") or g.get("category") or "")) <= 4
            else str(g.get("project") or g.get("category") or "").title(),
            ((g.get("stages") or [""])[0] or "").replace("Runtime & Toolchain", "Runtime"),
            hw if hw != "see paths" else "",
        )
        if b
    )
    return f"""<section id="deep-dive" class="issue-section deep-dive section-dive">
  <h2>Under the hood</h2>
  <p class="section-lede muted">Technical explanation with evidence —
    problem → implementation → validation. Unanswered questions stay marked unknown.</p>
  <article class="dive-panel" id="{html.escape(anchor)}" data-project="{html.escape(proj)}">
    <p class="info-kind info-kind-evidence">Evidence-bound deep dive</p>
    <p class="card-kicker-row">
      <span class="badge tax-evidence evidence-{html.escape(ev_slug)}">{html.escape(ev_label)}</span>
      <span class="card-labels">{html.escape(dive_labels)}</span>
    </p>
    <h3>{title}</h3>
    <p class="muted dive-confidence">Confidence {html.escape(ev_label)}
      ({html.escape(str(notes.get("confidence") or "unknown"))};
      fact-check {html.escape(str(notes.get("factcheck") or "n/a"))})</p>
    <div class="dive-sections">
      {''.join(section_html)}
    </div>
    <details class="story-details dive-sources">
      <summary>Primary sources ({len(sources)})</summary>
      <ul class="source-list">{''.join(sources)}</ul>
    </details>
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
        num = f"#{m.issue_number:03d}" if m.issue_number else "Weekly edition"
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
    subscribe = html.escape(NEWSLETTER_FORM_URL)
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
    search_index = json.dumps(
        [
            {"label": "Latest edition", "href": home, "hint": "Home"},
            {"label": "Explore", "href": explore, "hint": "Filters"},
            {"label": "Topics", "href": topics, "hint": "Ecosystems"},
            {"label": "Research papers", "href": research, "hint": "Papers"},
            {"label": "Archive", "href": archive, "hint": "Editions"},
            {"label": "Change log", "href": changelog, "hint": "Full dataset"},
            {"label": "About", "href": about, "hint": "How it works"},
            {"label": "Subscribe", "href": NEWSLETTER_FORM_URL, "hint": "Email"},
            {"label": "GitHub repository", "href": REPO_URL, "hint": "Source"},
        ],
        ensure_ascii=True,
    )
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(META_DESCRIPTION)}"/>
  <meta name="color-scheme" content="dark light"/>
  <script>
  (function(){{try{{var t=localStorage.getItem('csw-theme');
  if(t!=='light'&&t!=='dark')t=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';
  document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();
  </script>
  <script src="{prefix}/theme.js" defer></script>
  <script src="{prefix}/ui.js" defer></script>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="{prefix}/site.css"/>
</head>
<body>
  <div class="read-progress" id="read-progress" hidden aria-hidden="true"></div>
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
        <a href="{subscribe}" rel="noopener noreferrer" target="_blank">Subscribe</a>
        <a href="{about}"{cur("about")}>About</a>
      </nav>
      <div class="header-actions">
        <button type="button" class="icon-btn search-trigger" id="search-open" aria-label="Open search (Control K)">Search <span class="kbd">Ctrl K</span></button>
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
        <a href="{subscribe}" rel="noopener noreferrer" target="_blank">Subscribe</a>
        <a href="{about}">About</a>
        <a href="{changelog}">Change log</a>
        <a href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub</a>
        <a href="{html.escape(EDU_URL)}" rel="noopener noreferrer">CompilerSutra</a>
      </div>
    </div>
  </header>
  <div id="main">
  {body}
  </div>
  <div class="search-backdrop" id="site-search" hidden>
    <div class="search-panel" role="dialog" aria-modal="true" aria-label="Site search">
      <input id="site-search-input" type="search" placeholder="Jump to a page or section…" autocomplete="off" aria-autocomplete="list" aria-controls="site-search-results"/>
      <ul class="search-results" id="site-search-results" role="listbox"></ul>
    </div>
  </div>
  <script type="application/json" id="site-search-index">{search_index}</script>
  <footer class="site-footer">
    <div class="wrap">
      <div>© CompilerSutra · Apache-2.0 · {html.escape(CADENCE)}</div>
      <div>
        <a href="{subscribe}" rel="noopener noreferrer" target="_blank">Subscribe</a> ·
        <a href="{changelog}">Change log</a> ·
        <a href="{html.escape(REPO_URL)}">Source</a> ·
        <a href="{html.escape(ISSUES_URL)}">Corrections</a>
      </div>
    </div>
  </footer>
  {_analytics_snippet()}
</body>
</html>
"""


def _analytics_snippet() -> str:
    """Optional Cloudflare Web Analytics beacon (cookieless)."""
    token = CLOUDFLARE_WEB_ANALYTICS_TOKEN
    if not token:
        return ""
    # Token is alphanumeric; still escape for attribute safety.
    safe = html.escape(token, quote=True)
    return (
        "<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
        f"data-cf-beacon='{{\"token\": \"{safe}\"}}'></script>\n"
    )


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
