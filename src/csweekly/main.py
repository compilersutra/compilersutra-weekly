# SPDX-License-Identifier: Apache-2.0
"""CLI: csweekly week | collect | report | run | sources | index."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from csweekly.config import load_sources, sources_dir
from csweekly.models import Story, Window
from csweekly.pipeline import collect_all
from csweekly.reporters.index import write_archive_index
from csweekly.reporters.markdown import build_issue, render_markdown, write_issue
from csweekly.window import friday_friday_window, publish_saturday


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="csweekly",
        description="CompilerSutra Weekly — Fri→Fri research window, Saturday publish",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_week = sub.add_parser("week", help="Show Friday→Friday window and publish Saturday")
    p_week.add_argument("--as-of", type=str, default=None, help="YYYY-MM-DD (UTC date)")

    p_sources = sub.add_parser("sources", help="List configured sources")
    p_sources.add_argument("--sources-dir", type=Path, default=None)
    p_sources.add_argument("--all", action="store_true", help="Include disabled")

    p_collect = sub.add_parser("collect", help="Collect from configured sources")
    p_collect.add_argument("--as-of", type=str, default=None)
    p_collect.add_argument("--sources-dir", type=Path, default=None)
    p_collect.add_argument("--mirrors-dir", type=Path, default=Path("data/mirrors"))
    p_collect.add_argument("--source", action="append", default=None)
    p_collect.add_argument("--kind", action="append", default=None, help="git|rss|arxiv|github_releases")
    p_collect.add_argument("--no-fetch", action="store_true")
    p_collect.add_argument("--repo", type=Path, default=None, help="Override git repo (tests)")
    p_collect.add_argument("--out", type=Path, default=Path("data/last_collect.json"))

    p_report = sub.add_parser("report", help="Build Saturday Markdown from collect JSON")
    p_report.add_argument("--in", dest="infile", type=Path, default=Path("data/last_collect.json"))
    p_report.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_report.add_argument("--stdout", action="store_true")
    p_report.add_argument("--index", action="store_true", help="Also refresh archive index")

    p_index = sub.add_parser("index", help="Rebuild reports archive index for GitHub Pages")
    p_index.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_index.add_argument("--site-dir", type=Path, default=Path("site"))

    p_run = sub.add_parser("run", help="collect + report + index")
    p_run.add_argument("--as-of", type=str, default=None)
    p_run.add_argument("--sources-dir", type=Path, default=None)
    p_run.add_argument("--mirrors-dir", type=Path, default=Path("data/mirrors"))
    p_run.add_argument("--source", action="append", default=None)
    p_run.add_argument("--kind", action="append", default=None)
    p_run.add_argument("--no-fetch", action="store_true")
    p_run.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_run.add_argument("--site-dir", type=Path, default=Path("site"))

    args = parser.parse_args(argv)
    if args.cmd == "week":
        return cmd_week(args.as_of)
    if args.cmd == "sources":
        return cmd_sources(args)
    if args.cmd == "collect":
        return cmd_collect(args)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "index":
        return cmd_index(args)
    if args.cmd == "run":
        return cmd_run(args)
    return 2


def _parse_as_of(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def cmd_week(as_of: str | None) -> int:
    window = friday_friday_window(as_of=_parse_as_of(as_of))
    pub = publish_saturday(window)
    print(f"window:  {window.label} ({window.timezone})")
    print(f"start:   {window.start.isoformat()}")
    print(f"end:     {window.end.isoformat()} (exclusive)")
    print(f"publish: {pub.isoformat()} (Saturday)")
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
    window = friday_friday_window(as_of=_parse_as_of(args.as_of))
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
    payload = {
        "window": window.model_dump(mode="json"),
        "results": [r.model_dump(mode="json") for r in results],
        "stories": [s.model_dump(mode="json") for s in stories],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(stories)} stories)", file=sys.stderr)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    raw = json.loads(args.infile.read_text(encoding="utf-8"))
    window = Window.model_validate(raw["window"])
    stories = [Story.model_validate(s) for s in raw["stories"]]
    issue = build_issue(window, stories)
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


if __name__ == "__main__":
    raise SystemExit(main())
