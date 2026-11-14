# SPDX-License-Identifier: Apache-2.0
"""Independent taxonomy chips: project · stage · domain · target · evidence."""

from __future__ import annotations

import html
import re
from typing import Any

LEVEL_LABELS = {
    "deep_dive": "Deep dive",
    "engineering_analysis": "Engineering analysis",
    "quick_signal": "Quick signal",
}

PROJECT_LABELS = {
    "llvm": "LLVM",
    "clang": "Clang",
    "gcc": "GCC",
    "mlir": "MLIR",
    "ai": "AI",
    "gpu": "GPU",
    "research": "Research",
}

# Map display / alias names onto the ecosystem colour tokens.
PROJECT_COLOR_KEYS = {
    "llvm": "llvm",
    "clang": "clang",
    "gcc": "gcc",
    "mlir": "mlir",
    "ai": "ai",
    "gpu": "gpu",
    "research": "research",
    "iree": "ai",
    "tvm": "ai",
    "xla": "ai",
    "triton": "ai",
    "circt": "mlir",
}


def css_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def project_color_key(raw: str) -> str:
    key = css_slug(raw)
    if key in PROJECT_COLOR_KEYS:
        return PROJECT_COLOR_KEYS[key]
    for alias, mapped in PROJECT_COLOR_KEYS.items():
        if alias in key:
            return mapped
    return key or "other"


def _uniq(items: list[str], *, limit: int = 3) -> list[str]:
    out: list[str] = []
    for item in items:
        text = (item or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _project_label(raw: str) -> str:
    key = (raw or "").strip()
    if not key:
        return ""
    return PROJECT_LABELS.get(key.lower(), key[:1].upper() + key[1:] if key.islower() else key)


def evidence_confidence(g: dict[str, Any] | None) -> tuple[str, str]:
    """Return (display label, css slug) for evidence trust.

    Verified | Source-backed | Inferred | Unverified
    """
    g = g or {}
    notes = g.get("deep_dive_notes") or {}
    conf = str(notes.get("confidence") or "").lower()
    fc = str(notes.get("factcheck") or "").lower()
    validation = str(notes.get("validation") or "").lower()
    has_tests = "test" in validation and "no obvious test" not in validation
    if conf == "high" and fc == "pass" and has_tests:
        return "Verified", "verified"
    if conf in {"high", "medium"} and fc == "pass":
        return "Source-backed", "source-backed"
    if conf == "low" or fc == "fail":
        return "Inferred", "inferred"
    if not conf:
        return "Unverified", "unverified"
    return "Inferred", "inferred"


def taxonomy_fields(g: dict[str, Any] | None) -> dict[str, list[str]]:
    """Split mixed labels into independent dimensions."""
    g = g or {}
    project = g.get("project") or g.get("category") or ""
    projects = _uniq([_project_label(str(project))], limit=1)
    if projects == [""]:
        projects = []
    level_raw = str(g.get("editorial_level") or "")
    level = LEVEL_LABELS.get(level_raw, level_raw.replace("_", " ").title() if level_raw else "")
    return {
        "project": projects,
        "stage": _uniq(list(g.get("stages") or []), limit=2),
        "domain": _uniq(list(g.get("domains") or []), limit=2),
        "target": _uniq(list(g.get("hardware_targets") or []), limit=2),
        "type": _uniq([str(g.get("change_type") or "")], limit=1),
        "level": _uniq([level], limit=1),
    }


def taxonomy_badges_html(
    g: dict[str, Any] | None, *, include_type: bool = False, include_evidence: bool = True
) -> str:
    """Compact chips with dimension hints — never concatenates bare words."""
    g = g or {}
    fields = taxonomy_fields(g)
    raw_project = str(g.get("project") or g.get("category") or "")
    project_key = project_color_key(raw_project)
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
            extra = ""
            if dim == "project":
                extra = f" project-{html.escape(project_key)}"
            elif dim == "stage":
                extra = f" stage-{html.escape(css_slug(value))}"
            chips.append(
                f'<span class="badge tax-{html.escape(dim)}{extra}" '
                f'data-dim="{html.escape(dim)}" title="{html.escape(dim)}">'
                f'<span class="tax-dim">{html.escape(dim)}</span>'
                f"{html.escape(value)}</span>"
            )
    if include_evidence:
        label, slug = evidence_confidence(g)
        chips.append(
            f'<span class="badge tax-evidence evidence-{html.escape(slug)}" '
            f'data-dim="evidence" title="Evidence confidence">'
            f'<span class="tax-dim">evidence</span>{html.escape(label)}</span>'
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
