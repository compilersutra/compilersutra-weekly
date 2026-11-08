# SPDX-License-Identifier: Apache-2.0
"""Group related commits within the same project."""

from __future__ import annotations

import re
from collections import defaultdict

from csweekly.analyzers.importance import assign_importance
from csweekly.models import ChangeGroup, Importance, Story


def subject_key(title: str) -> str:
    return _subject_key(title)


def _subject_key(title: str) -> str:
    m = re.match(r"^\[([^\]]+)\]\s*(.*)$", title.strip())
    if m:
        label = m.group(1).strip().lower()
        rest = m.group(2).strip()
        if ":" in rest:
            head = rest.split(":", 1)[0].strip()
            if 2 <= len(head) <= 48:
                return f"{label}:{head.lower()}"
        tokens = re.findall(r"[A-Za-z0-9_+.-]+", rest)
        return f"{label}:{' '.join(tokens[:2]).lower()}" if tokens else label
    t = title.strip()
    if ":" in t:
        head = t.split(":", 1)[0].strip()
        if 2 <= len(head) <= 48:
            return head.lower()
    tokens = re.findall(r"[A-Za-z0-9_+.-]+", t)
    return " ".join(tokens[:4]).lower() if tokens else t.lower()[:40]


def _path_key(paths: list[str]) -> str:
    dirs = []
    for p in paths[:12]:
        parts = p.split("/")
        dirs.append("/".join(parts[:3]) if len(parts) >= 3 else p)
    if not dirs:
        return ""
    counts: dict[str, int] = defaultdict(int)
    for d in dirs:
        counts[d] += 1
    return max(counts, key=counts.get)


def group_stories(stories: list[Story]) -> list[ChangeGroup]:
    buckets: dict[str, list[Story]] = defaultdict(list)
    for s in stories:
        if s.evidence_kind.value != "git_commit":
            key = f"single:{s.id}"
        else:
            sk = _subject_key(s.title)
            pk = _path_key(s.paths)
            key = f"{s.project or s.category}|{sk}|{pk}"
        buckets[key].append(s)

    groups: list[ChangeGroup] = []
    for key, members in buckets.items():
        members = sorted(
            members,
            key=lambda s: s.published_at.timestamp() if s.published_at else 0,
            reverse=True,
        )
        for m in members:
            m.importance = assign_importance(m)
            m.group_id = key
        order = {Importance.HIGHLIGHT: 0, Importance.NOTABLE: 1, Importance.OTHER: 2}
        best = min((m.importance for m in members), key=lambda i: order[i])
        title = members[0].title
        if len(members) > 1:
            base = _subject_key(members[0].title) or members[0].title
            title = f"{base} ({len(members)} commits)"
        areas: list[str] = []
        for m in members:
            for a in m.areas:
                if a not in areas:
                    areas.append(a)
            m.group_title = title
        groups.append(
            ChangeGroup(
                id=key,
                title=title,
                category=members[0].category,
                project=members[0].project or members[0].category,
                areas=areas[:6],
                importance=best,
                stories=members,
            )
        )

    groups.sort(
        key=lambda g: (
            {Importance.HIGHLIGHT: 0, Importance.NOTABLE: 1, Importance.OTHER: 2}[
                g.importance
            ],
            -len(g.stories),
            g.title.lower(),
        )
    )
    return groups
