# SPDX-License-Identifier: Apache-2.0
"""Weekly newsletter Markdown — LLVM Weekly–style editorial digest."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from csweekly.analyzers.hotspots import path_hotspots
from csweekly.brand import EDU_URL, REPO_URL
from csweekly.models import ChangeGroup, EvidenceKind, Importance, Story, WeeklyIssue, Window
from csweekly.processors.dedupe import dedupe_stories
from csweekly.processors.editorial import (
    editorial_blurb,
    select_for_newsletter,
    split_non_git,
)
from csweekly.processors.group import group_stories
from csweekly.window import publish_saturday

# Published newsletter sections (heading → categories for git groups)
SECTION_ORDER: list[tuple[str, list[str]]] = [
    ("LLVM", ["llvm"]),
    ("GCC", ["gcc"]),
    ("MLIR", ["mlir"]),
    ("AI Compilers", ["ai"]),
    ("GPU Compilers", ["gpu"]),
    ("Other Compiler Projects", ["other"]),
]


def issue_number(published_on, reports_dir: Path | None = None) -> int:
    """Stable issue number from chronological Saturday publish dates."""
    if reports_dir and reports_dir.is_dir():
        dates = []
        for p in reports_dir.glob("**/*.md"):
            if p.name == "README.md":
                continue
            try:
                dates.append(p.stem)  # YYYY-MM-DD
            except Exception:
                continue
        dates = sorted(set(dates) | {published_on.isoformat()})
        try:
            return dates.index(published_on.isoformat()) + 1
        except ValueError:
            return len(dates)
    # fallback: days since project epoch / 7
    from datetime import date

    epoch = date(2026, 11, 7)
    weeks = max(0, (published_on - epoch).days // 7)
    return weeks + 1


def build_issue(
    window: Window,
    stories: list[Story],
    *,
    title: str | None = None,
    reports_dir: Path | None = None,
    errors: list[str] | None = None,
) -> WeeklyIssue:
    unique = dedupe_stories(stories)
    # Enrich paths/areas already done in pipeline; group + select
    for s in unique:
        if not s.project:
            s.project = s.category
    groups = group_stories(
        [s for s in unique if s.evidence_kind == EvidenceKind.GIT_COMMIT]
    )
    editorial_groups = select_for_newsletter(groups)
    hot = path_hotspots(unique)
    sections: dict[str, list[Story]] = defaultdict(list)
    for story in unique:
        sections[story.category].append(story)
    pub = publish_saturday(window)
    num = issue_number(pub, reports_dir)
    projects = sorted({(s.project or s.category) for s in unique if s.evidence_kind == EvidenceKind.GIT_COMMIT})
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
        "highlights": sum(1 for g in editorial_groups if g.importance == Importance.HIGHLIGHT),
        "notable": sum(1 for g in editorial_groups if g.importance == Importance.NOTABLE),
        "projects": projects,
        "projects_tracked": len(projects),
        "releases": len(side["releases"]),
        "research": len(side["research"]),
        "community": len(side["community"]),
        "errors": errors or [],
    }
    return WeeklyIssue(
        title=title or f"CompilerSutra Weekly — #{num:03d}, {pub.strftime('%B')} {pub.day} {pub.year}",
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
    lines: list[str] = [
        f"# CompilerSutra Weekly — #{num:03d}, {issue.published_on.strftime('%B')} {issue.published_on.day} {issue.published_on.year}",
        "",
        "**What changed in compilers this week.**",
        "",
        f"**Issue:** #{num:03d}  ",
        f"**Published:** {issue.published_on.isoformat()} (Saturday)  ",
        f"**Reporting period:** {issue.window.label} ({issue.window.timezone}, Fri→Fri, end exclusive)",
        "",
        _intro(issue),
        "",
        "## Contents",
        "",
    ]

    # TOC only for sections that will appear
    toc_items: list[str] = []
    groups_by_cat: dict[str, list[ChangeGroup]] = defaultdict(list)
    for g in issue.groups:
        groups_by_cat[g.category].append(g)

    for heading, cats in SECTION_ORDER:
        if any(groups_by_cat.get(c) for c in cats):
            toc_items.append(f"- [{heading}](#{_slug(heading)})")
    if side["releases"]:
        toc_items.append("- [Releases and announcements](#releases-and-announcements)")
    if side["research"]:
        toc_items.append("- [Research papers](#research-papers)")
    if side["community"]:
        toc_items.append(
            "- [Articles and community discussions](#articles-and-community-discussions)"
        )
    toc_items.append("- [Complete change log](#complete-change-log)")
    lines.extend(toc_items)
    lines.append("")

    for heading, cats in SECTION_ORDER:
        section_groups: list[ChangeGroup] = []
        for c in cats:
            section_groups.extend(groups_by_cat.get(c, []))
        if not section_groups:
            continue
        lines.append(f"## {heading}")
        lines.append("")
        by_project: dict[str, list[ChangeGroup]] = defaultdict(list)
        for g in section_groups:
            by_project[g.project or g.category].append(g)
        multi = heading in {"AI Compilers", "GPU Compilers", "Other Compiler Projects"} and len(by_project) > 1
        for project, pgroups in sorted(by_project.items(), key=lambda x: x[0]):
            if multi:
                lines.append(f"### {project}")
                lines.append("")
            for g in pgroups:
                lines.extend(_entry_block(g))
        lines.append("")

    if side["releases"]:
        lines.append("## Releases and announcements")
        lines.append("")
        for s in sorted(side["releases"], key=lambda x: x.title.lower())[:20]:
            lines.append(f"- **{s.title}** — [source]({s.source_url})")
            if s.summary and s.summary != s.title:
                lines.append(f"  - {s.summary[:240]}")
        lines.append("")

    if side["research"]:
        lines.append("## Research papers")
        lines.append("")
        lines.append(
            "Research entries come from arXiv / paper sources — not from Git commits."
        )
        lines.append("")
        for s in side["research"][:15]:
            lines.append(f"- **{s.title}**")
            lines.append(f"  - [Paper]({s.source_url})")
            if s.summary:
                lines.append(f"  - {s.summary[:320]}")
        lines.append("")

    if side["community"]:
        lines.append("## Articles and community discussions")
        lines.append("")
        for s in side["community"][:20]:
            lines.append(f"- **{s.title}** — [source]({s.source_url})")
            if s.summary and s.summary != s.title:
                lines.append(f"  - {s.summary[:240]}")
        lines.append("")

    errs = stats.get("errors") or []
    if errs:
        lines.append("## Collection notes")
        lines.append("")
        for e in errs[:20]:
            lines.append(f"- {e}")
        lines.append("")

    lines.extend(
        [
            "## Complete change log",
            "",
            f"Editorial selection above covers **{stats.get('editorial_groups', 0)}** "
            f"development groups from **{stats.get('unique_commits', 0)}** unique commits "
            f"across **{stats.get('projects_tracked', 0)}** projects with activity. "
            "The full collected set (including lower-priority changes) is available on the "
            "[changelog](../../site/changelog.html) page and in the machine-readable "
            f"`{issue.published_on.isoformat()}.changelog.json` alongside this issue.",
            "",
            "### All unique items this week",
            "",
        ]
    )
    for story in sorted(
        issue.stories,
        key=lambda s: (s.category, s.project or "", s.title.lower()),
    ):
        lines.extend(_story_compact(story))

    lines.extend(
        [
            "",
            "---",
            "",
            f"CompilerSutra Weekly · [Source]({REPO_URL}) · [CompilerSutra]({EDU_URL}) "
            "(education site links out only). Every entry links to its original source.",
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


def _intro(issue: WeeklyIssue) -> str:
    stats = issue.stats
    num = int(stats.get("issue_number", 1))
    projects = stats.get("projects") or []
    project_bit = ", ".join(projects[:8]) if projects else "tracked sources"
    if len(projects) > 8:
        project_bit += ", …"
    return (
        f"Welcome to issue **#{num:03d}** of CompilerSutra Weekly — a Saturday digest of "
        f"compiler engineering across LLVM, GCC, MLIR, AI compilers, GPU compilers, and "
        f"related toolchains. This week covers **{issue.window.label}** (UTC). "
        f"Activity observed in: {project_bit}. "
        "Entries are selected and grouped from repository activity; every link goes to "
        "the original source. Descriptions stay factual — we do not invent performance "
        "claims or completion status."
    )


def _entry_block(group: ChangeGroup) -> list[str]:
    """LLVM Weekly–style: bold title, short paragraph, source links."""
    blurb = editorial_blurb(group.stories[0])
    if len(group.stories) > 1:
        # Prefer a cleaner group title without raw subject noise
        head = group.title
        if "(" in head and head.endswith("commits)"):
            # "amdgpu (5 commits)" → expand
            base = head.rsplit("(", 1)[0].strip()
            head = f"{base}"
            blurb = (
                f"{len(group.stories)} related commits on this development. "
                f"Latest: {blurb}"
            )
        title = _pretty_title(head, group)
    else:
        title = _pretty_title(group.stories[0].title, group)

    areas = ", ".join(group.areas[:3]) if group.areas else ""
    lines = [
        f"**{title}**",
        "",
    ]
    if areas and group.importance != Importance.OTHER:
        lines.append(f"{blurb} *({areas})*")
    else:
        lines.append(blurb)
    lines.append("")
    if len(group.stories) == 1:
        s = group.stories[0]
        sha = (s.related_ref or "")[:8]
        label = sha if sha else "source"
        lines.append(f"[`{label}`]({s.source_url})")
    else:
        parts = []
        for s in group.stories[:8]:
            sha = (s.related_ref or "")[:8] or "link"
            parts.append(f"[`{sha}`]({s.source_url})")
        extra = f" (+{len(group.stories) - 8} more)" if len(group.stories) > 8 else ""
        lines.append(", ".join(parts) + extra)
    lines.append("")
    return lines


def _pretty_title(raw: str, group: ChangeGroup) -> str:
    # Prefer the latest commit subject when group title is a machine key
    if group.stories:
        raw = group.stories[0].title or raw
    t = re.sub(r"^\[[^\]]+\]\s*", "", raw).strip()
    t = re.sub(r"\s*\(\d+ commits\)\s*$", "", t).strip()
    if group.project and group.category in {"ai", "gpu", "other"}:
        if group.project.lower() not in t.lower()[: len(group.project) + 2]:
            return f"{group.project}: {t}"[:160]
    return t[:160]


def _story_compact(story: Story) -> list[str]:
    when = story.published_at.date().isoformat() if story.published_at else "?"
    areas = ",".join(story.areas) if story.areas else "Other"
    return [
        f"- `{story.importance.value}` · **{story.project or story.category}** · {areas} · "
        f"[{story.title}]({story.source_url}) · {when} · `{story.evidence_kind.value}`",
    ]


def _slug(heading: str) -> str:
    s = heading.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")
