# SPDX-License-Identifier: Apache-2.0
"""Editorial selection — high-signal newsletter, not a commit dump."""

from __future__ import annotations

import re
from collections import defaultdict

from csweekly.models import ChangeGroup, EvidenceKind, SignalLevel, Story

_CAPS = {
    SignalLevel.HIGH_SIGNAL: 8,
    SignalLevel.WORTH_KNOWING: 12,
    SignalLevel.DEEP_DIVE: 1,
}

_NOISE = re.compile(
    r"(?i)\b(revert\b|\bnfc\b|typo\b|whitespace\b|clang-format\b|"
    r"update\s+(tests?|docs?)\s+only|fix target selector)\b"
)
_PR = re.compile(r"\s*\(#\d+\)\s*$")
_BRACKET = re.compile(r"^\[([^\]]+)\]\s*")


def newsletter_bucket(story: Story) -> str:
    paths = story.paths
    title = story.title.lower()
    if story.category == "llvm":
        if any(p.startswith(("clang/", "clang-tools-extra/")) for p in paths) or "[clang]" in title:
            return "clang"
        if any(
            p.startswith(pref)
            for pref in (
                "lldb/",
                "lld/",
                "libc/",
                "libcxx/",
                "libcxxabi/",
                "compiler-rt/",
                "flang/",
                "flang-rt/",
                "bolt/",
            )
            for p in paths
        ):
            return "other-llvm"
        return "llvm"
    return story.category


def is_noise(story: Story) -> bool:
    text = f"{story.title}\n{story.summary}"
    if re.search(r"(?i)\brevert\b", text):
        return True
    if _NOISE.search(text):
        return True
    areas = set(story.areas or [])
    if areas and areas <= {"Documentation", "Testing", "Build infrastructure", "Other"}:
        if story.signal == SignalLevel.SKIP:
            return True
    return False


def select_for_newsletter(groups: list[ChangeGroup]) -> list[ChangeGroup]:
    """Return curated groups for the issue body (already explained)."""
    usable = []
    for g in groups:
        if all(is_noise(s) for s in g.stories):
            continue
        if re.search(r"(?i)\brevert\b", g.stories[0].title):
            continue
        if g.signal == SignalLevel.SKIP and len(g.stories) < 2:
            continue
        usable.append(g)

    by_signal: dict[SignalLevel, list[ChangeGroup]] = defaultdict(list)
    for g in usable:
        by_signal[g.signal].append(g)

    def rank_key(g: ChangeGroup) -> tuple:
        return (
            -len(g.stories),
            0 if not g.impact_uncertain else 1,
            g.title.lower(),
        )

    selected: list[ChangeGroup] = []
    # Prefer deep dive pick from high signal first
    deep_candidates = sorted(
        by_signal.get(SignalLevel.HIGH_SIGNAL, [])
        + by_signal.get(SignalLevel.WORTH_KNOWING, []),
        key=lambda g: (-len(g.stories), 0 if not g.impact_uncertain else 1, g.title.lower()),
    )
    if deep_candidates:
        dive = deep_candidates[0]
        dive.signal = SignalLevel.DEEP_DIVE
        selected.append(dive)

    for level in (SignalLevel.HIGH_SIGNAL, SignalLevel.WORTH_KNOWING):
        items = sorted(by_signal.get(level, []), key=rank_key)
        cap = _CAPS[level]
        for g in items:
            if g in selected or g.signal == SignalLevel.DEEP_DIVE:
                continue
            selected.append(g)
            if sum(1 for x in selected if x.signal == level) >= cap:
                break

    # Ensure sparse ecosystems still appear a little
    by_cat: dict[str, list[ChangeGroup]] = defaultdict(list)
    for g in usable:
        by_cat[g.category].append(g)
    for cat in ("ai", "gpu", "mlir", "gcc"):
        if any(g.category == cat for g in selected):
            continue
        extras = sorted(by_cat.get(cat, []), key=rank_key)
        for g in extras[:2]:
            if g not in selected:
                if g.signal == SignalLevel.SKIP:
                    g.signal = SignalLevel.WORTH_KNOWING
                selected.append(g)
    return selected


