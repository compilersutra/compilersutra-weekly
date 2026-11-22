# SPDX-License-Identifier: Apache-2.0
"""Publication presentation layer — briefing cards, headlines, evidence-safe copy.

Does not invent engineering claims. Rewrites only generic boilerplate so the
HTML/Markdown surface reads like a compiler-engineering briefing.
"""

from __future__ import annotations

import re
from typing import Any

from csweekly.processors.editorial import _briefing_slot_label, _clip_words, clean_subject
from csweekly.reporters.taxonomy_ui import evidence_confidence

_GENERIC_WHY = re.compile(
    r"(?i)\b(matters for .+? compiler engineering|lives in the .+? of the pipeline|"
    r"affects .+? lowering / target code generation|primary audience:)\b"
)
_PR = re.compile(r"\s*\(#\d+\)\s*$")
_NOT_ESTABLISHED = re.compile(r"(?i)not established|insufficient evidence|see linked|unlisted")


def editorial_headline(g: dict[str, Any] | None) -> str:
    """Human headline from title/subject — strip brackets and PR numbers."""
    g = g or {}
    raw = (g.get("title") or "").strip()
    cleaned = clean_subject(raw) or raw
    cleaned = _PR.sub("", cleaned).strip()
    return _clip_words(cleaned or "Untitled development", 96)


def path_grounded_targets(g: dict[str, Any] | None) -> list[str]:
    """Keep hardware targets only when paths/subjects support them."""
    g = g or {}
    claimed = [t for t in (g.get("hardware_targets") or []) if t]
    if not claimed:
        return []
    primary_paths = " ".join(
        p for p in ((g.get("stories") or [{}])[0].get("paths") or [])[:16]
    ).lower()
    all_paths = " ".join(
        p for s in (g.get("stories") or []) for p in (s.get("paths") or [])[:8]
    ).lower()
    subject = f"{g.get('title') or ''}\n{g.get('what_changed') or ''}".lower()
    # Debugger / LLDB API tests: only keep targets named in the subject/body.
    if "lldb/" in primary_paths or "lldb/" in all_paths:
        keep = []
        for t in claimed:
            tl = t.lower()
            aliases = _target_path_tips(t) + [tl]
            if any(a in subject for a in aliases):
                keep.append(t)
        return keep[:3]
    blob = f"{all_paths}\n{subject}"
    out: list[str] = []
    for t in claimed:
        tips = _target_path_tips(t)
        if any(tip in blob for tip in tips):
            out.append(t)
    return out[:3] if out else claimed[:2]


def _target_path_tips(target: str) -> list[str]:
    t = target.lower()
    tips = {
        "amdgpu": ["amdgpu", "amdgcn"],
        "nvptx": ["nvptx", "nvvm"],
        "x86": ["x86", "i386"],
        "aarch64": ["aarch64", "arm64"],
        "riscv": ["riscv", "risc-v"],
        "webassembly": ["wasm", "webassembly"],
        "spir-v": ["spirv", "spir-v"],
    }
    for key, vals in tips.items():
        if key in t or t in key:
            return vals
    return [t]


def sanitize_group_for_display(g: dict[str, Any]) -> dict[str, Any]:
    """Shallow copy with path-grounded targets/audience for UI (does not mutate source)."""
    out = dict(g)
    targets = path_grounded_targets(g)
    out["hardware_targets"] = targets
    out["who_should_care"] = scrub_audience(g.get("who_should_care") or [], targets)
    # Never surface raw file/symbol dumps in reading fields.
    ctx = out.get("technical_context") or ""
    if re.match(r"(?i)^primary\s+`", ctx.strip()) or "Files:" in ctx[:100]:
        out["technical_context"] = implementation_explanation(out)
    why = out.get("why_it_matters") or ""
    if _GENERIC_WHY.search(why):
        out["why_it_matters"] = engineering_takeaway(out)
    return out


