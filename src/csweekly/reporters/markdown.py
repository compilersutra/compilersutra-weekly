# SPDX-License-Identifier: Apache-2.0
"""Weekly newsletter — high-signal compiler intelligence."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from csweekly.analyzers.hotspots import path_hotspots
from csweekly.brand import EDU_URL, PAGES_URL, REPO_URL
from csweekly.models import (
    ChangeGroup,
    EvidenceKind,
    Importance,
    SignalLevel,
    Story,
    WeeklyIssue,
    Window,
)
from csweekly.processors.dedupe import dedupe_stories
from csweekly.processors.editorial import (
    moving_story_lines,
    newsletter_bucket,
    select_for_newsletter,
    split_non_git,
    week_overview_bullets,
)
from csweekly.processors.explain import explain_group
from csweekly.processors.group import group_stories
from csweekly.window import publish_saturday

SECTION_ORDER = [
    ("LLVM", ["llvm"]),
    ("Clang", ["clang"]),
    ("GCC", ["gcc"]),
    ("MLIR", ["mlir"]),
    ("AI Compilers", ["ai"]),
    ("GPU Compilers", ["gpu"]),
    ("Other Compiler Projects", ["other"]),
]
SECTION_SPECS = SECTION_ORDER


def issue_number(published_on, reports_dir: Path | None = None) -> int:
    """Edition ordinal from published report stems (YYYY-MM-DD.md only)."""
    import re

    if reports_dir and reports_dir.is_dir():
        date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        dates = sorted(
            {
                p.stem
                for p in reports_dir.glob("**/*.md")
                if date_re.match(p.stem)
            }
            | {published_on.isoformat()}
        )
        try:
            return dates.index(published_on.isoformat()) + 1
        except ValueError:
            return len(dates)
    from datetime import date

    return max(0, (published_on - date(2026, 11, 7)).days // 7) + 1


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
    groups = [explain_group(g) for g in group_stories(git_stories)]
    editorial = select_for_newsletter(groups)

    high = [g for g in editorial if g.signal == SignalLevel.HIGH_SIGNAL]
    worth = [g for g in editorial if g.signal == SignalLevel.WORTH_KNOWING]
    deep = next((g for g in editorial if g.signal == SignalLevel.DEEP_DIVE), None)

    sections: dict[str, list[Story]] = defaultdict(list)
    for story in unique:
        sections[story.category].append(story)

    pub = publish_saturday(window)
    num = issue_number(pub, reports_dir)
    projects = sorted(
        {(s.project or s.category) for s in unique if s.evidence_kind == EvidenceKind.GIT_COMMIT}
    )
    side = split_non_git(unique)
    overview = week_overview_bullets(editorial)
    moving = moving_story_lines(editorial)

    stats = {
        "issue_number": num,
        "total_stories": len(stories),
        "unique_commits": sum(1 for s in unique if s.evidence_kind == EvidenceKind.GIT_COMMIT),
        "unique_items": len(unique),
        "groups": len(groups),
        "editorial_groups": len(editorial),
        # deep dive is separate from high_signal list; total for covers:
        "high_signal": len(high) + (1 if deep else 0),
        "high_signal_listed": len(high),
        "deep_dive_count": 1 if deep else 0,
        "worth_knowing": len(worth),
        "highlights": sum(1 for g in editorial if g.importance == Importance.HIGHLIGHT),
        "notable": sum(1 for g in editorial if g.importance == Importance.NOTABLE),
        "projects": projects,
        "projects_tracked": len(projects),
        "releases": len(side["releases"]),
        "research": len(side["research"]),
        "community": len(side["community"]),
        "errors": errors or [],
        "by_domain": _count_labels(editorial, "domains"),
        "by_stage": _count_labels(editorial, "stages"),
        "by_area": _count_labels(editorial, "technical_areas"),
    }
    return WeeklyIssue(
        title=title
        or f"CompilerSutra Weekly — #{num:03d}, {pub.strftime('%B')} {pub.day} {pub.year}",
        published_on=pub,
        window=window,
        stories=unique,
        groups=editorial,
        sections=dict(sections),
        hotspots={"paths": path_hotspots(unique)},
        stats=stats,
        week_overview=overview,
        high_signal=high,
        worth_knowing=worth,
        deep_dive=deep,
        moving_stories=moving,
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
        "**What changed in compilers this week — selected, with context.**",
        "",
        f"Welcome to edition **#{num:03d}**. Not every commit — curated changes across "
        "LLVM, Clang, GCC, MLIR, GPU compilers, AI compilers, and research, with context "
        "on why they matter.",
        "",
        f"**Reporting period:** {issue.window.label} "
        f"({issue.window.timezone}, Saturday→Friday, end exclusive)  ",
        f"**Published:** {issue.published_on.isoformat()}",
        "",
        "## The week in compiler development",
        "",
    ]
    for b in issue.week_overview:
        lines.append(f"- {b}")
    lines.append("")

    # HIGH SIGNAL
    lines.append("## High signal")
    lines.append("")
    lines.append(
        "Changes that affect compiler behavior, architecture support, or a clear "
        "project direction. Investigate these first."
    )
    lines.append("")
    signal_items = list(issue.high_signal)
    if issue.deep_dive and issue.deep_dive not in signal_items:
        # deep dive also listed in its section; include in high signal count display via card
        pass
    if not signal_items and issue.deep_dive:
        signal_items = [issue.deep_dive]
    if not signal_items:
        lines.append("_No high-signal items this week._")
        lines.append("")
    else:
        for i, g in enumerate(signal_items[:8], 1):
            lines.extend(_story_card(g, index=i))

    # WORTH KNOWING
    lines.append("## Worth knowing")
    lines.append("")
    lines.append(
        "Interesting technical changes for a subset of readers. Skip confidently if "
        "the audience tags don't match your work."
    )
    lines.append("")
    if not issue.worth_knowing:
        lines.append("_No additional worth-knowing items selected._")
        lines.append("")
    else:
        for i, g in enumerate(issue.worth_knowing[:12], 1):
            lines.extend(_story_card(g, index=i, compact=True))

    # THEMES THIS WEEK (not invented cross-issue history)
    if issue.moving_stories:
        lines.append("## Themes this week")
        lines.append("")
        lines.append(
            "Theme index for this edition. Cross-edition continuity links appear once "
            "prior editions cover the same story_id."
        )
        lines.append("")
        for track, items in sorted(issue.moving_stories.items()):
            lines.append(f"### {track}")
            lines.append("")
            for item in items:
                # Strip internal [[story:id]] markers for Markdown readers
                visible = re.sub(r"\s*\[\[story:[^\]]+\]\]", "", item)
                lines.append(f"- {visible}")
            lines.append("")

    # WORTH READING
    research = _filter_compiler_research(side["research"])
    if side["releases"] or side["community"] or research:
        lines.append("## Research and reading")
        lines.append("")
        for s in side["releases"][:6]:
            lines.append(f"### Release — {s.title}")
            lines.append("")
            lines.append(f"**What it is.** {_plain_note(s.summary or s.title, 180)}")
            lines.append("")
            lines.append(
                "**Why compiler engineers might care.** Official release notes for a "
                "tracked toolchain — scan for ABI, backend, and diagnostics changes."
            )
            lines.append("")
            lines.append(f"**Source:** [release]({s.source_url})")
            lines.append("")
        for s in side["community"][:6]:
            lines.append(f"### Discussion — {s.title}")
            lines.append("")
            note = _plain_note(s.summary or "", 200)
            lines.append(f"**What is being discussed.** {note if note else 'Community discussion / RFC.'}")
            lines.append("")
            lines.append(
                "**Why it matters.** Early design signal — not an accepted change unless "
                "the thread says so."
            )
            lines.append("")
            lines.append(f"**Source:** [discussion]({s.source_url})")
            lines.append("")
        for s in research[:5]:
            lines.append(f"### Paper — {s.title}")
            lines.append("")
            abstract = _plain_note(s.summary or "", 220)
            lines.append(
                f"**Research problem / contribution (from abstract).** {abstract}"
                if abstract
                else "**Research problem / contribution.** See the paper abstract."
            )
            lines.append("")
            lines.append(
                "**Relevance.** Selected as compiler-adjacent research this week — "
                "read the paper before assuming production impact."
            )
            lines.append("")
            lines.append(f"**Source:** [paper]({s.source_url})")
            lines.append("")

    # DEEP DIVE
    if issue.deep_dive:
        from csweekly.processors.explain import build_deep_dive_notes

        g = issue.deep_dive
        notes = g.deep_dive_notes or build_deep_dive_notes(g)
        lines.append("## Deep dive")
        lines.append("")
        lines.append(f"### {g.title}")
        lines.append("")
        lines.append(
            "Technical walkthrough grounded in the source commits. "
            "Claims stay tied to evidence; unknowns are marked."
        )
        lines.append("")
        lines.append(f"1. **Background** — {notes.get('background', '')}")
        lines.append(f"2. **Previous behavior** — {notes.get('previous_behavior', '')}")
        lines.append(f"3. **Problem** — {notes.get('problem', '')}")
        lines.append(f"4. **Implementation** — {notes.get('implementation', '')}")
        lines.append(f"5. **Example** — {notes.get('example', '')}")
        lines.append(f"6. **Implications** — {notes.get('implications', '')}")
        lines.append(f"7. **Limits / uncertainty** — {notes.get('limits', '')}")
        lines.append("")
        lines.append("**Evidence (sources):**")
        lines.append("")
        for s in g.stories[:8]:
            sha = (s.related_ref or "")[:8]
            lines.append(f"- [`{sha}`]({s.source_url}) — {s.summary[:120]}")
        lines.append("")

    # BY TOPIC — compact index (no full why reprints)
    lines.append("## Topic index")
    lines.append("")
    lines.append(
        "Compact links to canonical stories in this edition. Full explanations live above."
    )
    lines.append("")
    buckets: dict[str, list[ChangeGroup]] = defaultdict(list)
    for g in issue.groups:
        buckets[newsletter_bucket(g.stories[0])].append(g)

    def emit_topic(name: str, groups: list[ChangeGroup]) -> None:
        if not groups:
            return
        lines.append(f"### {name}")
        lines.append("")
        for g in groups[:8]:
            stage = ", ".join((g.stages or [])[:2]) or "—"
            domain = ", ".join((g.domains or [])[:2]) or "—"
            sha = (g.stories[0].related_ref or "")[:7]
            sid = g.story_id or g.id
            lines.append(
                f"- [{g.title[:100]}](#{sid}) · {stage} · {domain} · "
                f"[`{sha}`]({g.stories[0].source_url})"
            )
        lines.append("")

    emit_topic("LLVM", buckets.get("llvm", []))
    emit_topic("Clang", buckets.get("clang", []))
    emit_topic("GCC", [g for g in issue.groups if g.category == "gcc"])
    emit_topic("MLIR", [g for g in issue.groups if g.category == "mlir"])
    emit_topic("AI Compilers", [g for g in issue.groups if g.category == "ai"])
    emit_topic("GPU Compilers", [g for g in issue.groups if g.category == "gpu"])
    emit_topic(
        "Other",
        [g for g in issue.groups if g.category == "other"] + buckets.get("other-llvm", []),
    )

    # Rename moving stories heading in MD
    # (rendered from issue.moving_stories earlier as "Moving stories")

    lines.extend(
        [
            "## Further reading",
            "",
            f"- Complete collected dataset (searchable): "
            f"[{PAGES_URL.rstrip('/')}/changelog.html]({PAGES_URL.rstrip('/')}/changelog.html)",
            f"- Explore by stage / domain / area: "
            f"[{PAGES_URL.rstrip('/')}/topics/index.html]({PAGES_URL.rstrip('/')}/topics/index.html)",
            f"- Source & collectors: [{REPO_URL}]({REPO_URL})",
            f"- Learn compilers: [{EDU_URL}]({EDU_URL})",
            "",
            "---",
            "",
            "CompilerSutra Weekly explains *why you should care* — we do not invent "
            "benchmarks, performance numbers, or completion status. When impact is unclear, "
            "we say so.",
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
        "week_overview": issue.week_overview,
        "stories": [s.model_dump(mode="json") for s in issue.stories],
        "groups": [g.model_dump(mode="json") for g in issue.groups],
        "high_signal": [g.model_dump(mode="json") for g in issue.high_signal],
        "worth_knowing": [g.model_dump(mode="json") for g in issue.worth_knowing],
        "deep_dive": issue.deep_dive.model_dump(mode="json") if issue.deep_dive else None,
        "moving_stories": issue.moving_stories,
    }
    data_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _story_card(group: ChangeGroup, *, index: int, compact: bool = False) -> list[str]:
    proj = (group.project or group.category or "compiler").upper()
    title = group.title[:120]
    what = group.what_changed or title
    why = group.why_it_matters or "The practical impact is not yet clear from the commit message alone."
    who = ", ".join(group.who_should_care) if group.who_should_care else "Compiler engineers"
    ctype = group.change_type or "Other"
    stage = ", ".join(group.stages[:2]) if group.stages else "—"
    domain = ", ".join(group.domains[:2]) if group.domains else "—"
    sha = (group.stories[0].related_ref or "")[:8]
    url = group.stories[0].source_url
    lines = [
        f"### {index}. [{proj}] {title}",
        "",
        f"**What changed**  ",
        what,
        "",
        f"**Why it matters**  ",
        why,
        "",
    ]
    if not compact:
        lines.extend(
            [
                f"**Who should care**  ",
                who,
                "",
                f"**Type:** {ctype} · **Stage:** {stage} · **Domain:** {domain}",
                "",
            ]
        )
    else:
        lines.append(f"**Who:** {who} · **Type:** {ctype}")
        lines.append("")
    if len(group.stories) == 1:
        lines.append(f"**Source:** [`{sha}`]({url})")
    else:
        links = ", ".join(
            f"[`{(s.related_ref or '')[:7]}`]({s.source_url})" for s in group.stories[:4]
        )
        extra = f" (+{len(group.stories) - 4})" if len(group.stories) > 4 else ""
        lines.append(f"**Source:** {links}{extra}")
    lines.append("")
    return lines


def _count_labels(groups: list[ChangeGroup], attr: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for g in groups:
        for label in getattr(g, attr, []) or []:
            counts[label] += 1
    return dict(counts)


_COMPILER_RESEARCH = re.compile(
    r"(?i)\b(compiler|compilation|llvm|clang|gcc|mlir|codegen|vectoriz|"
    r"register alloc|gpu|cuda|rocm|triton|xla|tvm|iree|wasm|jit|backend|frontend)\b"
)


def _filter_compiler_research(stories: list[Story]) -> list[Story]:
    return [s for s in stories if _COMPILER_RESEARCH.search(f"{s.title}\n{s.summary}")]


def _plain_note(text: str, limit: int) -> str:
    """Strip markdown headings so release notes don't pollute the issue TOC."""
    cleaned = re.sub(r"(?m)^#{1,6}\s*", "", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]
