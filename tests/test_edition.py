# SPDX-License-Identifier: Apache-2.0
from datetime import date, datetime, timezone
from pathlib import Path

from csweekly.edition import (
    EditionStatus,
    ensure_edition,
    freeze_edition,
    is_publicly_visible,
    load_meta,
    load_raw_stories,
    merge_raw_stories,
    set_status,
)
from csweekly.models import EvidenceKind, Story


def _story(sha: str, title: str = "t") -> Story:
    return Story(
        id=f"llvm:{sha}",
        title=title,
        source_url=f"https://github.com/llvm/llvm-project/commit/{sha}",
        source_org="LLVM",
        category="llvm",
        project="LLVM",
        discovered_at=datetime.now(timezone.utc),
        evidence_kind=EvidenceKind.GIT_COMMIT,
        summary=title,
        related_ref=sha,
    )


def test_idempotent_raw_merge(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    meta, edir = ensure_edition(as_of=date(2026, 11, 5), mode="collecting")
    assert meta.status == EditionStatus.collecting

    a, total = merge_raw_stories(edir, [_story("aaa"), _story("bbb")])
    assert a == 2 and total == 2
    a2, total2 = merge_raw_stories(edir, [_story("aaa"), _story("ccc")])
    assert a2 == 1 and total2 == 3
    assert len(load_raw_stories(edir)) == 3


def test_freeze_blocks_further_collect(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, edir = ensure_edition(as_of=date(2026, 11, 5), mode="collecting")
    merge_raw_stories(edir, [_story("aaa")])
    freeze_edition(edir)
    meta = load_meta(edir)
    assert meta.status == EditionStatus.processing
    assert meta.frozen_at
    try:
        merge_raw_stories(edir, [_story("bbb")])
        assert False, "expected freeze error"
    except RuntimeError as exc:
        assert "frozen" in str(exc).lower()


def test_legacy_report_without_edition_is_public():
    assert is_publicly_visible(date(2026, 11, 7), root=Path("/tmp/no-editions-here"))


def test_collecting_edition_not_public(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    meta, edir = ensure_edition(as_of=date(2026, 11, 5), mode="collecting")
    assert not is_publicly_visible(meta.published_at or date(2026, 11, 7), root=tmp_path)
    set_status(edir, EditionStatus.published)
    # published_at already set on meta
    meta = load_meta(edir)
    meta.status = EditionStatus.published
    from csweekly.edition import save_meta

    save_meta(meta, edir)
    assert is_publicly_visible(meta.published_at, root=tmp_path)
