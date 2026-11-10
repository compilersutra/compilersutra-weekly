# SPDX-License-Identifier: Apache-2.0
"""Extract structured evidence from git mirrors — source of truth for AI writing."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from csweekly.models import ChangeGroup
from csweekly.processors.diff_enrich import resolve_mirror


class CommitEvidence(BaseModel):
    sha: str
    subject: str = ""
    body: str = ""
    files: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    functions: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    diff_excerpt: str = ""
    source_url: str = ""
    repo: str = ""


class EvidencePack(BaseModel):
    """Facts the writer may use — nothing else is authoritative."""

    story_id: str
    title_hint: str
    project_hint: str = ""
    category: str = ""
    stages: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    hardware_targets: list[str] = Field(default_factory=list)
    related_shas: list[str] = Field(default_factory=list)
    primary: CommitEvidence | None = None
    related: list[CommitEvidence] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def to_prompt_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _run(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _parse_numstat(text: str) -> tuple[int, int]:
    add = dele = 0
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            add += int(parts[0])
            dele += int(parts[1])
    return add, dele


_NOISE_FUNCS = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "return",
        "sizeof",
        "like",
        "set",
        "get",
        "add",
        "and",
        "or",
        "not",
        "new",
        "int",
        "bool",
        "void",
        "true",
        "false",
    }
)


def _extract_functions(diff: str) -> list[str]:
    found: list[str] = []
    for line in diff.splitlines():
        if line.startswith("@@") and "@@" in line[2:]:
            tail = line.split("@@")[-1].strip()
            if tail:
                m = re.search(r"\b([A-Za-z_][\w:]{4,80})\s*\(", tail)
                if m and m.group(1) not in found and m.group(1) not in _NOISE_FUNCS:
                    found.append(m.group(1))
        elif line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            m = re.search(
                r"\b([A-Za-z_][\w:]{4,60})\s*\([^;]*\)\s*(?:const\s*)?\{?\s*$",
                line[1:],
            )
            if not m:
                continue
            name = m.group(1)
            if name in _NOISE_FUNCS or name in found:
                continue
            # Prefer CamelCase / snake_case symbols over tiny keywords
            if "_" in name or any(c.isupper() for c in name[1:]):
                found.append(name)
        if len(found) >= 12:
            break
    return found


def extract_commit(repo: Path, sha: str, *, source_url: str = "") -> CommitEvidence:
    subject = _run(repo, ["log", "-1", "--format=%s", sha]).strip()
    body = _run(repo, ["log", "-1", "--format=%b", sha]).strip()
    files = [
        f.strip()
        for f in _run(repo, ["show", "--name-only", "--format=", sha]).splitlines()
        if f.strip()
    ]
    numstat = _run(repo, ["show", "--numstat", "--format=", sha])
    additions, deletions = _parse_numstat(numstat)
    # Cap diff for prompts / storage
    diff = _run(repo, ["show", "--unified=3", "--format=", sha])
    if len(diff) > 24000:
        diff = diff[:24000] + "\n… [diff truncated] …\n"
    tests = [f for f in files if re.search(r"test|Test|lit|unittest", f)]
    return CommitEvidence(
        sha=sha,
        subject=subject,
        body=body,
        files=files[:40],
        additions=additions,
        deletions=deletions,
        functions=_extract_functions(diff),
        tests=tests[:20],
        diff_excerpt=diff,
        source_url=source_url,
        repo=str(repo),
    )


def build_evidence_pack(group: ChangeGroup, mirrors_dir: Path) -> EvidencePack:
    pack = EvidencePack(
        story_id=group.story_id or group.id,
        title_hint=group.title,
        project_hint=group.project or group.category,
        category=group.category,
        stages=list(group.stages),
        domains=list(group.domains),
        hardware_targets=list(group.hardware_targets),
        related_shas=[s.related_ref for s in group.stories if s.related_ref],
    )
    primary = group.stories[0] if group.stories else None
    if not primary or not primary.related_ref:
        pack.errors.append("no primary commit SHA")
        return pack

    paths: list[str] = []
    for s in group.stories:
        paths.extend(s.paths)
    repo = resolve_mirror(paths, mirrors_dir)
    if repo is None:
        pack.errors.append("mirror not found for paths")
        return pack

    pack.primary = extract_commit(
        repo, primary.related_ref, source_url=primary.source_url or ""
    )
    if not pack.primary.subject and not pack.primary.files:
        pack.errors.append(f"git show failed for {primary.related_ref[:12]}")

    for s in group.stories[1:4]:
        if not s.related_ref:
            continue
        pack.related.append(
            extract_commit(repo, s.related_ref, source_url=s.source_url or "")
        )
    return pack


def prose_from_body(body: str) -> list[str]:
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    out: list[str] = []
    for p in paragraphs:
        low = p.lower()
        if low.startswith(("gcc/changelog", "differential", "reviewed-by", "signed-off")):
            break
        if p.startswith("* ") and "changelog" in body.lower():
            break
        out.append(p)
    return out
