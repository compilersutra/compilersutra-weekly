# SPDX-License-Identifier: Apache-2.0
"""Weekly newsletter Markdown — curated LLVM Weekly–style digest."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from csweekly.analyzers.hotspots import path_hotspots
from csweekly.brand import EDU_URL, PAGES_URL, REPO_URL
from csweekly.models import ChangeGroup, EvidenceKind, Importance, Story, WeeklyIssue, Window
from csweekly.processors.dedupe import dedupe_stories
from csweekly.processors.editorial import (
    editorial_sentence,
    newsletter_bucket,
    select_for_newsletter,
    split_non_git,
)
from csweekly.processors.group import group_stories
from csweekly.window import publish_saturday

# Published section order for the editorial issue (not a dump of every category).
SECTION_SPECS: list[tuple[str, list[str]]] = [
    ("LLVM", ["llvm"]),
    ("Clang", ["clang"]),
    ("GCC", ["gcc"]),
    ("MLIR", ["mlir"]),
    ("AI Compilers", ["ai"]),
    ("GPU Compilers", ["gpu"]),
    ("Other compiler projects", ["other"]),
]

# Back-compat for tests
SECTION_ORDER = SECTION_SPECS


def issue_number(published_on, reports_dir: Path | None = None) -> int:
    if reports_dir and reports_dir.is_dir():
        dates = sorted(
            {
                p.stem
                for p in reports_dir.glob("**/*.md")
                if p.name != "README.md"
            }
            | {published_on.isoformat()}
        )
        try:
            return dates.index(published_on.isoformat()) + 1
        except ValueError:
            return len(dates)
    from datetime import date

    epoch = date(2026, 11, 7)
    return max(0, (published_on - epoch).days // 7) + 1


def build_issue(
    window: Window,
    stories: list[Story],
    *,
    title: str | None = None,
    reports_dir: Path | None = None,
    errors: list[str] | None = None,
) -> WeeklyIssue:
    unique = dedupe_stories(stories)
    for s in unique:
        if not s.project:
            s.project = s.category

    git_stories = [s for s in unique if s.evidence_kind == EvidenceKind.GIT_COMMIT]
    groups = group_stories(git_stories)
    editorial_groups = select_for_newsletter(groups)
    hot = path_hotspots(unique)
    sections: dict[str, list[Story]] = defaultdict(list)
    for story in unique:
        sections[story.category].append(story)
    pub = publish_saturday(window)
    num = issue_number(pub, reports_dir)
    projects = sorted(
        {
            (s.project or s.category)
            for s in unique
            if s.evidence_kind == EvidenceKind.GIT_COMMIT
        }
    )
    side = split_non_git(unique)
    stats = {
        "issue_number": num,
        "total_stories": len(stories),
        "unique_commits": sum(
            1 for s in unique if s.evidence_kind == EvidenceKind.GIT_COMMIT
        ),
        "unique_items": len(unique),
        "groups": len(groups),
        "editorial_groups": len(editorial_groups),
        "highlights": sum(
            1 for g in editorial_groups if g.importance == Importance.HIGHLIGHT
        ),
        "notable": sum(
            1 for g in editorial_groups if g.importance == Importance.NOTABLE
        ),
        "projects": projects,
        "projects_tracked": len(projects),
        "releases": len(side["releases"]),
        "research": len(side["research"]),
        "community": len(side["community"]),
        "errors": errors or [],
    }
    return WeeklyIssue(
        title=title
        or f"CompilerSutra Weekly — #{num:03d}, {pub.strftime('%B')} {pub.day} {pub.year}",
        published_on=pub,
        window=window,
        stories=unique,
        groups=editorial_groups,
        sections=dict(sections),
        hotspots={"paths": hot},
        stats=stats,
    )


def render_markdown(issue: WeeklyIssue) -> str:
    stats = issue.stats
    num = int(stats.get("issue_number", 1))
    side = split_non_git(issue.stories)
    date_label = (
        f"{issue.published_on.strftime('%B')} {issue.published_on.day} "
        f"{issue.published_on.year}"
    )

    lines: list[str] = [
        f"# CompilerSutra Weekly — #{num:03d}, {date_label}",
        "",
        "**What changed in compilers this week.**",
        "",
        f"Welcome to issue **#{num:03d}** of CompilerSutra Weekly, a Saturday newsletter "
        "covering developments across LLVM, Clang, GCC, MLIR, AI compilers, GPU compilers, "
        "and related toolchains.",
        "",
        f"**Reporting period:** {issue.window.label} ({issue.window.timezone}, Fri→Fri, end exclusive)  ",
        f"**Published:** {issue.published_on.isoformat()}",
        "",
        "Entries below are curated from repository activity and project announcements. "
        "Each item is a short technical note with a link to the original source — not a "
        "raw commit dump. Full collected data stays on the "
        f"[complete change log]({PAGES_URL.rstrip('/')}/changelog.html).",
        "",
    ]

    # Bucket editorial groups the way LLVM Weekly splits LLVM / Clang / other
    buckets: dict[str, list[ChangeGroup]] = defaultdict(list)
    for g in issue.groups:
        buckets[newsletter_bucket(g.stories[0])].append(g)

    def emit_bullets(heading: str, groups: list[ChangeGroup]) -> None:
        if not groups:
            return
        lines.append(f"## {heading}")
        lines.append("")
        for g in groups:
            lines.append(_bullet(g))
        lines.append("")

    emit_bullets("LLVM", buckets.get("llvm", []))
    emit_bullets("Clang", buckets.get("clang", []))
    emit_bullets("GCC", [g for g in issue.groups if g.category == "gcc"])
    emit_bullets("MLIR", [g for g in issue.groups if g.category == "mlir"])

    # AI / GPU / other: subgroup by project when useful
    for heading, cats in (
        ("AI Compilers", ["ai"]),
        ("GPU Compilers", ["gpu"]),
        ("Other compiler projects", ["other"]),
    ):
        groups = [g for g in issue.groups if g.category in cats]
        # include other-llvm under Other compiler projects
        if heading.startswith("Other"):
            groups = list(groups) + list(buckets.get("other-llvm", []))
        if not groups:
            continue
        lines.append(f"## {heading}")
        lines.append("")
        by_proj: dict[str, list[ChangeGroup]] = defaultdict(list)
        for g in groups:
            by_proj[g.project or g.category].append(g)
        if len(by_proj) > 1:
            for proj, pgroups in sorted(by_proj.items(), key=lambda x: x[0]):
                lines.append(f"### {proj}")
                lines.append("")
                for g in pgroups:
                    lines.append(_bullet(g))
                lines.append("")
        else:
            for g in groups:
                lines.append(_bullet(g))
            lines.append("")

    if side["releases"]:
        lines.append("## Releases and announcements")
        lines.append("")
        for s in sorted(side["releases"], key=lambda x: x.title.lower())[:12]:
            lines.append(f"- **{s.title}** — [release]({s.source_url})")
            note = (s.summary or "").strip()
            if note and note != s.title:
                lines.append(f"  {note[:220]}")
        lines.append("")

    if side["community"]:
        lines.append("## Articles and community discussions")
        lines.append("")
        for s in side["community"][:12]:
            lines.append(f"- **{s.title}** — [source]({s.source_url})")
            note = (s.summary or "").strip()
            if note and note != s.title:
                lines.append(f"  {note[:220]}")
        lines.append("")

    research = _filter_compiler_research(side["research"])
    if research:
        lines.append("## Research papers")
        lines.append("")
        lines.append(
            "Compiler-relevant papers from arXiv this window (not Git commits)."
        )
        lines.append("")
        for s in research[:8]:
            lines.append(f"- **{s.title}** — [paper]({s.source_url})")
            if s.summary:
                lines.append(f"  {s.summary[:260]}")
        lines.append("")

    errs = stats.get("errors") or []
    if errs:
        lines.append("## Collection notes")
        lines.append("")
        for e in errs[:12]:
            lines.append(f"- {e}")
        lines.append("")

    lines.extend(
        [
            "## Further reading",
            "",
            f"- Browse every collected change in the "
            f"[complete change log]({PAGES_URL.rstrip('/')}/changelog.html) "
            f"(search GlobalISel, AMDGPU, Triton, GCC, …).",
            f"- Machine-readable data: "
            f"`reports/{issue.published_on.year}/{issue.published_on.isoformat()}.changelog.json`",
            f"- Source & collectors: [{REPO_URL}]({REPO_URL})",
            f"- Learn compilers: [{EDU_URL}]({EDU_URL})",
            "",
            "---",
            "",
            "CompilerSutra Weekly selects developments that matter for compiler engineers. "
            "We do not invent impact, performance numbers, or completion status.",
            "",
        ]
    )
    return "\n".join(lines)


def write_issue(issue: WeeklyIssue, reports_dir: Path) -> Path:
    year_dir = reports_dir / f"{issue.published_on.year}"
    year_dir.mkdir(parents=True, exist_ok=True)
    path = year_dir / f"{issue.published_on.isoformat()}.md"
    path.write_text(render_markdown(issue), encoding="utf-8")
    data_path = year_dir / f"{issue.published_on.isoformat()}.changelog.json"
    payload = {
        "title": issue.title,
        "issue_number": issue.stats.get("issue_number"),
        "published_on": issue.published_on.isoformat(),
        "window": issue.window.model_dump(mode="json"),
        "stats": {k: v for k, v in issue.stats.items() if k != "errors"},
        "stories": [s.model_dump(mode="json") for s in issue.stories],
        "groups": [g.model_dump(mode="json") for g in issue.groups],
    }
    data_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


_COMPILER_RESEARCH = re.compile(
    r"(?i)\b("
    r"compiler|compilation|llvm|clang|gcc|mlir|codegen|code generation|"
    r"vectoriz|register alloc|instruction select|gpu|cuda|rocm|sycl|"
    r"triton|xla|tvm|iree|optimization pass|intermediate representation|"
    r"wasm|webassembly|jit|aot\b|backend|frontend|gimple|rtl\b"
    r")\b"
)


def _filter_compiler_research(stories: list[Story]) -> list[Story]:
    out = []
    for s in stories:
        blob = f"{s.title}\n{s.summary}"
        if _COMPILER_RESEARCH.search(blob):
            out.append(s)
    return out


def _bullet(group: ChangeGroup) -> str:
    """One LLVM Weekly–style bullet: sentence + linked SHA(s)."""
    sentence = editorial_sentence(group)
    if len(group.stories) == 1:
        s = group.stories[0]
        sha = (s.related_ref or "")[:7]
        return f"- {sentence} [`{sha}`]({s.source_url})."
    # Grouped: list a few SHAs like LLVM Weekly libc example
    links = []
    for s in group.stories[:4]:
        sha = (s.related_ref or "")[:7]
        links.append(f"[`{sha}`]({s.source_url})")
    extra = f", +{len(group.stories) - 4} more" if len(group.stories) > 4 else ""
    return f"- {sentence} {', '.join(links)}{extra}."


def _slug(heading: str) -> str:
    s = heading.lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")
