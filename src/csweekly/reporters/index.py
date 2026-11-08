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
from csweekly.brand import EDU_URL, PAGES_URL, PROJECT_NAME, REPO_URL
from csweekly.reporters.mdhtml import markdown_to_html

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
    files = sorted(reports_dir.glob("**/*.md"), reverse=True)
    return [p for p in files if p.name != "README.md" and p.parent.name != "archive"]


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
        hs = int(latest.stats.get("high_signal") or 0)
        wk = int(latest.stats.get("worth_knowing") or 0)
        bullets = payload.get("week_overview") or []
        overview = ""
        if bullets:
            overview = "<ul class='overview-list'>" + "".join(
                f"<li>{html.escape(b)}</li>" for b in bullets[:5]
            ) + "</ul>"
        latest_block = f"""
        <div class="latest-card">
          <p class="hero-kicker">This week</p>
          <h2>Issue {html.escape(num)}</h2>
          <p class="latest-meta">{html.escape(latest.date)} · {html.escape(latest.window)}</p>
          <p class="latest-cover">{hs} high signal · {wk} worth knowing</p>
          {overview}
          <div class="cta-row">
            <a class="btn btn-primary" href="{html.escape(latest.href_html)}">Read latest issue →</a>
            <a class="btn btn-ghost" href="explore/index.html">Explore ecosystem</a>
            <a class="btn btn-ghost" href="archive.html">Browse archive</a>
          </div>
        </div>
"""
        feat = payload.get("deep_dive") or (payload.get("high_signal") or [None])[0]
        if feat:
            why = html.escape((feat.get("why_it_matters") or "")[:220])
            what = html.escape((feat.get("what_changed") or feat.get("title") or "")[:240])
            who = html.escape(", ".join(feat.get("who_should_care") or [])[:140])
            src = "#"
            stories = feat.get("stories") or []
            if stories:
                src = html.escape(stories[0].get("source_url") or "#")
            badges = "".join(
                f'<span class="badge">{html.escape(str(b))}</span>'
                for b in (
                    [feat.get("change_type")]
                    + (feat.get("stages") or [])[:1]
                    + (feat.get("domains") or [])[:1]
                )
                if b
            )
            featured = f"""
      <section class="wrap" style="padding:2rem 0 0.5rem" aria-labelledby="featured-heading">
        <p class="hero-kicker">Featured development</p>
        <h2 id="featured-heading" class="section-label">A compiler change worth understanding</h2>
        <article class="feature-card">
          <h2>{html.escape((feat.get("title") or "")[:140])}</h2>
          <div class="badge-row">{badges}</div>
          <p class="secondary"><strong>What changed.</strong> {what}</p>
          <p class="secondary"><strong>Why it matters.</strong> {why}</p>
          <p class="muted"><strong>Who should care.</strong> {who or "Compiler engineers"}</p>
          <div class="cta-row" style="margin-top:0.85rem">
            <a class="btn btn-primary" href="{html.escape(latest.href_html)}#deep-dive">Read technical analysis →</a>
            <a class="btn btn-ghost" href="{src}" rel="noopener noreferrer">Original source</a>
          </div>
        </article>
      </section>
"""
        cards = "".join(
            _group_html_card(g, depth=0) for g in (payload.get("high_signal") or [])[:6]
        )
        if cards:
            recent = f"""
      <section class="wrap" style="padding:1.5rem 0 0.5rem" aria-labelledby="latest-dev">
        <h2 id="latest-dev" class="section-label">Latest developments</h2>
        <p class="muted">High-signal items from the current issue.</p>
        <div class="story-grid">{cards}</div>
      </section>
"""

    domain_cards = "\n".join(
        f"""<a class="bucket" href="topics/{html.escape(str(t['id']))}.html">
  <strong>{html.escape(str(t['label']))}</strong>
  <span>{html.escape(str(t['blurb']))}</span>
  <span class="go">Open →</span>
</a>"""
        for t in TOPICS
    )
    items = _issue_rows(metas[:10], depth=0)
    body = f"""
  {_topic_bar(depth=0)}
  <main>
    <section class="hero">
      <div class="wrap">
        <p class="hero-kicker">Compiler ecosystem intelligence</p>
        <h1>The compiler changes worth understanding.</h1>
        <p class="tagline">The compiler ecosystem, explained every week.</p>
        <p class="lede">One weekly view of what is changing across compilers, runtimes,
        hardware targets and research — selected and explained for engineers.</p>
        {latest_block}
      </div>
    </section>
    {featured}
    <div class="wrap" style="padding-top:2rem">
      <h2 class="section-label">Explore the compiler pipeline</h2>
      <p class="muted" style="margin-bottom:0.85rem">An organizing model — not a claim every compiler looks the same.
        <a href="explore/index.html">View all filters →</a></p>
      <div class="pipeline">
        <a class="pipeline-step" href="explore/stage-frontend.html"><strong>01 Frontend</strong><span>Parsing · types · semantics</span></a>
        <a class="pipeline-step" href="explore/stage-middle-end.html"><strong>02 Middle-end</strong><span>IR · analysis · optimization</span></a>
        <a class="pipeline-step" href="explore/stage-backend.html"><strong>03 Backend</strong><span>CodeGen · register allocation</span></a>
        <a class="pipeline-step" href="explore/stage-runtime-toolchain.html"><strong>04 Runtime</strong><span>JIT · linkers · toolchains</span></a>
      </div>
      <h2 class="section-label">Backend hardware</h2>
      <div class="hw-grid" aria-label="Hardware targets">
        <div class="hw-col"><h3>CPU</h3>
          <a href="explore/domain-cpu.html">x86-64</a>
          <a href="explore/domain-cpu.html">AArch64</a>
          <a href="explore/domain-cpu.html">RISC-V</a>
        </div>
        <div class="hw-col"><h3>GPU</h3>
          <a href="explore/domain-gpu.html">NVIDIA</a>
          <a href="explore/domain-gpu.html">AMD</a>
          <a href="explore/domain-gpu.html">Intel</a>
          <a href="explore/domain-gpu.html">Portable GPU</a>
        </div>
        <div class="hw-col"><h3>AI accelerators</h3>
          <a href="explore/domain-ai-ml.html">TPU</a>
          <a href="explore/domain-accelerators.html">NPU</a>
          <a href="explore/domain-accelerators.html">ASIC</a>
        </div>
        <div class="hw-col"><h3>Other</h3>
          <a href="explore/domain-fpga.html">FPGA</a>
          <a href="explore/domain-dsp.html">DSP</a>
          <a href="explore/domain-quantum.html">Quantum</a>
        </div>
      </div>
      <h2 class="section-label">Explore domains &amp; projects</h2>
      <div class="buckets">{domain_cards}</div>
      {recent}
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
        latest_line = f"<span class='go'>Latest: {n} curated changes</span>" if latest and n else "<span class='go'>Open →</span>"
        if tid == "research" and latest:
            n = int(latest.stats.get("research") or 0)
            latest_line = f"<span class='go'>Latest: {n} papers/items</span>" if n else latest_line
        cards.append(
            f"""<a class="bucket" href="{html.escape(tid)}.html">
  <strong>{html.escape(str(t['label']))}</strong>
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
    who = html.escape(", ".join(g.get("who_should_care") or [])[:120])
    ctype = html.escape(g.get("change_type") or "Other")
    badges = "".join(
        f'<span class="badge">{html.escape(str(b))}</span>'
        for b in (g.get("stages") or [])[:2] + (g.get("domains") or [])[:2]
        if b
    )
    url = "#"
    stories = g.get("stories") or []
    if stories:
        url = html.escape(stories[0].get("source_url") or "#")
    if compact:
        return f"""<article class="story-row">
  <h4><a href="{url}" rel="noopener noreferrer">{title}</a></h4>
  <p class="secondary">{why}</p>
  <div class="meta">{ctype} · {who}</div>
</article>"""
    what_block = f'<p class="secondary"><strong>What.</strong> {what}</p>' if what else ""
    return f"""<article class="story-card">
  <h4><a href="{url}" rel="noopener noreferrer">{title}</a></h4>
  <div class="badge-row">{badges}</div>
  {what_block}
  <p><strong>Why.</strong> {why}</p>
  <div class="meta">{ctype} · {who}</div>
</article>"""