def scrub_audience(who: list[str], targets: list[str]) -> list[str]:
    """Drop audience labels for hardware not supported by path-grounded targets."""
    allowed = {t.lower() for t in targets}
    cpu_isas = {"x86", "aarch64", "riscv", "arm", "powerpc", "cpu"}
    out: list[str] = []
    for label in who:
        low = label.strip().lower()
        m = re.match(r"^(.+?)\s+backend engineers$", low)
        if m and allowed:
            name = m.group(1).strip()
            if not any(name == a or name in a or a in name for a in allowed):
                continue
        if low == "cpu developers" and allowed and not (allowed & cpu_isas):
            continue
        out.append(label)
    return out or list(who)[:3]


def engineering_takeaway(g: dict[str, Any] | None) -> str:
    """Short implication for briefing cards — never copy generic taxonomy filler."""
    g = g or {}
    why = (g.get("why_it_matters") or "").strip()
    what = (g.get("what_changed") or "").strip()
    notes = g.get("deep_dive_notes") or {}
    impl_hint = (notes.get("implications") or "").strip()

    candidates = [why, impl_hint]
    for c in candidates:
        if c and not _GENERIC_WHY.search(c) and _clip_words(c, 80) != _clip_words(what, 80):
            return _clip_words(c, 220)

    # Derive a grounded takeaway from what_changed + stage without inventing mechanism.
    stage = (g.get("stages") or ["compiler"])[0]
    domain = (g.get("domains") or ["engineering"])[0]
    targets = path_grounded_targets(g)
    target_bit = f" ({', '.join(targets[:2])})" if targets else ""
    if what:
        first = _first_sentence(what, limit=220)
        return (
            f"{first} Engineering focus: {stage}{target_bit} — "
            f"{domain} teams should confirm behavior in the linked source."
        )
    return (
        f"{stage} change{target_bit}. "
        "Inspect the primary commit before treating this as a broader architecture shift."
    )


def briefing_slot(g: dict[str, Any], index: int) -> str:
    """Map group dict onto editorial slot labels."""
    from csweekly.models import ChangeGroup, SignalLevel

    signal_raw = g.get("signal") or ""
    try:
        signal = SignalLevel(signal_raw) if signal_raw else SignalLevel.WORTH_KNOWING
    except ValueError:
        signal = SignalLevel.WORTH_KNOWING
    stub = ChangeGroup(
        id=str(g.get("id") or g.get("story_id") or f"b{index}"),
        title=str(g.get("title") or ""),
        category=str(g.get("category") or "other"),
        project=str(g.get("project") or g.get("category") or "other"),
        stages=list(g.get("stages") or []),
        domains=list(g.get("domains") or []),
        hardware_targets=path_grounded_targets(g),
        signal=signal,
        stories=[],
    )
    return _briefing_slot_label(stub, index)


def briefing_kicker(slot: str, index: int) -> str:
    mapping = {
        "The biggest development": "FEATURED",
        "GPU / accelerator compilers": "GPU SIGNAL",
        "Backend and code generation": "BACKEND",
        "Frontend and language infrastructure": "FRONTEND",
        "Research worth reading": "RESEARCH",
    }
    if index == 0:
        return "01 · FEATURED"
    label = mapping.get(slot, "SIGNAL")
    return f"{index + 1:02d} · {label}"


