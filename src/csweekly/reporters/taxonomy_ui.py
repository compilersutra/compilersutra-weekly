# SPDX-License-Identifier: Apache-2.0
"""Independent taxonomy chips: project · stage · domain · target."""

from __future__ import annotations

import html
from typing import Any


def _uniq(items: list[str], *, limit: int = 3) -> list[str]:
    out: list[str] = []
    for item in items:
        text = (item or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def taxonomy_fields(g: dict[str, Any] | None) -> dict[str, list[str]]:
    """Split mixed labels into independent dimensions."""
    g = g or {}
    project = g.get("project") or g.get("category") or ""
    projects = _uniq([str(project).upper() if project else ""], limit=1)
    if projects == [""]:
        projects = []
    return {
        "project": projects,
        "stage": _uniq(list(g.get("stages") or []), limit=2),
        "domain": _uniq(list(g.get("domains") or []), limit=2),
        "target": _uniq(list(g.get("hardware_targets") or []), limit=2),
        "type": _uniq([str(g.get("change_type") or "")], limit=1),
        "level": _uniq([str(g.get("editorial_level") or "")], limit=1),
    }


def taxonomy_badges_html(g: dict[str, Any] | None, *, include_type: bool = False) -> str:
    """Compact chips with dimension hints — never concatenates bare words."""
    fields = taxonomy_fields(g)
    order = [
        ("project", fields["project"]),
        ("stage", fields["stage"]),
        ("domain", fields["domain"]),
        ("target", fields["target"]),
    ]
    if include_type and fields["type"]:
        order.append(("type", fields["type"]))
    if fields["level"]:
        order.append(("level", fields["level"]))
    chips: list[str] = []
    for dim, values in order:
        for value in values:
            chips.append(
                f'<span class="badge tax-{html.escape(dim)}" '
                f'data-dim="{html.escape(dim)}" title="{html.escape(dim)}">'
                f'<span class="tax-dim">{html.escape(dim)}</span>'
                f"{html.escape(value)}</span>"
            )
    if not chips:
        return ""
    return f'<div class="badge-row">{"".join(chips)}</div>'


def taxonomy_line(g: dict[str, Any] | None) -> str:
    """Single muted line: Project · Stage · Domain · Target (no duplicate Stage: labels)."""
    fields = taxonomy_fields(g)
    parts: list[str] = []
    for key in ("project", "stage", "domain", "target"):
        if fields[key]:
            parts.append(html.escape(" · ".join(fields[key])))
    return " · ".join(parts)


def format_issue_date(iso: str) -> str:
    """Render YYYY-MM-DD as '7 Nov 2026' without HTML entities."""
    from datetime import date

    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day} {d.strftime('%b')} {d.year}"
