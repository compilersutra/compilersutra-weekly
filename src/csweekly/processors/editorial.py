# SPDX-License-Identifier: Apache-2.0
"""Editorial selection + prose — newsletter quality, not a commit dump."""

from __future__ import annotations

import re

from csweekly.models import ChangeGroup, EvidenceKind, Importance, Story

# Hard caps — LLVM Weekly ships ~8–15 bullets per section, not dozens.
_CAPS: dict[str, int] = {
    "llvm": 14,
    "clang": 8,
    "gcc": 10,
    "mlir": 8,
    "ai": 8,
    "gpu": 8,
    "other": 8,
    "research": 8,
    "release": 8,
    "community": 10,
}

_NOISE = re.compile(
    r"(?i)\b("
    r"revert\b|\(nfc\)|\bnfc\b|typo\b|whitespace\b|clang-format\b|git-clang-format\b|"
    r"update\s+(tests?|docs?|documentation)\s+only|"
    r"fix target selector|testsuite:\s*fix"
    r")\b"
)

_PR = re.compile(r"\s*\(#\d+\)\s*$")
_BRACKET = re.compile(r"^\[([^\]]+)\]\s*")
# "Name: subject" or "name: [Tag] subject" — not "foo: bar" path-like keys
_AUTHOR_PREFIX = re.compile(
    r"^(?:"
    r"[A-Za-z][\w .'\-]{0,48}|"
    r"[\w .'\-]{1,48}"
    r"):\s+(?=\[|[A-Z]|Implement|Add|Fix|Remove|Introduce|Enable|Teach)"
)


def newsletter_bucket(story: Story) -> str:
    """Split LLVM monorepo noise into readable newsletter buckets."""
    paths = " ".join(story.paths).lower()
    title = story.title.lower()
    if story.category == "llvm":
        if any(p.startswith("clang/") or p.startswith("clang-tools-extra/") for p in story.paths) or "[clang]" in title:
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
                "polly/",
            )
            for p in story.paths
        ):
            return "other-llvm"
        return "llvm"
    return story.category


def is_noise(story: Story) -> bool:
    text = f"{story.title}\n{story.summary}"
    # Reverts are almost never newsletter-worthy on their own
    if re.search(r"(?i)\brevert\b", text):
        return True
    if _NOISE.search(text):
        return True
    areas = set(story.areas or [])
    if areas and areas <= {"Documentation", "Testing", "Build infrastructure", "Other"}:
        if story.importance == Importance.OTHER:
            return True
    return False


def select_for_newsletter(groups: list[ChangeGroup]) -> list[ChangeGroup]:
    """Strict curation: highlights/notables only; drop noise; small caps."""
    by_bucket: dict[str, list[ChangeGroup]] = {}
    for g in groups:
        # Drop pure noise groups unless they are true highlights with substance
        # Never publish pure noise/revert groups, even if scored as highlight
        if all(is_noise(s) for s in g.stories):
            continue
        if re.search(r"(?i)\brevert\b", g.stories[0].title):
            continue
        bucket = newsletter_bucket(g.stories[0])
        if bucket == "clang":
            key = "clang"
        elif bucket == "other-llvm":
            key = "other"
        else:
            key = g.category
        # Drop tiny OTHER noise in busy LLVM/GCC tracks; keep for sparse AI/GPU/other
        if (
            g.importance == Importance.OTHER
            and len(g.stories) < 2
            and key in {"llvm", "clang", "gcc"}
        ):
            continue
        by_bucket.setdefault(key, []).append(g)

    selected: list[ChangeGroup] = []
    for cat, items in by_bucket.items():
        cap = _CAPS.get(cat, 8)
        ranked = sorted(
            items,
            key=lambda g: (
                {Importance.HIGHLIGHT: 0, Importance.NOTABLE: 1, Importance.OTHER: 2}[
                    g.importance
                ],
                -len(g.stories),
                -_signal_score(g),
                g.title.lower(),
            ),
        )
        keep: list[ChangeGroup] = []
        for g in ranked:
            if g.importance == Importance.OTHER and len(keep) >= max(3, cap // 3):
                continue
            keep.append(g)
            if len(keep) >= cap:
                break
        # Sparse trackers (AI/GPU/other): still show a few signals if nothing ranked higher
        if not keep and ranked:
            keep = ranked[: min(3, cap)]
        selected.extend(keep)
    return selected


def _signal_score(group: ChangeGroup) -> int:
    text = " ".join(s.title for s in group.stories).lower()
    score = 0
    for token in (
        "implement",
        "introduce",
        "add support",
        "new backend",
        "globalisel",
        "vector",
        "rfc",
        "abi",
        "security",
        "performance",
        "land",
        "remove",
    ):
        if token in text:
            score += 2
    score += min(len(group.stories), 5)
    return score


def split_non_git(stories: list[Story]) -> dict[str, list[Story]]:
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


def clean_subject(text: str) -> str:
    text = (text or "").strip()
    # Drop "Author Name: subject" / "username: subject" prefixes
    for _ in range(4):
        m = re.match(r"^([^:]{2,70}):\s+(.+)$", text)
        if not m:
            break
        left, right = m.group(1).strip(), m.group(2).strip()
        looks_like_person = (" " in left) or ("(" in left) or (
            left.replace("-", "").replace("_", "").isalnum()
            and len(left) <= 40
            and not left.lower()
            in {
                "llvm",
                "clang",
                "gcc",
                "mlir",
                "amdgpu",
                "riscv",
                "i386",
                "aarch64",
                "gccrs",
                "amdgcn",
            }
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
    # peel repeated [tags]
    while True:
        m = _BRACKET.match(text)
        if not m:
            break
        text = text[m.end() :].strip()
    # Drop leading component/ tags like "gccrs:" / "i386:" once for prose
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
    text = text.strip(" .")
    return text


def editorial_sentence(group: ChangeGroup) -> str:
    """Rewrite a commit/group into one LLVM Weekly–style sentence.

    Grounded only in the subject/paths — no invented performance claims.
    """
    primary = group.stories[0]
    subject = clean_subject(primary.summary or primary.title)
    if not subject:
        subject = clean_subject(primary.title)

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
            areas=story.areas,
            importance=story.importance,
            stories=[story],
        )
    )