def briefing_cards_from_payload(payload: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    """Build five-minute briefing cards from deep dive + high signal (+ worth)."""
    deep = payload.get("deep_dive")
    high = list(payload.get("high_signal") or [])
    worth = list(payload.get("worth_knowing") or [])
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(g: dict[str, Any] | None) -> None:
        if not g:
            return
        sid = str(g.get("story_id") or g.get("id") or "")
        if sid and sid in seen:
            return
        if sid:
            seen.add(sid)
        ordered.append(sanitize_group_for_display(g))

    _add(deep)
    for g in high:
        _add(g)
        if len(ordered) >= limit:
            break
    if len(ordered) < limit:
        for g in worth:
            _add(g)
            if len(ordered) >= limit:
                break

    cards: list[dict[str, Any]] = []
    used_slots: set[str] = set()
    for i, g in enumerate(ordered[:limit]):
        slot = briefing_slot(g, i)
        if slot in used_slots and i > 0:
            slot = "Also on the radar"
        used_slots.add(slot)
        stories = g.get("stories") or []
        primary = stories[0] if stories else {}
        ev_label, ev_slug = evidence_confidence(g)
        stage = (g.get("stages") or ["—"])[0]
        cards.append(
            {
                "index": i,
                "kicker": briefing_kicker(slot, i),
                "slot": slot,
                "headline": editorial_headline(g),
                "summary": _first_sentence(
                    g.get("what_changed") or g.get("title") or "", limit=200
                ),
                "takeaway": engineering_takeaway(g),
                "stage": stage,
                "project": g.get("project") or g.get("category") or "",
                "targets": path_grounded_targets(g),
                "anchor": _anchor(g),
                "sha": (primary.get("related_ref") or "")[:8],
                "source_url": primary.get("source_url") or "#",
                "evidence_label": ev_label,
                "evidence_slug": ev_slug,
                "group": g,
            }
        )
    return cards


def briefing_overview_lines(cards: list[dict[str, Any]]) -> list[str]:
    """Flat overview strings for changelog / markdown compatibility."""
    lines: list[str] = []
    for c in cards:
        lines.append(
            f"{c['index'] + 1:02d} — {c['slot']}: {c['headline']}. "
            f"{_clip_words(c['takeaway'], 140)} ({c['stage']})"
        )
    return lines or ["Quiet week in the tracked sources — no high-signal themes stood out."]


def coverage_tier(g: dict[str, Any] | None) -> str:
    """featured | quick_signal | watchlist"""
    g = g or {}
    level = str(g.get("editorial_level") or "")
    signal = str(g.get("signal") or "")
    ev_label, _ = evidence_confidence(g)
    if signal == "deep_dive" or level == "deep_dive":
        return "featured"
    if signal == "high_signal" or level == "engineering_analysis":
        return "featured" if ev_label in {"Verified", "Source-backed"} else "quick_signal"
    if ev_label in {"Unverified", "Inferred"} or g.get("impact_uncertain"):
        return "watchlist"
    return "quick_signal"


def watchlist_bucket(g: dict[str, Any] | None) -> str:
    """needs_inspection | potentially_important | low_priority"""
    g = g or {}
    title = (g.get("title") or "").lower()
    n_related = max(0, len(g.get("stories") or []) - 1)
    score = g.get("impact_score")
    score_f = float(score) if isinstance(score, (int, float)) else 0.0
    stages = " ".join(g.get("stages") or []).lower()
    domains = " ".join(g.get("domains") or []).lower()
    low = (
        "comment",
        "nfc",
        "typo",
        "whitespace",
        "clang-format",
        "deprecated attribute",
        "incorrect comments",
        "port commits",
    )
    if any(k in title for k in low):
        return "low_priority"
    hot = (
        "abi",
        "crash",
        "miscompile",
        "vectoriz",
        "barrier",
        "isel",
        "codegen",
        "register",
        "legaliz",
        "wasm",
        "amdgpu",
        "nvptx",
    )
    if n_related >= 8 or score_f >= 5.5 or any(k in title for k in hot):
        return "needs_inspection"
    if "backend" in stages or "gpu" in domains or "middle-end" in stages:
        return "potentially_important"
    if n_related >= 3:
        return "potentially_important"
    return "low_priority"


WATCHLIST_LABELS = {
    "needs_inspection": "Needs technical inspection",
    "potentially_important": "Potentially important",
    "low_priority": "Low-priority / maintenance",
}


def engineering_lessons(groups: list[dict[str, Any]], *, limit: int = 4) -> list[dict[str, str]]:
    """Short lessons grounded in what_changed — no invented benchmarks."""
    lessons: list[dict[str, str]] = []
    for g in groups:
        g = sanitize_group_for_display(g)
        what = re.sub(r"\s+", " ", (g.get("what_changed") or "").strip())
        if not what or len(what) < 40:
            continue
        headline = editorial_headline(g)
        stage = ((g.get("stages") or ["compiler"])[0]).replace(
            "Runtime & Toolchain", "Runtime"
        )
        # Lesson = mechanism sentence + audience caution (evidence-bound).
        mechanism = _first_sentence(what, limit=180)
        lesson = (
            f"{mechanism} "
            f"For {stage.lower()} work, treat the linked commit as the authority — "
            "do not generalize beyond what the diff establishes."
        )
        lessons.append(
            {
                "headline": headline,
                "lesson": lesson,
                "anchor": _anchor(g),
            }
        )
        if len(lessons) >= limit:
            break
    return lessons


def note_is_unknown(text: str | None) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    return bool(_NOT_ESTABLISHED.search(t))


def primary_commit(g: dict[str, Any] | None) -> dict[str, Any]:
    """Primary commit meta for hyperlinks: sha, short, url, paths, file_count."""
    g = g or {}
    stories = g.get("stories") or []
    primary = stories[0] if stories else {}
    sha = str(primary.get("related_ref") or "")
    paths = list(primary.get("paths") or [])
    notes = g.get("deep_dive_notes") or {}
    # Prefer size from notes ("(+24/−1)") when story lacks additions fields.
    size = ""
    impl = notes.get("implementation") or g.get("technical_context") or ""
    # Formats seen: (+24/−1) with ASCII slash + Unicode minus, or (+24/-1).
    m = re.search(r"\((\+\d+\s*/\s*[\u2212\-]?\s*\d+)\)", impl)
    if m:
        size = re.sub(r"\s+", "", m.group(1)).replace("\u2212", "−")
    elif primary.get("additions") is not None:
        size = f"+{primary.get('additions')}/−{primary.get('deletions') or 0}"
    return {
        "sha": sha,
        "short": sha[:8] if sha else "",
        "url": primary.get("source_url") or "#",
        "paths": paths,
        "file_count": len(paths),
        "size": size,
        "symbols": _symbols_from_notes(notes.get("implementation") or ""),
    }


def _symbols_from_notes(impl: str) -> list[str]:
    m = re.search(r"Diff-referenced symbols include:\s*([^.]+)", impl or "")
    if not m:
        return []
    return [s.strip() for s in m.group(1).split(",") if s.strip()][:6]


def _surface_summary(paths: list[str]) -> str:
    """Human surface label from paths — not a filename dump."""
    if not paths:
        return "the inspected source tree"
    joined = " ".join(paths).lower()
    if "lldb/test" in joined:
        n = len(paths)
        return f"{n} LLDB API test modules"
    if all("/test/" in p or p.endswith((".ll", ".mlir", ".c", ".cpp", ".py")) for p in paths[:8]):
        return f"{len(paths)} test files"
    roots: list[str] = []
    for p in paths:
        root = p.split("/")[0] if "/" in p else p
        if root and root not in roots:
            roots.append(root)
    if len(roots) == 1:
        return f"{len(paths)} files under {roots[0]}/"
    return f"{len(paths)} files across {', '.join(roots[:3])}"


def implementation_explanation(g: dict[str, Any] | None) -> str:
    """Prose explanation of the change — never a raw file/symbol dump."""
    g = g or {}
    notes = g.get("deep_dive_notes") or {}
    what = re.sub(r"\s+", " ", (g.get("what_changed") or "").strip())
    problem = re.sub(r"\s+", " ", (notes.get("problem") or "").strip())
    raw_impl = notes.get("implementation") or g.get("technical_context") or ""
    # Reject machine dumps that start with "Primary `sha`" / "Files:"
    if re.match(r"(?i)^primary\s+`", raw_impl.strip()) or "Files:" in raw_impl[:80]:
        raw_impl = ""
    base = what or problem or raw_impl
    if not base:
        return "See the primary commit for the implementation details."
    # Prefer 1–2 sentences of engineering prose.
    sentences = re.findall(r"[^.!?]+[.!?]?", base)
    prose = " ".join(s.strip() for s in sentences[:2] if s.strip())
    prose = re.sub(r"\s+", " ", prose).strip()
    if not prose.endswith((".", "!", "?")):
        prose += "."
    meta = primary_commit(g)
    surface = _surface_summary(meta["paths"])
    size_bit = f" ({meta['size']})" if meta.get("size") else ""
    return (
        f"{prose} The change touches {surface}{size_bit}. "
        "Open the primary commit for the exact hunks — this section explains the mechanism, "
        "not the file list."
    )


def validation_explanation(g: dict[str, Any] | None) -> str:
    """Compact validation note without dumping every test path."""
    g = g or {}
    notes = g.get("deep_dive_notes") or {}
    validation = (notes.get("validation") or notes.get("example") or "").strip()
    meta = primary_commit(g)
    test_paths = [p for p in meta["paths"] if "/test/" in p.lower() or p.endswith(".py")]
    if test_paths or (validation and "test" in validation.lower()):
        surface = _surface_summary(test_paths or meta["paths"])
        return (
            f"Validation is carried by {surface}. "
            "Run the project’s usual LLDB API / lit invocation for the paths in the "
            "primary commit — that is the reproduce entry point."
        )
    if validation and not note_is_unknown(validation) and "Files:" not in validation:
        # Drop embedded path lists
        if validation.lower().startswith("tests touched:"):
            return (
                f"The commit updates {_surface_summary(meta['paths'])}. "
                "Use those tests as the reproduce entry point via the primary commit."
            )
        return _first_sentence(validation, limit=280)
    return ""


def deep_dive_sections(g: dict[str, Any] | None) -> list[tuple[str, str, str]]:
    """Ordered engineering sections: (id, title, body). Skip empty unknowns.

    Implementation/validation bodies are prose explanations. HTML rendering
    adds the commit hyperlink separately via primary_commit().
    """
    g = g or {}
    notes = g.get("deep_dive_notes") or {}
    what = (g.get("what_changed") or "").strip()
    why = engineering_takeaway(g)
    who = ", ".join(g.get("who_should_care") or []) or "Compiler engineers"
    limits = (notes.get("limits") or g.get("uncertainty_note") or "").strip()
    prev = (notes.get("previous_behavior") or "").strip()
    problem = (notes.get("problem") or what).strip()
    # Problem should be prose, not identical file dump
    problem = re.sub(r"\s+", " ", problem)
    impl = implementation_explanation(g)
    validation = validation_explanation(g)
    reproduce = (notes.get("reproduce") or "").strip()
    if not reproduce and validation:
        meta = primary_commit(g)
        reproduce = (
            f"Inspect primary commit {meta['short'] or 'link'} and run the touched "
            f"{_surface_summary(meta['paths'])} with the project’s standard test runner."
        )

    sections: list[tuple[str, str, str]] = [
        ("problem", "01. Problem", problem),
        ("previous", "02. Previous behavior", prev if not note_is_unknown(prev) else ""),
        ("implementation", "03. Implementation", impl),
        (
            "before-after",
            "04. Before vs after",
            notes.get("before_after")
            or (
                ""
                if note_is_unknown(notes.get("example"))
                else (notes.get("example") or "")
            ),
        ),
        ("reproduce", "05. How to reproduce", reproduce),
        ("validation", "06. Validation", validation),
        (
            "implications",
            "07. Engineering implications",
            f"{why} Who should care: {who}.",
        ),
        (
            "evidence",
            "08. Evidence and limitations",
            limits
            or "Claims are limited to inspected commit evidence; unresolved questions stay unmarked.",
        ),
    ]
    return [(i, t, b.strip()) for i, t, b in sections if b and b.strip()]


def score_caption(score: float | None) -> str:
    if not isinstance(score, (int, float)):
        return ""
    return f"Editor's pick · {score:.1f}/10"


def editorial_score_legend() -> str:
    return (
        "Editorial ranking (not an objective importance score): "
        "technical significance 30% · engineering impact 25% · novelty 20% · "
        "breadth 15% · evidence quality 10%. Separate from evidence confidence."
    )


def _first_sentence(text: str, *, limit: int = 220) -> str:
    """First sentence without mid-word cuts; soft-wrapped commit bodies are joined."""
    line = re.sub(r"\s+", " ", (text or "").strip())
    m = re.match(r"^(.{12," + str(limit) + r"}?[.!?])(\s|$)", line)
    if m:
        return m.group(1).strip()
    clipped = _clip_words(line, limit).rstrip(".")
    return clipped + "."


def _anchor(g: dict[str, Any]) -> str:
    sid = g.get("story_id") or g.get("id") or "story"
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(sid))[:80]