def _page_archive(metas: list[IssueMeta]) -> str:
    items = _issue_rows(metas, depth=0)
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap article-narrow">
    <p class="hero-kicker">Archive</p>
    <h1 class="page-title">All issues</h1>
    <section class="panel" style="margin-top:1.5rem">
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
    <h1 class="page-title">Compiler intelligence, not a commit dump</h1>
    <p class="muted">CompilerSutra Weekly curates developments across the compiler ecosystem and
    explains <em>what changed</em>, <em>why it matters</em>, and <em>who should care</em>.</p>
    <p class="muted">Git repository activity is the primary source. We do not invent benchmarks or impact.</p>
    <div class="cta-row" style="margin-top:1.5rem">
      <a class="btn btn-primary" href="{html.escape(REPO_URL)}" rel="noopener noreferrer">GitHub</a>
      <a class="btn btn-ghost" href="{html.escape(EDU_URL)}" rel="noopener noreferrer">CompilerSutra.com</a>
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
    <p class="muted">Email delivery is not wired yet. Watch the
    <a href="{html.escape(REPO_URL)}">GitHub repository</a> or check the archive each Saturday.
    We will not ship a fake signup form.</p>
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
    payload = json.dumps(datasets)
    body = f"""
  {_topic_bar(depth=0)}
  <main class="wrap">
    <p class="hero-kicker">Complete change log</p>
    <h1 class="page-title">Search the collected dataset</h1>
    <p class="muted">Includes items not selected for the editorial newsletter.</p>
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
    <p id="count" class="muted"></p>
    <ul id="results" class="changelog-list"></ul>
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
    countEl.textContent = hits.length + ' shown';
    results.innerHTML = hits.map(s => {{
      const why = s.why_it_matters || '';
      const num = s._num ? ('#'+String(s._num).padStart(3,'0')) : s._date;
      return `<li>
        <a href="${{s.source_url}}" rel="noopener noreferrer"><strong>${{esc(s.title)}}</strong></a>
        <div class="meta">${{esc(s.signal||s.importance||'')}} · ${{esc(s.project||s.category||'')}} ·
          ${{esc(why).slice(0,140)}} · <a href="${{s._href}}">${{esc(num)}}</a></div>
      </li>`;
    }}).join('') || '<li class="topic-empty">No matches.</li>';
  }}
  function esc(t){{return String(t||'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
  [q,project,domain,stage,importance].forEach(el=>el.addEventListener('input',render));
  render();
  </script>
"""
    return _shell("Change log — CompilerSutra Weekly", body, active="archive", depth=0)