def split_non_git(stories: list[Story]) -> dict[str, list[Story]]:
    out: dict[str, list[Story]] = {"releases": [], "research": [], "community": []}
    for s in stories:
        kind = s.evidence_kind
        if kind == EvidenceKind.GITHUB_RELEASE:
            out["releases"].append(s)
        elif kind == EvidenceKind.ARXIV:
            out["research"].append(s)
        elif kind in {EvidenceKind.RSS, EvidenceKind.WEB_ANNOUNCEMENT, EvidenceKind.MANUAL}:
            if s.category == "research":
                out["research"].append(s)
            else:
                out["community"].append(s)
    return out


def clean_subject(text: str) -> str:
    text = (text or "").strip()
    for _ in range(4):
        m = re.match(r"^([^:]{2,70}):\s+(.+)$", text)
        if not m:
            break
        left, right = m.group(1).strip(), m.group(2).strip()
        looks_like_person = (" " in left) or ("(" in left) or (
            left.replace("-", "").replace("_", "").isalnum() and len(left) <= 40
        )
        looks_like_subject = bool(
            _BRACKET.match(right)
            or re.match(
                r"(?i)^(add|fix|implement|remove|introduce|enable|teach|initial|"
                r"support|allow|refactor|improve|optimize|port|extract|check|"
                r"fold|combine|compute|make|do not|pick|attach|split|drop|"
                r"disallow|skip|clear|use |llvm|clang|gcc|mlir|amdgpu|i386|"
                r"aarch64|riscv|gccrs|libc|flang|revert)",
                right,
            )
        )
        if looks_like_person and looks_like_subject:
            text = right
            continue
        break
    while True:
        m = _BRACKET.match(text)
        if not m:
            break
        text = text[m.end() :].strip()
    text = re.sub(
        r"^(gccrs|i386|aarch64|amdgcn|riscv|risc-v|mlir|nvvm|tosa|vector|math|"
        r"match\.pd|libc\+\+|libc|lldb|flang-rt|flang|bolt|cir|abi)\s*:\s*",
        "",
        text,
        flags=re.I,
    ).strip()
    text = _PR.sub("", text).strip()
    text = re.sub(r"\s*\(NFC\)\s*$", "", text, flags=re.I).strip()
    text = re.sub(r"\s*\[PR\d+\]\s*$", "", text).strip()
    return text.strip(" .")


def editorial_sentence(group: ChangeGroup) -> str:
    primary = group.stories[0]
    subject = clean_subject(primary.summary or primary.title) or clean_subject(primary.title)
    component = _component_hint(primary)
    n = len(group.stories)
    prose = _subject_to_prose(subject, component)
    if n > 1:
        prose = f"{prose} ({n} related commits)"
    return prose


def editorial_blurb(story: Story) -> str:
    return editorial_sentence(
        ChangeGroup(
            id=story.id,
            title=story.title,
            category=story.category,
            project=story.project or story.category,
            stories=[story],
        )
    )


def week_overview_bullets(groups: list[ChangeGroup]) -> list[str]:
    """Derive 3–5 big-picture bullets from selected groups only."""
    themes: dict[str, int] = defaultdict(int)
    for g in groups:
        for d in g.domains or [g.category]:
            themes[d] += 1
        for t in g.technical_areas[:2]:
            themes[t] += 1
        for h in g.hardware_targets[:1]:
            themes[h] += 1
    if not themes:
        return ["Quiet week in the tracked sources — no high-signal themes stood out."]
    top = sorted(themes.items(), key=lambda x: -x[1])[:5]
    bullets = []
    for name, count in top:
        if name in {"CPU", "GPU", "AI / ML", "Languages", "Research"}:
            bullets.append(f"{name} work appears across {count} curated developments this week.")
        elif name in {"Optimization", "Vectorization", "Code generation", "IR"}:
            bullets.append(f"{name} remains active in this week's curated set ({count} items).")
        else:
            bullets.append(f"{name} shows up in {count} curated changes.")
    return bullets[:5]


