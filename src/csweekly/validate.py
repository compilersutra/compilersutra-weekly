# SPDX-License-Identifier: Apache-2.0
"""Pre-publish quality gates for a weekly edition / issue."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from csweekly.edition import (
    EditionStatus,
    editorial_counts,
    load_candidates,
    load_meta,
    load_raw_stories,
)
from csweekly.models import WeeklyIssue


@dataclass
class GateResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "", *, warning: bool = False) -> None:
        self.checks.append((name, passed, detail))
        if passed:
            return
        msg = f"{name}: {detail}" if detail else name
        if warning:
            self.warnings.append(msg)
        else:
            self.errors.append(msg)
            self.ok = False


def validate_edition(edir: Path, issue: WeeklyIssue | None = None) -> GateResult:
    result = GateResult(ok=True)
    meta = load_meta(edir)
    raw = load_raw_stories(edir)
    candidates = load_candidates(edir)
    counts = editorial_counts(candidates)

    result.add(
        "Week boundary valid",
        meta.period_start < meta.period_end
        and (meta.published_at is None or meta.published_at > meta.period_end),
        f"{meta.period_start} → {meta.period_end} publish {meta.published_at}",
    )

    # Duplicate raw keys
    keys = []
    for s in raw:
        keys.append(s.id)
        if s.source_url:
            keys.append(s.source_url)
    dup_ids = len(keys) - len(set(keys))
    result.add("No duplicate commit/story keys in raw", dup_ids == 0, f"extra={dup_ids}")

    story_ids = [c.get("id") for c in candidates if c.get("id")]
    result.add(
        "No duplicate story IDs",
        len(story_ids) == len(set(story_ids)),
        f"candidates={len(story_ids)}",
    )

    selected = [
        c
        for c in candidates
        if (c.get("editorial") or {}).get("status")
        in {"selected", "featured", "worth_knowing", "research", "published"}
    ]
    missing_source = [
        c.get("id") or c.get("title")
        for c in selected
        if not (c.get("source_url") or c.get("primary_source") or c.get("commits"))
    ]
    result.add(
        "Selected stories have primary sources",
        not missing_source,
        f"missing={missing_source[:5]}",
    )

    featured = [
        c
        for c in candidates
        if (c.get("editorial") or {}).get("status") in {"featured", "selected"}
    ]
    no_reason = [
        c.get("id")
        for c in featured
        if not (c.get("editorial") or {}).get("reason")
        and not c.get("why_it_matters")
    ]
    result.add(
        "Featured stories have explanations",
        not no_reason,
        f"missing={no_reason[:5]}",
    )

    # Raw must not equal public selection blindly
    if selected and raw and len(selected) >= len(raw) and len(raw) > 20:
        result.add(
            "Public issue is curated (not raw dump)",
            False,
            f"selected={len(selected)} raw={len(raw)}",
        )
    else:
        result.add(
            "Public issue is curated (not raw dump)",
            True,
            f"selected={len(selected)} raw={len(raw)}",
        )

    if meta.status == EditionStatus.published and not meta.published_at:
        result.add("Published edition has publication date", False)
    else:
        result.add(
            "Publication date present when required",
            meta.status != EditionStatus.published or meta.published_at is not None,
        )

    if issue is not None:
        urls = [s.source_url for s in issue.stories if s.source_url]
        result.add("Issue has source links", bool(urls), f"links={len(urls)}")
        # Unsupported performance claims heuristic
        bad = [
            g.title
            for g in (issue.high_signal or [])
            if "faster" in (g.why_it_matters or "").lower()
            and g.impact_uncertain
        ]
        result.add(
            "No unsupported performance claims in featured",
            not bad,
            f"flagged={bad[:3]}",
            warning=True,
        )
        # AI fact-check trail on deep dive / high signal
        fc_fail = []
        for g in list(issue.high_signal or []) + (
            [issue.deep_dive] if issue.deep_dive else []
        ):
            notes = g.deep_dive_notes or {}
            if notes.get("factcheck") == "fail":
                fc_fail.append(g.title)
            perf = (notes.get("performance") or "").lower()
            if any(k in perf for k in ("faster", "speedup", "%")) and (
                "not established" not in perf
            ):
                fc_fail.append(g.title)
        result.add(
            "AI fact-check passed on selected stories",
            not fc_fail,
            f"flagged={fc_fail[:3]}",
        )

    if counts.get("rejected", 0) == 0 and len(candidates) > 30:
        result.add(
            "Editorial rejections recorded",
            False,
            "large candidate set with zero rejects — review may be incomplete",
            warning=True,
        )
    else:
        result.add("Editorial queue present", True, str(counts))

    return result


def format_gate_report(result: GateResult) -> str:
    lines = ["csweekly validate", ""]
    for name, passed, detail in result.checks:
        mark = "✓" if passed else "✗"
        suffix = f" — {detail}" if detail else ""
        lines.append(f"{mark} {name}{suffix}")
    lines.append("")
    if result.ok and not result.errors:
        lines.append("Ready to publish: YES")
    else:
        lines.append("Ready to publish: NO")
        lines.append("")
        lines.append(f"{len(result.errors)} errors")
        lines.append(f"{len(result.warnings)} warnings")
        for e in result.errors:
            lines.append(f"  ERROR: {e}")
        for w in result.warnings:
            lines.append(f"  WARN: {w}")
    return "\n".join(lines) + "\n"