def _page_issue(meta: IssueMeta, md: str, prev_m: IssueMeta | None, next_m: IssueMeta | None) -> str:
    payload = _load_changelog(meta.path)
    num = f"#{meta.issue_number:03d}" if meta.issue_number else meta.date
    if payload.get("high_signal") or payload.get("groups"):
        content = _render_issue_html(meta, payload)
        toc_ids = [
            ("week-overview", "This week"),
            ("high-signal", "High signal"),
            ("worth-knowing", "Worth knowing"),
            ("moving-stories", "Moving stories"),
            ("worth-reading", "Worth reading"),
            ("deep-dive", "Deep dive"),
            ("by-topic", "By topic"),
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
    <p class="muted">{html.escape(meta.window)}</p>
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
            f'<section id="week-overview" class="issue-section">'
            f'<h2>The week in compiler development</h2>'
            f'<ul class="overview-list">{items}</ul></section>'
        )

    high = payload.get("high_signal") or []
    if high:
        cards = "".join(_issue_story_card(g, prominent=True) for g in high)
        parts.append(
            f'<section id="high-signal" class="issue-section">'
            f"<h2>High signal</h2>"
            f"<p class=\"muted\">Changes that affect behavior, architecture support, or direction.</p>"
            f'<div class="story-stack">{cards}</div></section>'
        )

    worth = payload.get("worth_knowing") or []
    if worth:
        rows = "".join(_issue_story_card(g, prominent=False) for g in worth)
        parts.append(
            f'<section id="worth-knowing" class="issue-section">'
            f"<h2>Worth knowing</h2>"
            f'<div class="story-stack compact">{rows}</div></section>'
        )

    moving = payload.get("moving_stories") or {}
    if moving:
        blocks = []
        for track, items in sorted(moving.items()):
            lis = "".join(f"<li>{html.escape(str(i))}</li>" for i in items)
            blocks.append(f"<h3>{html.escape(str(track))}</h3><ul>{lis}</ul>")
        parts.append(
            f'<section id="moving-stories" class="issue-section">'
            f"<h2>Moving stories</h2>{''.join(blocks)}</section>"
        )

    # Worth reading from markdown section when present
    reading = _extract_section(meta.md, "Worth reading")
    if reading:
        parts.append(
            f'<section id="worth-reading" class="issue-section">'
            f"<h2>Worth reading</h2>"
            f"{markdown_to_html(reading)}</section>"
        )

    deep = payload.get("deep_dive")
    if deep:
        parts.append(_deep_dive_html(deep))

    by_topic = _extract_section(meta.md, "By topic")
    if by_topic:
        parts.append(
            f'<section id="by-topic" class="issue-section">'
            f"<h2>By topic</h2>"
            f"{markdown_to_html(by_topic)}</section>"
        )

    parts.append(
        '<p class="muted" style="margin-top:2rem">CompilerSutra Weekly explains '
        "<em>why you should care</em> — we do not invent benchmarks or completion status.</p>"
    )
    return "\n".join(parts)