def _component_hint(story: Story) -> str:
    m = _BRACKET.match(story.title.strip())
    if m:
        return m.group(1).strip()
    for pref, name in (
        ("llvm/lib/Target/AMDGPU/", "AMDGPU"),
        ("llvm/lib/CodeGen/GlobalISel/", "GlobalISel"),
        ("llvm/lib/Transforms/", "LLVM Transforms"),
        ("clang/", "Clang"),
        ("mlir/", "MLIR"),
        ("gcc/", "GCC"),
    ):
        if any(p.startswith(pref) for p in story.paths):
            return name
    return story.project or story.category


def _subject_to_prose(subject: str, component: str) -> str:
    s = subject.strip()
    low = s.lower()

    # Already sentence-like
    if low.startswith(("this ", "the ", "a ", "an ")) and s[:1].isupper():
        return _ensure_period(s)

    patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"(?i)^add(?:ed)? support for\s+(.+)$"), r"Support for \1 was added"),
        (re.compile(r"(?i)^add(?:ed)?\s+(.+)$"), r"\1 was added"),
        (re.compile(r"(?i)^implement(?:ed|s|ation of)?\s+(.+)$"), r"\1 was implemented"),
        (re.compile(r"(?i)^introduce(?:d|s)?\s+(.+)$"), r"\1 was introduced"),
        (re.compile(r"(?i)^enable(?:d|s)?\s+(.+)$"), r"\1 was enabled"),
        (re.compile(r"(?i)^fix(?:es|ed)?\s+(.+)$"), r"\1 was fixed"),
        (re.compile(r"(?i)^remove(?:d|s)?\s+(.+)$"), r"\1 was removed"),
        (re.compile(r"(?i)^rename(?:d|s)?\s+(.+)$"), r"\1 was renamed"),
        (re.compile(r"(?i)^improve(?:d|s)?\s+(.+)$"), r"\1 was improved"),
        (re.compile(r"(?i)^optimize(?:d|s)?\s+(.+)$"), r"\1 was optimized"),
        (re.compile(r"(?i)^refactor(?:ed|s)?\s+(.+)$"), r"\1 was refactored"),
        (re.compile(r"(?i)^extend(?:ed|s)?\s+(.+)$"), r"\1 was extended"),
        (re.compile(r"(?i)^initial(?:ize|ise)?\s+(.+)$"), r"Initial work landed for \1"),
        (re.compile(r"(?i)^support\s+(.+)$"), r"Support for \1 landed"),
        (re.compile(r"(?i)^allow\s+(.+)$"), r"\1 is now allowed"),
        (re.compile(r"(?i)^teach\s+(.+?)\s+to\s+(.+)$"), r"\1 learned to \2"),
        (re.compile(r"(?i)^(.+?)\s+learned to\s+(.+)$"), r"\1 learned to \2"),
    ]
    for pat, repl in patterns:
        m = pat.match(s)
        if m:
            out = pat.sub(repl, s)
            out = _trim_backticks_noise(out)
            out = _maybe_prefix_component(out, component)
            return _ensure_period(out)

    out = _maybe_prefix_component(s, component)
    return _ensure_period(out)


def _maybe_prefix_component(text: str, component: str) -> str:
    if not text:
        return text
    # Avoid "LLVM: …" / "Clang: …" noise — those are already section headings.
    if not component or component.lower() in {"llvm", "clang", "gcc", "mlir", "ai", "gpu", "other"}:
        return text
    if component.lower() in text.lower()[: len(component) + 12]:
        return text
    return f"{component}: {text[0].lower() + text[1:]}" if text else text


def _trim_backticks_noise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _ensure_period(text: str) -> str:
    text = text.strip().rstrip(".")
    if not text:
        return text
    # Capitalize first letter
    text = text[0].upper() + text[1:]
    return text + "."
