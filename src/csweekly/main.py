# SPDX-License-Identifier: Apache-2.0
"""CLI: collect → process → review → validate → publish (Saturday)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from csweekly.config import load_sources, sources_dir
from csweekly.edition import (
    EditionStatus,
    ensure_edition,
    freeze_edition,
    load_candidates,
    load_meta,
    load_raw_stories,
    mark_published,
    merge_raw_stories,
    set_status,
    write_candidates,
    write_editorial_report,
    write_normalized,
)
from csweekly.models import SignalLevel, Story, Window
from csweekly.pipeline import collect_all, enrich_story
from csweekly.processors.group import group_stories
from csweekly.processors.normalize import normalize_stories
from csweekly.reporters.index import write_archive_index
from csweekly.reporters.markdown import build_issue, render_markdown, write_issue
from csweekly.validate import format_gate_report, validate_edition
from csweekly.window import (
    collecting_window,
    publish_saturday,
    publishable_window,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="csweekly",
        description=(
            "CompilerSutra Weekly — Sat→Fri collect (Asia/Kolkata), "
            "Friday freeze, Saturday publish"
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_week = sub.add_parser("week", help="Show collecting + publishable windows")
    p_week.add_argument("--as-of", type=str, default=None, help="YYYY-MM-DD")

    p_sources = sub.add_parser("sources", help="List configured sources")
    p_sources.add_argument("--sources-dir", type=Path, default=None)
    p_sources.add_argument("--all", action="store_true", help="Include disabled")

    p_collect = sub.add_parser(
        "collect",
        help="Idempotent raw collection into the active edition (never public prose)",
    )
    p_collect.add_argument("--as-of", type=str, default=None)
    p_collect.add_argument("--sources-dir", type=Path, default=None)
    p_collect.add_argument("--mirrors-dir", type=Path, default=Path("data/mirrors"))
    p_collect.add_argument("--source", action="append", default=None)
    p_collect.add_argument("--kind", action="append", default=None, help="git|rss|arxiv|github_releases")
    p_collect.add_argument("--no-fetch", action="store_true")
    p_collect.add_argument("--repo", type=Path, default=None, help="Override git repo (tests)")
    p_collect.add_argument("--out", type=Path, default=Path("data/last_collect.json"))
    p_collect.add_argument(
        "--closed",
        action="store_true",
        help="Collect into the closed publishable week (rebuild), not the live week",
    )

    p_process = sub.add_parser(
        "process",
        help="Normalize + cluster raw edition data into candidates",
    )
    p_process.add_argument("--as-of", type=str, default=None)
    p_process.add_argument("--edition", type=Path, default=None, help="Edition directory")

    p_review = sub.add_parser(
        "review",
        help="Write editorial queue report from candidates",
    )
    p_review.add_argument("--as-of", type=str, default=None)
    p_review.add_argument("--edition", type=Path, default=None)

    p_analyze = sub.add_parser(
        "analyze",
        help="AI editorial engine: diff evidence → write → fact-check (changelog)",
    )
    p_analyze.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_analyze.add_argument("--site-dir", type=Path, default=Path("site"))
    p_analyze.add_argument(
        "--changelog",
        type=Path,
        default=None,
        help="Specific *.changelog.json (default: latest under reports)",
    )
    p_analyze.add_argument("--mirrors-dir", type=Path, default=Path("data/mirrors"))
    p_analyze.add_argument(
        "--llm",
        action="store_true",
        help="Use CSWEEKLY_AI_API_KEY / OpenAI-compatible API (else deterministic)",
    )
    p_analyze.add_argument(
        "--factcheck-llm",
        action="store_true",
        help="Also run LLM fact-check pass",
    )
    p_analyze.add_argument(
        "--deep-only",
        action="store_true",
        help="Only analyze deep_dive + high_signal (skip worth_knowing)",
    )
    p_analyze.add_argument("--no-index", action="store_true")

    p_freeze = sub.add_parser(
        "freeze",
        help="Friday freeze: stop collecting into this edition",
    )
    p_freeze.add_argument("--as-of", type=str, default=None)
    p_freeze.add_argument("--edition", type=Path, default=None)

    p_validate = sub.add_parser("validate", help="Pre-publish quality gates")
    p_validate.add_argument("--as-of", type=str, default=None)
    p_validate.add_argument("--edition", type=Path, default=None)
    p_validate.add_argument(
        "--reports-dir", type=Path, default=Path("reports"), help="Optional issue cross-check"
    )

    p_publish = sub.add_parser(
        "publish",
        help="Build immutable report + mark edition published + refresh site",
    )
    p_publish.add_argument("--as-of", type=str, default=None)
    p_publish.add_argument("--edition", type=Path, default=None)
    p_publish.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_publish.add_argument("--site-dir", type=Path, default=Path("site"))
    p_publish.add_argument("--skip-validate", action="store_true")

    p_report = sub.add_parser("report", help="Build Saturday Markdown from collect JSON (legacy)")
    p_report.add_argument("--in", dest="infile", type=Path, default=Path("data/last_collect.json"))
    p_report.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_report.add_argument("--stdout", action="store_true")
    p_report.add_argument("--index", action="store_true", help="Also refresh archive index")

    p_index = sub.add_parser("index", help="Rebuild site from published reports only")
    p_index.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_index.add_argument("--site-dir", type=Path, default=Path("site"))

    p_refresh = sub.add_parser(
        "refresh",
        help="Re-enrich stories from changelog JSON and rewrite MD + site",
    )
    p_refresh.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_refresh.add_argument("--site-dir", type=Path, default=Path("site"))
    p_refresh.add_argument(
        "--changelog",
        type=Path,
        default=None,
        help="Specific *.changelog.json (default: all under reports)",
    )

    p_run = sub.add_parser(
        "run",
        help="Legacy: collect(closed) + report + index (prefer publish lifecycle)",
    )
    p_run.add_argument("--as-of", type=str, default=None)
    p_run.add_argument("--sources-dir", type=Path, default=None)
    p_run.add_argument("--mirrors-dir", type=Path, default=Path("data/mirrors"))
    p_run.add_argument("--source", action="append", default=None)
    p_run.add_argument("--kind", action="append", default=None)
    p_run.add_argument("--no-fetch", action="store_true")
    p_run.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_run.add_argument("--site-dir", type=Path, default=Path("site"))

    args = parser.parse_args(argv)
    dispatch = {
        "week": lambda: cmd_week(args.as_of),
        "sources": lambda: cmd_sources(args),
        "collect": lambda: cmd_collect(args),
        "process": lambda: cmd_process(args),
        "review": lambda: cmd_review(args),
        "analyze": lambda: cmd_analyze(args),
        "freeze": lambda: cmd_freeze(args),
        "validate": lambda: cmd_validate(args),
        "publish": lambda: cmd_publish(args),
        "report": lambda: cmd_report(args),
        "index": lambda: cmd_index(args),
        "refresh": lambda: cmd_refresh(args),
        "run": lambda: cmd_run(args),
    }
    return dispatch.get(args.cmd, lambda: 2)()


def _parse_as_of(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _resolve_edition(args: argparse.Namespace, *, mode: str) -> Path:
    if getattr(args, "edition", None):
        return Path(args.edition)
    as_of = _parse_as_of(getattr(args, "as_of", None))
    _, edir = ensure_edition(as_of=as_of, mode=mode)
    return edir


def cmd_week(as_of: str | None) -> int:
    day = _parse_as_of(as_of)
    collecting = collecting_window(as_of=day)
    publishable = publishable_window(as_of=day)
    print(f"timezone:     {collecting.timezone}")
    print(f"collecting:   {collecting.label}")
    print(f"  start:      {collecting.start.isoformat()}")
    print(f"  end:        {collecting.end.isoformat()} (exclusive)")
    print(f"  publish_on: {publish_saturday(collecting).isoformat()} (Saturday)")
    print(f"publishable:  {publishable.label}")
    print(f"  publish_on: {publish_saturday(publishable).isoformat()} (Saturday)")
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    srcs = load_sources(args.sources_dir or sources_dir())
    for s in srcs:
        if not args.all and not s.enabled:
            continue
        flag = "on " if s.enabled else "off"
        print(f"{flag}  {s.id:20} {s.kind:16} {s.category:10} {s.name}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    as_of = _parse_as_of(args.as_of)
    mode = "publishable" if args.closed else "collecting"
    window = publishable_window(as_of=as_of) if args.closed else collecting_window(as_of=as_of)
    meta, edir = ensure_edition(as_of=as_of, mode=mode)

    only = set(args.source) if args.source else None
    kinds = set(args.kind) if args.kind else None
    results, stories = collect_all(
        window,
        sources_dir=args.sources_dir,
        mirrors_dir=args.mirrors_dir,
        only=only,
        fetch=not args.no_fetch,
        repo_path=args.repo,
        kinds=kinds,
    )
    for r in results:
        print(f"  {r.source_id}: {len(r.stories)} stories", file=sys.stderr)

    try:
        added, total = merge_raw_stories(edir, stories)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = {
        "window": window.model_dump(mode="json"),
        "edition_id": meta.id,
        "edition_dir": str(edir),
        "results": [r.model_dump(mode="json") for r in results],
        "stories": [s.model_dump(mode="json") for s in load_raw_stories(edir)],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"edition {meta.id} ({meta.status.value}): +{added} new → {total} unique raw",
        file=sys.stderr,
    )
    print(f"wrote {args.out} and {edir / 'raw' / 'stories.jsonl'}", file=sys.stderr)
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    # Process the week being closed (collecting), not the prior published week.
    edir = _resolve_edition(args, mode="collecting")
    meta = load_meta(edir)
    if meta.status == EditionStatus.published:
        print(f"edition {meta.id} already published — refuse process", file=sys.stderr)
        return 1

    raw = load_raw_stories(edir)
    normalized = [enrich_story(s) for s in normalize_stories(raw)]
    write_normalized(edir, normalized)

    groups = group_stories(normalized)
    candidates: list[dict] = []
    for g in groups:
        primary = g.stories[0] if g.stories else None
        editorial_status = "candidate"
        if g.signal == SignalLevel.HIGH_SIGNAL:
            editorial_status = "featured"
        elif g.signal == SignalLevel.WORTH_KNOWING:
            editorial_status = "worth_knowing"
        elif primary and primary.category == "research":
            editorial_status = "research"
        candidates.append(
            {
                "id": g.story_id or g.id,
                "title": g.title,
                "project": g.project,
                "category": g.category,
                "source_url": primary.source_url if primary else "",
                "commits": [s.related_ref or s.id for s in g.stories],
                "why_it_matters": g.why_it_matters,
                "what_changed": g.what_changed,
                "signal": g.signal.value if g.signal else None,
                "editorial": {
                    "status": editorial_status,
                    "signal": None,
                    "reason": (
                        [g.why_it_matters]
                        if g.why_it_matters
                        else ["clustered from related commits"]
                    ),
                },
            }
        )
    write_candidates(edir, candidates)
    if meta.status in {EditionStatus.collecting, EditionStatus.processing}:
        set_status(edir, EditionStatus.review)
    write_editorial_report(
        edir,
        raw_count=len(raw),
        normalized_count=len(normalized),
        cluster_count=len(groups),
        candidates=candidates,
    )
    print(
        f"processed {edir}: raw={len(raw)} normalized={len(normalized)} "
        f"candidates={len(candidates)}",
        file=sys.stderr,
    )
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    edir = _resolve_edition(args, mode="collecting")
    raw = load_raw_stories(edir)
    candidates = load_candidates(edir)
    path = write_editorial_report(
        edir,
        raw_count=len(raw),
        normalized_count=len(raw),
        cluster_count=len(candidates),
        candidates=candidates,
    )
    cur = load_meta(edir)
    if cur.status not in {EditionStatus.published, EditionStatus.archived}:
        set_status(edir, EditionStatus.review)
    print(path.read_text(encoding="utf-8"))
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Diff-grounded editorial writing + fact-check for a changelog issue."""
    from csweekly.ai.pipeline import analyze_issue_groups, write_analysis_report
    from csweekly.models import ChangeGroup
    from csweekly.processors.impact import score_impact

    if args.changelog:
        files = [args.changelog]
    else:
        files = sorted(args.reports_dir.glob("**/*.changelog.json"))
        files = files[-1:] if files else []
    if not files:
        print("no changelog files found", file=sys.stderr)
        return 1

    path = files[0]
    raw = json.loads(path.read_text(encoding="utf-8"))
    window = Window.model_validate(raw["window"])
    stories = [enrich_story(Story.model_validate(s)) for s in raw.get("stories") or []]
    issue = build_issue(window, stories, reports_dir=args.reports_dir, errors=[])
    if raw.get("published_on"):
        issue.published_on = date.fromisoformat(str(raw["published_on"]))
    if raw.get("issue_number") is not None:
        issue.stats["issue_number"] = int(raw["issue_number"])
        num = int(raw["issue_number"])
        issue.title = (
            f"CompilerSutra Weekly — #{num:03d}, "
            f"{issue.published_on.strftime('%B')} {issue.published_on.day} "
            f"{issue.published_on.year}"
        )

    def _load_groups(key: str) -> list[ChangeGroup]:
        return [ChangeGroup.model_validate(g) for g in (raw.get(key) or [])]

    # Keep curated selection from the published changelog; re-explain with evidence.
    if raw.get("high_signal") or raw.get("deep_dive"):
        issue.high_signal = _load_groups("high_signal")
        issue.worth_knowing = _load_groups("worth_knowing")
        if raw.get("deep_dive"):
            issue.deep_dive = ChangeGroup.model_validate(raw["deep_dive"])

    targets: list[ChangeGroup] = []
    if issue.deep_dive:
        issue.deep_dive.signal = SignalLevel.DEEP_DIVE
        issue.deep_dive.editorial_level = "deep_dive"
        targets.append(issue.deep_dive)
    for g in issue.high_signal:
        g.signal = SignalLevel.HIGH_SIGNAL
        g.editorial_level = g.editorial_level or "engineering_analysis"
        targets.append(g)
    if not args.deep_only:
        for g in issue.worth_knowing:
            g.signal = SignalLevel.WORTH_KNOWING
            g.editorial_level = g.editorial_level or "quick_signal"
            targets.append(g)

    for g in targets:
        _apply_known_classification_fixes(g)

    rows = analyze_issue_groups(
        targets,
        args.mirrors_dir,
        use_llm=bool(args.llm),
        factcheck_llm=bool(args.factcheck_llm),
    )
    for g in targets:
        score_impact(g)

    report_path = path.parent / path.name.replace(".changelog.json", ".ai_report.md")
    write_analysis_report(report_path, rows)

    out = write_issue(issue, args.reports_dir)
    failed = [r for r in rows if not r.get("factcheck_ok")]
    print(f"analyzed {len(rows)} stories → {out}", file=sys.stderr)
    print(f"report {report_path}", file=sys.stderr)
    if failed:
        print(f"fact-check failures: {len(failed)}", file=sys.stderr)
    if not args.no_index:
        idx = write_archive_index(args.reports_dir, args.site_dir)
        print(f"wrote {idx}", file=sys.stderr)
    return 1 if failed else 0


