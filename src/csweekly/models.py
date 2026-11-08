# SPDX-License-Identifier: Apache-2.0
"""Shared schemas. Factual fields vs analysis fields stay distinct."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceKind(str, Enum):
    """How the finding was observed."""

    GIT_COMMIT = "git_commit"
    GIT_TAG = "git_tag"
    GITHUB_RELEASE = "github_release"
    RSS = "rss"
    ARXIV = "arxiv"
    MANUAL = "manual"


class Story(BaseModel):
    """One source-backed finding for the weekly window."""

    id: str = Field(description="Stable id for dedupe, e.g. git:llvm:<sha>")
    title: str
    source_url: str
    source_org: str
    category: str
    published_at: datetime | None = None
    discovered_at: datetime
    evidence_kind: EvidenceKind
    summary: str = Field(description="Factual summary from the source only")
    engineering_significance: str | None = Field(
        default=None,
        description="Optional analysis; must not invent source facts",
    )
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    related_ref: str | None = Field(
        default=None, description="commit sha, PR number, paper id, …"
    )
    paths: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    analysis_generated: bool = Field(
        default=False,
        description="True only when engineering_significance was machine-written",
    )


class Window(BaseModel):
    """Friday→Friday reporting window (end exclusive)."""

    start: datetime
    end: datetime
    timezone: str = "UTC"

    @property
    def label(self) -> str:
        return f"{self.start.date().isoformat()} → {self.end.date().isoformat()}"


class CollectResult(BaseModel):
    source_id: str
    window: Window
    stories: list[Story]
    meta: dict[str, Any] = Field(default_factory=dict)


class WeeklyIssue(BaseModel):
    title: str
    published_on: date
    window: Window
    stories: list[Story]
    sections: dict[str, list[Story]] = Field(default_factory=dict)
    hotspots: dict[str, list[tuple[str, int]]] = Field(default_factory=dict)
