# SPDX-License-Identifier: Apache-2.0
"""CLI: csweekly collect | report | week."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from csweekly.collectors.git_mirror import collect_git
from csweekly.config import load_sources, sources_dir
from csweekly.models import CollectResult, Story
from csweekly.reporters.markdown import build_issue, render_markdown, write_issue
from csweekly.window import friday_friday_window, publish_saturday


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="csweekly",
        description="CompilerSutra Weekly — Fri→Fri research window, Saturday publish",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_week = sub.add_parser("week", help="Show the Friday→Friday window and publish Saturday")
    p_week.add_argument("--as-of", type=str, default=None, help="YYYY-MM-DD (UTC date)")

    p_collect = sub.add_parser("collect", help="Collect from configured git sources")
    p_collect.add_argument("--as-of", type=str, default=None)
    p_collect.add_argument("--sources-dir", type=Path, default=None)
    p_collect.add_argument("--mirrors-dir", type=Path, default=Path("data/mirrors"))
    p_collect.add_argument("--source", action="append", default=None, help="Limit to source id")
    p_collect.add_argument("--no-fetch", action="store_true")
    p_collect.add_argument("--repo", type=Path, default=None, help="Use this repo for all (tests)")
    p_collect.add_argument("--out", type=Path, default=Path("data/last_collect.json"))

    p_report = sub.add_parser("report", help="Build Saturday Markdown from collect JSON")
    p_report.add_argument("--in", dest="infile", type=Path, default=Path("data/last_collect.json"))
    p_report.add_argument("--reports-dir", type=Path, default=Path("reports"))
    p_report.add_argument("--stdout", action="store_true")

    p_run = sub.add_parser("run", help="collect + report for the closed Fri→Fri window")
    p_run.add_argument("--as-of", type=str, default=None)
    p_run.add_argument("--sources-dir", type=Path, default=None)
    p_run.add_argument("--mirrors-dir", type=Path, default=Path("data/mirrors"))
    p_run.add_argument("--source", action="append", default=None)
    p_run.add_argument("--no-fetch", action="store_true")
    p_run.add_argument("--reports-dir", type=Path, default=Path("reports"))

    args = parser.parse_args(argv)

    if args.cmd == "week":
        return cmd_week(args.as_of)
    if args.cmd == "collect":
        return cmd_collect(args)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "run":
        return cmd_run(args)
    return 2


def _parse_as_of(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def cmd_week(as_of: str | None) -> int:
    window = friday_friday_window(as_of=_parse_as_of(as_of))
    pub = publish_saturday(window)
    print(f"window:  {window.label} ({window.timezone})")
    print(f"start:   {window.start.isoformat()}")
    print(f"end:     {window.end.isoformat()} (exclusive)")
    print(f"publish: {pub.isoformat()} (Saturday)")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    window = friday_friday_window(as_of=_parse_as_of(args.as_of))
    src_dir = args.sources_dir or sources_dir()
    sources = load_sources(src_dir)
    if args.source:
        wanted = set(args.source)
        sources = [s for s in sources if s.id in wanted]
    sources = [s for s in sources if s.enabled and s.kind == "git"]

    results: list[CollectResult] = []
    all_stories: list[Story] = []
    for source in sources:
        print(f"collecting {source.id} …", file=sys.stderr)
        result = collect_git(
            source,
            window,
            args.mirrors_dir,
            fetch=not args.no_fetch,
            repo_path=args.repo,
        )
        results.append(result)
        all_stories.extend(result.stories)
        print(f"  → {len(result.stories)} commits", file=sys.stderr)

    payload = {
        "window": window.model_dump(mode="json"),
        "results": [r.model_dump(mode="json") for r in results],
        "stories": [s.model_dump(mode="json") for s in all_stories],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(all_stories)} stories)", file=sys.stderr)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    raw = json.loads(args.infile.read_text(encoding="utf-8"))
    from csweekly.models import Window

    window = Window.model_validate(raw["window"])
    stories = [Story.model_validate(s) for s in raw["stories"]]
    issue = build_issue(window, stories)
    text = render_markdown(issue)
    if args.stdout:
        print(text)
    path = write_issue(issue, args.reports_dir)
    print(f"wrote {path}", file=sys.stderr)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    out = Path("data/last_collect.json")
    rc = cmd_collect(
        argparse.Namespace(
            as_of=args.as_of,
            sources_dir=args.sources_dir,
            mirrors_dir=args.mirrors_dir,
            source=args.source,
            no_fetch=args.no_fetch,
            repo=None,
            out=out,
        )
    )
    if rc != 0:
        return rc
    return cmd_report(
        argparse.Namespace(infile=out, reports_dir=args.reports_dir, stdout=False)
    )


if __name__ == "__main__":
    raise SystemExit(main())