def cmd_freeze(args: argparse.Namespace) -> int:
    edir = _resolve_edition(args, mode="collecting")
    if load_meta(edir).status == EditionStatus.published:
        print("edition already published — refuse freeze", file=sys.stderr)
        return 1
    meta = freeze_edition(edir)
    print(f"frozen {meta.id} at {meta.frozen_at} (status={meta.status.value})")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    # Saturday validate targets the closed publishable week; mid-week uses collecting.
    as_of = _parse_as_of(args.as_of)
    mode = "publishable" if as_of and as_of.weekday() == 5 else "collecting"
    edir = _resolve_edition(args, mode=mode)
    issue = None
    meta = load_meta(edir)
    if meta.published_at:
        changelog = (
            args.reports_dir
            / f"{meta.published_at.year}"
            / f"{meta.published_at.isoformat()}.changelog.json"
        )
        if changelog.is_file():
            raw = json.loads(changelog.read_text(encoding="utf-8"))
            window = Window.model_validate(raw["window"])
            stories = [Story.model_validate(s) for s in raw.get("stories") or []]
            issue = build_issue(window, stories, reports_dir=args.reports_dir)
    result = validate_edition(edir, issue)
    sys.stdout.write(format_gate_report(result))
    return 0 if result.ok else 1


def cmd_publish(args: argparse.Namespace) -> int:
    edir = _resolve_edition(args, mode="publishable")
    meta = load_meta(edir)
    if meta.status == EditionStatus.published:
        print(f"edition {meta.id} already published — refusing rewrite", file=sys.stderr)
        return 1

    if not args.skip_validate:
        # Ensure candidates exist for gates
        if not load_candidates(edir):
            cmd_process(argparse.Namespace(as_of=args.as_of, edition=edir))
        gate = validate_edition(edir)
        sys.stdout.write(format_gate_report(gate))
        if not gate.ok:
            print("publish aborted", file=sys.stderr)
            return 1

    raw = load_raw_stories(edir)
    if not raw:
        print("no raw stories in edition", file=sys.stderr)
        return 1
    stories = [enrich_story(s) for s in normalize_stories(raw)]
    window = publishable_window(as_of=_parse_as_of(args.as_of) or meta.published_at)
    issue = build_issue(window, stories, reports_dir=args.reports_dir)
    path = write_issue(issue, args.reports_dir)
    meta.number = int(issue.stats.get("issue_number") or meta.number or 0) or None
    mark_published(edir, issue)
    # Copy edition.yaml beside report for status introspection
    year_dir = args.reports_dir / f"{issue.published_on.year}"
    (year_dir / f"{issue.published_on.isoformat()}.edition.yaml").write_text(
        (edir / "edition.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    idx = write_archive_index(args.reports_dir, args.site_dir)
    print(f"published {path}", file=sys.stderr)
    print(f"wrote {idx}", file=sys.stderr)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    raw = json.loads(args.infile.read_text(encoding="utf-8"))
    window = Window.model_validate(raw["window"])
    stories = [enrich_story(Story.model_validate(s)) for s in raw["stories"]]
    errors: list[str] = []
    for r in raw.get("results") or []:
        errors.extend(r.get("errors") or [])
    issue = build_issue(
        window,
        stories,
        reports_dir=args.reports_dir,
        errors=errors,
    )
    text = render_markdown(issue)
    if args.stdout:
        print(text)
    path = write_issue(issue, args.reports_dir)
    print(f"wrote {path}", file=sys.stderr)
    if args.index:
        idx = write_archive_index(args.reports_dir, Path("site"))
        print(f"wrote {idx}", file=sys.stderr)
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    path = write_archive_index(args.reports_dir, args.site_dir)
    print(f"wrote {path}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    """Re-apply classification/editorial layer to stored changelogs without recollecting."""
    files: list[Path]
    if args.changelog:
        files = [args.changelog]
    else:
        files = sorted(args.reports_dir.glob("**/*.changelog.json"))
    if not files:
        print("no changelog files found", file=sys.stderr)
        return 1
    # refresh rebuilds selection; prefer `csweekly analyze` for evidence-backed prose
    for path in files:
        rc = cmd_analyze(
            argparse.Namespace(
                reports_dir=args.reports_dir,
                site_dir=args.site_dir,
                changelog=path,
                mirrors_dir=Path("data/mirrors"),
                llm=False,
                factcheck_llm=False,
                deep_only=False,
                no_index=True,
            )
        )
        if rc not in (0, 1):
            return rc
        print(f"refreshed via analyze {path}", file=sys.stderr)
    idx = write_archive_index(args.reports_dir, args.site_dir)
    print(f"wrote {idx}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    out = Path("data/last_collect.json")
    rc = cmd_collect(
        argparse.Namespace(
            as_of=args.as_of,
            sources_dir=args.sources_dir,
            mirrors_dir=args.mirrors_dir,
            source=args.source,
            kind=args.kind,
            no_fetch=args.no_fetch,
            repo=None,
            out=out,
            closed=True,
        )
    )
    if rc != 0:
        return rc
    rc = cmd_report(
        argparse.Namespace(
            infile=out,
            reports_dir=args.reports_dir,
            stdout=False,
            index=False,
        )
    )
    if rc != 0:
        return rc
    return cmd_index(
        argparse.Namespace(reports_dir=args.reports_dir, site_dir=args.site_dir)
    )


def _apply_known_classification_fixes(group) -> None:
    """Correct recurring mislabels (independent project/stage/domain/target)."""
    blob = " ".join(
        [group.title or "", group.project or ""]
        + [p for s in group.stories for p in (s.paths or [])]
    ).lower()
    title = (group.title or "").lower()

    def set_dims(*, project=None, stages=None, domains=None, targets=None, ctype=None):
        if project:
            group.project = project
        if stages is not None:
            group.stages = stages
        if domains is not None:
            group.domains = domains
        if targets is not None:
            group.hardware_targets = targets
        if ctype:
            group.change_type = ctype

    if "matrix splat" in title or "cir/" in blob and "matrix" in title:
        set_dims(
            project="Clang",
            stages=["Frontend"],
            domains=["Languages"],
            targets=[],
            ctype="New capability",
        )
    elif "riscvabi" in title or ("riscv" in blob and "abi" in title):
        set_dims(
            project="LLVM",
            stages=["Backend"],
            domains=["CPU"],
            targets=["RISC-V"],
            ctype="Infrastructure",
        )
    elif "nvvm.mulf" in title or "nvvm.mulf" in blob:
        set_dims(
            project="MLIR",
            stages=["Middle-end"],
            domains=["GPU"],
            targets=["NVPTX"],
            ctype="New capability",
        )
    elif "spirvtranslate" in title or "spirvapi" in blob:
        set_dims(
            project="LLVM",
            stages=["Runtime & Toolchain"],
            domains=["GPU"],
            targets=["SPIR-V"],
            ctype="Infrastructure",
        )
    elif "dwarfastparserfortran" in title or "dwarfastparserfortran" in blob:
        set_dims(
            project="LLDB",
            stages=["Runtime & Toolchain"],
            domains=["Languages"],
            targets=[],
            ctype="New capability",
        )
    elif "nophis" in title or "sifixsgpr" in blob:
        set_dims(
            project="LLVM",
            stages=["Backend"],
            domains=["GPU"],
            targets=["AMDGPU"],
            ctype="Bug fix",
        )
    elif "vec_perm_const" in title or ("subvector" in title and "riscv" in blob):
        set_dims(
            project="GCC",
            stages=["Backend"],
            domains=["CPU"],
            targets=["RISC-V"],
            ctype="Code generation",
        )


if __name__ == "__main__":
    raise SystemExit(main())