def moving_story_lines(groups: list[ChangeGroup]) -> dict[str, list[str]]:
    """Continuity themes for this week (story_id based)."""
    by_track: dict[str, list[str]] = defaultdict(list)
    for g in groups:
        track = g.category if g.category != "llvm" else newsletter_bucket(g.stories[0])
        label = {
            "llvm": "LLVM",
            "clang": "Clang",
            "gcc": "GCC",
            "mlir": "MLIR",
            "ai": "AI Compilers",
            "gpu": "GPU",
            "other": "Other",
            "other-llvm": "LLVM tooling/runtime",
        }.get(track, track)
        hw = f" ({', '.join(g.hardware_targets[:2])})" if g.hardware_targets else ""
        line = f"{g.title[:90]}{hw}"
        if line not in by_track[label]:
            by_track[label].append(line)
    return {k: v[:4] for k, v in by_track.items() if v}


def _component_hint(story: Story) -> str:
    m = _BRACKET.match(story.title.strip())
    if m:
        return m.group(1).strip()
    for pref, name in (
        ("llvm/lib/Target/AMDGPU/", "AMDGPU"),
        ("llvm/lib/CodeGen/GlobalISel/", "GlobalISel"),
        ("clang/", "Clang"),
        ("mlir/", "MLIR"),
        ("gcc/", "GCC"),
    ):
        if any(p.startswith(pref) for p in story.paths):
            return name
    return story.project or story.category


def _subject_to_prose(subject: str, component: str) -> str:
    s = subject.strip()
    patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"(?i)^add(?:ed)? support for\s+(.+)$"), r"Support for \1 was added"),
        (re.compile(r"(?i)^add(?:ed)?\s+(.+)$"), r"\1 was added"),
        (re.compile(r"(?i)^implement(?:ed|s|ation of)?\s+(.+)$"), r"\1 was implemented"),
        (re.compile(r"(?i)^introduce(?:d|s)?\s+(.+)$"), r"\1 was introduced"),
        (re.compile(r"(?i)^enable(?:d|s)?\s+(.+)$"), r"\1 was enabled"),
        (re.compile(r"(?i)^fix(?:es|ed)?\s+(.+)$"), r"\1 was fixed"),
        (re.compile(r"(?i)^remove(?:d|s)?\s+(.+)$"), r"\1 was removed"),
        (re.compile(r"(?i)^improve(?:d|s)?\s+(.+)$"), r"\1 was improved"),
        (re.compile(r"(?i)^optimize(?:d|s)?\s+(.+)$"), r"\1 was optimized"),
        (re.compile(r"(?i)^initial(?:ize|ise)?\s+(.+)$"), r"Initial work landed for \1"),
        (re.compile(r"(?i)^support\s+(.+)$"), r"Support for \1 landed"),
        (re.compile(r"(?i)^teach\s+(.+?)\s+to\s+(.+)$"), r"\1 learned to \2"),
    ]
    for pat, repl in patterns:
        if pat.match(s):
            out = pat.sub(repl, s)
            out = _maybe_prefix_component(out, component)
            return _ensure_period(out)
    return _ensure_period(_maybe_prefix_component(s, component))


def _maybe_prefix_component(text: str, component: str) -> str:
    if not text or not component:
        return text
    if component.lower() in {"llvm", "clang", "gcc", "mlir", "ai", "gpu", "other"}:
        return text
    if component.lower() in text.lower()[: len(component) + 12]:
        return text
    return f"{component}: {text[0].lower() + text[1:]}"


def _ensure_period(text: str) -> str:
    text = text.strip().rstrip(".")
    if not text:
        return text
    return text[0].upper() + text[1:] + "."
