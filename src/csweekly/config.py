# SPDX-License-Identifier: Apache-2.0
"""Load ``sources/*.yaml`` definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    id: str
    name: str
    org: str
    category: str
    kind: str = "git"  # git | github | rss | arxiv
    enabled: bool = True
    # git
    url: str | None = None
    default_branch: str = "main"
    mirror_dirname: str | None = None
    path_prefixes: list[str] = Field(default_factory=list)
    path_labels: dict[str, str] = Field(default_factory=dict)
    ignore_author_regexes: list[str] = Field(default_factory=list)
    max_commits: int = 500
    # optional API / feeds
    github_repo: str | None = None
    feed_url: str | None = None
    notes: str | None = None


def sources_dir(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    candidate = base / "sources"
    if candidate.is_dir():
        return candidate
    # editable install from repo root
    return Path(__file__).resolve().parents[2] / "sources"


def load_sources(directory: Path | None = None) -> list[SourceConfig]:
    d = directory or sources_dir()
    configs: list[SourceConfig] = []
    for path in sorted(d.glob("*.yaml")):
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        configs.append(SourceConfig.model_validate(raw))
    return configs
