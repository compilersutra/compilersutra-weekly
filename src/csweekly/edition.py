# SPDX-License-Identifier: Apache-2.0
"""Weekly edition lifecycle: raw → normalized → stories → published.

Public site consumes only editions with status ``published``.
Raw collection accumulates under ``data/editions/`` and is never the
reader-facing newsletter by itself.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel

from csweekly.models import Story, Window, WeeklyIssue
from csweekly.window import (
    collecting_window,
    publish_saturday,
    publishable_window,
)


class EditionStatus(str, Enum):
    collecting = "collecting"
    processing = "processing"
    review = "review"
    ready = "ready"
    published = "published"
    archived = "archived"


class StoryEditorialStatus(str, Enum):
    new = "new"
    candidate = "candidate"
    selected = "selected"
    featured = "featured"
    worth_knowing = "worth_knowing"
    research = "research"
    rejected = "rejected"
    deferred = "deferred"
    published = "published"
    late = "late"
    next_issue = "next_issue"


class EditionMeta(BaseModel):
    id: str
    number: int | None = None
    period_start: date
    period_end: date
    published_at: date | None = None
    status: EditionStatus = EditionStatus.collecting
    timezone: str = "Asia/Kolkata"
    frozen_at: str | None = None
    notes: str = ""

    @property
    def label(self) -> str:
        return f"{self.period_start.isoformat()} → {self.period_end.isoformat()}"


def editions_root(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(".")
    return root / "data" / "editions"


def edition_dir(meta: EditionMeta, *, root: Path | None = None) -> Path:
    """``data/editions/YYYY/<publish-saturday>/``."""
    key = meta.published_at or (meta.period_end + timedelta(days=1))
    return editions_root(root) / f"{key.year}" / key.isoformat()


def edition_paths(edir: Path) -> dict[str, Path]:
    return {
        "meta": edir / "edition.yaml",
        "raw": edir / "raw" / "stories.jsonl",
        "normalized": edir / "normalized" / "stories.json",
        "stories": edir / "stories" / "candidates.json",
        "report": edir / "editorial_report.md",
        "freeze": edir / "freeze.json",
        "issue_draft": edir / "issue_draft.json",
    }


def window_to_meta(window: Window, *, number: int | None = None) -> EditionMeta:
    pub = publish_saturday(window)
    # Inclusive Friday calendar end for humans.
    period_end = pub - timedelta(days=1)
    return EditionMeta(
        id=pub.isoformat(),
        number=number,
        period_start=window.start.date(),
        period_end=period_end,
        published_at=pub,
        status=EditionStatus.collecting,
        timezone=window.timezone,
    )


def ensure_edition(
    *,
    as_of: date | None = None,
    mode: str = "collecting",
    root: Path | None = None,
    number: int | None = None,
) -> tuple[EditionMeta, Path]:
    """Create or load the edition for collection or publishable week."""
    window = (
        collecting_window(as_of=as_of)
        if mode == "collecting"
        else publishable_window(as_of=as_of)
    )
    meta = window_to_meta(window, number=number)
    edir = edition_dir(meta, root=root)
    paths = edition_paths(edir)
    if paths["meta"].is_file():
        meta = load_meta(edir)
        return meta, edir
    edir.mkdir(parents=True, exist_ok=True)
    (edir / "raw").mkdir(exist_ok=True)
    (edir / "normalized").mkdir(exist_ok=True)
    (edir / "stories").mkdir(exist_ok=True)
    save_meta(meta, edir)
    return meta, edir


def load_meta(edir: Path) -> EditionMeta:
    raw = yaml.safe_load(edition_paths(edir)["meta"].read_text(encoding="utf-8"))
    return EditionMeta.model_validate(raw)


def save_meta(meta: EditionMeta, edir: Path) -> Path:
    path = edition_paths(edir)["meta"]
    path.parent.mkdir(parents=True, exist_ok=True)
    data = meta.model_dump(mode="json")
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def set_status(edir: Path, status: EditionStatus, *, frozen: bool = False) -> EditionMeta:
    meta = load_meta(edir)
    if meta.status == EditionStatus.published and status != EditionStatus.archived:
        raise RuntimeError(
            f"Edition {meta.id} is published/frozen; refuse status → {status.value}"
        )
    meta.status = status
    if frozen or status == EditionStatus.published:
        meta.frozen_at = datetime.now(timezone.utc).isoformat()
    save_meta(meta, edir)
    return meta


def story_stable_key(story: Story) -> str:
    """Immutable-ish key for idempotent raw merges."""
    # Prefer related_ref (commit SHA / PR / arXiv) + URL; fall back to story.id.
    if story.related_ref and story.source_url:
        return f"{story.related_ref}|{story.source_url}"
    if story.related_ref:
        return f"ref:{story.related_ref}"
    if story.source_url:
        return f"url:{story.source_url}"
    return story.id


def load_raw_stories(edir: Path) -> list[Story]:
    path = edition_paths(edir)["raw"]
    if not path.is_file():
        return []
    out: list[Story] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(Story.model_validate(json.loads(line)))
    return out


def merge_raw_stories(edir: Path, stories: Iterable[Story]) -> tuple[int, int]:
    """Idempotent merge into raw/stories.jsonl. Returns (added, total)."""
    meta = load_meta(edir)
    if meta.status in {EditionStatus.published, EditionStatus.archived}:
        raise RuntimeError(f"Edition {meta.id} is frozen; cannot collect into it")
    if meta.frozen_at and meta.status not in {
        EditionStatus.collecting,
    }:
        # After Friday freeze, late items go to next edition — not silently into frozen.
        raise RuntimeError(
            f"Edition {meta.id} collection is frozen ({meta.status.value}); "
            "route late items to the next edition"
        )

    existing = {story_stable_key(s): s for s in load_raw_stories(edir)}
    added = 0
    for story in stories:
        key = story_stable_key(story)
        if key in existing:
            continue
        existing[key] = story
        added += 1

    path = edition_paths(edir)["raw"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(s.model_dump(mode="json"), ensure_ascii=False, default=str)
        for s in existing.values()
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    if meta.status == EditionStatus.collecting:
        save_meta(meta, edir)
    return added, len(existing)


def write_normalized(edir: Path, stories: list[Story]) -> Path:
    path = edition_paths(edir)["normalized"]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": len(stories),
        "stories": [s.model_dump(mode="json") for s in stories],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def write_candidates(edir: Path, candidates: list[dict[str, Any]]) -> Path:
    path = edition_paths(edir)["stories"]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"count": len(candidates), "candidates": candidates}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def load_candidates(edir: Path) -> list[dict[str, Any]]:
    path = edition_paths(edir)["stories"]
    if not path.is_file():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("candidates") or [])


def freeze_edition(edir: Path) -> EditionMeta:
    """Friday close: stop collecting; keep raw forever."""
    meta = load_meta(edir)
    if meta.status == EditionStatus.published:
        return meta
    meta.status = EditionStatus.processing
    meta.frozen_at = datetime.now(timezone.utc).isoformat()
    save_meta(meta, edir)
    freeze_path = edition_paths(edir)["freeze"]
    freeze_path.write_text(
        json.dumps(
            {
                "frozen_at": meta.frozen_at,
                "raw_count": len(load_raw_stories(edir)),
                "period_start": meta.period_start.isoformat(),
                "period_end": meta.period_end.isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return meta


def mark_published(edir: Path, issue: WeeklyIssue) -> EditionMeta:
    meta = load_meta(edir)
    meta.status = EditionStatus.published
    meta.published_at = issue.published_on
    meta.number = meta.number  # may be set by caller
    meta.frozen_at = meta.frozen_at or datetime.now(timezone.utc).isoformat()
    save_meta(meta, edir)
    # Snapshot published marker next to reports for the static site.
    return meta


def find_edition_for_publish_date(
    published_on: date, *, root: Path | None = None
) -> Path | None:
    edir = editions_root(root) / f"{published_on.year}" / published_on.isoformat()
    if (edir / "edition.yaml").is_file():
        return edir
    return None


def list_edition_dirs(root: Path | None = None) -> list[Path]:
    base = editions_root(root)
    if not base.is_dir():
        return []
    out: list[Path] = []
    for year in sorted(base.iterdir()):
        if not year.is_dir():
            continue
        for edir in sorted(year.iterdir()):
            if (edir / "edition.yaml").is_file():
                out.append(edir)
    return out


def is_publicly_visible(published_on: date, *, root: Path | None = None) -> bool:
    """Site may show an issue only if published (or legacy pre-edition report)."""
    edir = find_edition_for_publish_date(published_on, root=root)
    if edir is None:
        # Legacy reports without edition.yaml remain public.
        return True
    return load_meta(edir).status in {
        EditionStatus.published,
        EditionStatus.archived,
    }


def editorial_counts(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in candidates:
        status = str((c.get("editorial") or {}).get("status") or "new")
        counts[status] = counts.get(status, 0) + 1
    return counts


def write_editorial_report(
    edir: Path,
    *,
    raw_count: int,
    normalized_count: int,
    cluster_count: int,
    candidates: list[dict[str, Any]],
) -> Path:
    meta = load_meta(edir)
    counts = editorial_counts(candidates)
    featured = counts.get("featured", 0) + counts.get("selected", 0)
    lines = [
        f"# CompilerSutra Weekly — Issue #{meta.number or meta.id}",
        "",
        f"Period: {meta.period_start.isoformat()} → {meta.period_end.isoformat()}",
        f"Status: {meta.status.value}",
        f"Timezone: {meta.timezone}",
        "",
        "## Collection",
        "",
        f"- Raw items: {raw_count}",
        f"- Unique normalized: {normalized_count}",
        "",
        "## Processing",
        "",
        f"- Clusters / candidates: {cluster_count}",
        "",
        "## Editorial",
        "",
        f"- Featured / selected: {featured}",
        f"- Worth knowing: {counts.get('worth_knowing', 0)}",
        f"- Research: {counts.get('research', 0)}",
        f"- Rejected: {counts.get('rejected', 0)}",
        f"- Deferred: {counts.get('deferred', 0)}",
        f"- New / candidate: {counts.get('new', 0) + counts.get('candidate', 0)}",
        "",
        "## Quality gate",
        "",
        "Run `csweekly validate` before Saturday publish.",
        "",
    ]
    path = edition_paths(edir)["report"]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
