# SPDX-License-Identifier: Apache-2.0
"""Select groups for the published newsletter — not a commit dump."""

from __future__ import annotations

from csweekly.models import ChangeGroup, EvidenceKind, Importance, Story

# Soft caps per section so the issue stays readable; overflow stays in changelog.
_CAPS: dict[str, int] = {
    "llvm": 28,
    "gcc": 18,
    "mlir": 16,
    "ai": 18,
    "gpu": 16,
    "other": 14,
    "research": 12,
    "release": 12,
    "community": 12,
}


def select_for_newsletter(groups: list[ChangeGroup]) -> list[ChangeGroup]:
    """Keep highlights + notables first; fill with other only if sparse."""
    by_cat: dict[str, list[ChangeGroup]] = {}
    for g in groups:
        by_cat.setdefault(g.category, []).append(g)

    selected: list[ChangeGroup] = []
    for cat, items in by_cat.items():
        cap = _CAPS.get(cat, 16)
        ranked = sorted(
            items,
            key=lambda g: (
                {Importance.HIGHLIGHT: 0, Importance.NOTABLE: 1, Importance.OTHER: 2}[
                    g.importance
                ],
                -len(g.stories),
                g.title.lower(),
            ),
        )
        keep: list[ChangeGroup] = []
        for g in ranked:
            if g.importance in {Importance.HIGHLIGHT, Importance.NOTABLE}:
                keep.append(g)
            elif len(keep) < max(6, cap // 3):
                # sparse week: a few "other" entries for signal
                keep.append(g)
            if len(keep) >= cap:
                break
        selected.extend(keep)
    return selected


def split_non_git(stories: list[Story]) -> dict[str, list[Story]]:
    """Bucket non-git evidence for editorial side sections."""
    out: dict[str, list[Story]] = {
        "releases": [],
        "research": [],
        "community": [],
    }
    for s in stories:
        kind = s.evidence_kind
        if kind == EvidenceKind.GITHUB_RELEASE:
            out["releases"].append(s)
        elif kind == EvidenceKind.ARXIV:
            out["research"].append(s)
        elif kind in {EvidenceKind.RSS, EvidenceKind.WEB_ANNOUNCEMENT}:
            if s.category == "research":
                out["research"].append(s)
            else:
                out["community"].append(s)
        elif kind == EvidenceKind.MANUAL:
            out["community"].append(s)
    return out


def editorial_blurb(story: Story) -> str:
    """One-line factual blurb from the commit/subject — no invented impact."""
    text = (story.summary or story.title).strip()
    # Prefer original subject without author prefix "Name: "
    if ": " in text and len(text.split(": ", 1)[0]) < 40:
        left, right = text.split(": ", 1)
        if left and " " in left and not left.startswith("["):
            if not any(c in left for c in "/\\"):
                text = right
    return text[:280]