def _issue_story_card(g: dict, *, prominent: bool) -> str:
    title = html.escape((g.get("title") or "")[:140])
    proj = html.escape((g.get("project") or g.get("category") or "").upper())
    what = html.escape(g.get("what_changed") or "")
    why = html.escape(g.get("why_it_matters") or "Impact not yet clear from the source alone.")
    who = html.escape(", ".join(g.get("who_should_care") or []) or "Compiler engineers")
    ctype = html.escape(g.get("change_type") or "Other")
    stages = html.escape(", ".join(g.get("stages") or []) or "—")
    domains = html.escape(", ".join(g.get("domains") or []) or "—")
    badges = "".join(
        f'<span class="badge">{html.escape(str(b))}</span>'
        for b in (g.get("stages") or [])[:2] + (g.get("domains") or [])[:2]
        if b
    )
    sources = []
    for s in (g.get("stories") or [])[:5]:
        sha = html.escape((s.get("related_ref") or "")[:8])
        url = html.escape(s.get("source_url") or "#")
        sources.append(f'<a href="{url}" rel="noopener noreferrer"><code>{sha}</code></a>')
    extra = ""
    n = len(g.get("stories") or [])
    if n > 5:
        extra = f" <span class='muted'>(+{n - 5})</span>"
    cls = "story-card issue-story" if prominent else "story-row"
    return f"""<article class="{cls}">
  <h3>{f'[{proj}] ' if proj else ''}{title}</h3>
  <div class="badge-row">{badges}</div>
  <p><strong>What changed.</strong> {what}</p>
  <p><strong>Why it matters.</strong> {why}</p>
  <p class="muted"><strong>Who should care.</strong> {who}</p>
  <p class="meta">Type: {ctype} · Stage: {stages} · Domain: {domains}</p>
  <p class="meta">Source: {" · ".join(sources)}{extra}</p>
</article>"""


def _deep_dive_html(g: dict) -> str:
    title = html.escape((g.get("title") or "")[:160])
    what = html.escape(g.get("what_changed") or "See source commits.")
    why = html.escape(g.get("why_it_matters") or "Impact not yet clear.")
    who = html.escape(", ".join(g.get("who_should_care") or []) or "Compiler engineers")
    stages = html.escape(", ".join(g.get("stages") or []) or "unclassified")
    domains = html.escape(
        ", ".join((g.get("domains") or []) + (g.get("hardware_targets") or [])[:3])
        or "unclassified"
    )
    uncertain = (
        "<p class='muted'><em>Impact is not fully clear from commit subjects alone.</em></p>"
        if g.get("impact_uncertain")
        else ""
    )
    sources = []
    for s in (g.get("stories") or [])[:8]:
        sha = html.escape((s.get("related_ref") or "")[:8])
        url = html.escape(s.get("source_url") or "#")
        summary = html.escape((s.get("summary") or "")[:120])
        sources.append(f'<li><a href="{url}" rel="noopener noreferrer"><code>{sha}</code></a> — {summary}</li>')
    return f"""<section id="deep-dive" class="issue-section deep-dive">
  <h2>Deep dive</h2>
  <article class="feature-card">
    <h3>{title}</h3>
    <ol class="deep-list">
      <li><strong>Background</strong> — related work clustered as one development theme this week.</li>
      <li><strong>What changed</strong> — {what}</li>
      <li><strong>Why it matters</strong> — {why}</li>
      <li><strong>Compiler stage</strong> — {stages}</li>
      <li><strong>Domain / targets</strong> — {domains}</li>
      <li><strong>Who should investigate next</strong> — {who}</li>
    </ol>
    {uncertain}
    <h4>Evidence</h4>
    <ul>{''.join(sources)}</ul>
  </article>
</section>"""


def _issue_rows(metas: list[IssueMeta], *, depth: int) -> str:
    prefix = "" if depth == 0 else "../" * depth
    rows = []
    for m in metas:
        href = prefix + m.href_html
        num = f"#{m.issue_number:03d}" if m.issue_number else "Weekly issue"
        hs = m.stats.get("high_signal")
        extra = f" · {hs} high signal" if hs else ""
        rows.append(
            f"""<li>
  <a class="issue-row" href="{html.escape(href)}">
    <span class="issue-date">{html.escape(m.date)}</span>
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
  <meta name="description" content="The compiler ecosystem, explained every week — selected, organized, and contextualized."/>
  <meta name="color-scheme" content="dark light"/>
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
      <a class="brand" href="{home}">CompilerSutra <span>Weekly</span><span class="brand-tag">The compiler ecosystem, explained every week.</span></a>
      <nav class="nav-desktop" aria-label="Primary">
        <a href="{home}"{cur("home")}>Latest</a>
        <a href="{explore}"{" aria-current=\"page\"" if active=="explore" else ""}>Explore</a>
        <a href="{topics}"{" aria-current=\"page\"" if topic_active else ""}>Topics</a>
        <a href="{research}">Research</a>
        <a href="{archive}"{cur("archive")}>Archive</a>
        <a href="{about}"{cur("about")}>About</a>
      </nav>
      <div class="header-actions">
        <a class="icon-btn" href="{html.escape(REPO_URL)}" rel="noopener noreferrer" title="GitHub">GitHub</a>
        <button type="button" class="icon-btn" id="theme-toggle" aria-pressed="false" aria-label="Toggle color theme">Light</button>
        <button type="button" class="icon-btn nav-toggle" id="nav-toggle" aria-expanded="false" aria-controls="mobile-nav" aria-label="Open menu">Menu</button>
      </div>
    </div>
    <div class="mobile-nav" id="mobile-nav" hidden>
      <div class="wrap" aria-label="Mobile">
        <a href="{home}">Latest</a>
        <a href="{explore}">Explore</a>
        <a href="{topics}">Topics</a>
        <a href="{research}">Research</a>
        <a href="{archive}">Archive</a>
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
  <footer class="site-footer">
    <div class="wrap">
      <div>© CompilerSutra · Apache-2.0 · Editorial context over raw commits</div>
      <div>
        <a href="{changelog}">Change log</a> ·
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
