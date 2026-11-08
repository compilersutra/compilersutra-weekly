# SPDX-License-Identifier: Apache-2.0
"""Shared schemas. Factual fields vs analysis fields stay distinct."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceKind(str, Enum):
    GIT_COMMIT = "git_commit"
    GIT_TAG = "git_tag"
    GITHUB_RELEASE = "github_release"
    RSS = "rss"
    ARXIV = "arxiv"
    WEB_ANNOUNCEMENT = "web_announcement"
    MANUAL = "manual"


class Importance(str, Enum):
    HIGHLIGHT = "highlight"
    NOTABLE = "notable"
    OTHER = "other"


class Story(BaseModel):
    """One source-backed finding for the weekly window."""

    id: str
    title: str
    source_url: str
    source_org: str
    category: str  # llvm | gcc | mlir | ai | gpu | other | research
    project: str = ""
    published_at: datetime | None = None
    discovered_at: datetime
    evidence_kind: EvidenceKind
    summary: str
    engineering_significance: str | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    related_ref: str | None = None
    paths: list[str] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)
    importance: Importance = Importance.OTHER
    group_id: str | None = None
    group_title: str | None = None
    author: str | None = None
    committer: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    analysis_generated: bool = False


class ChangeGroup(BaseModel):
    id: str
    title: str
    category: str
    project: str
    areas: list[str] = Field(default_factory=list)
    importance: Importance = Importance.OTHER
    stories: list[Story] = Field(default_factory=list)


class Window(BaseModel):
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
    errors: list[str] = Field(default_factory=list)


class WeeklyIssue(BaseModel):
    title: str
    published_on: date
    window: Window
    stories: list[Story]
    groups: list[ChangeGroup] = Field(default_factory=list)
    sections: dict[str, list[Story]] = Field(default_factory=dict)
    hotspots: dict[str, list[tuple[str, int]]] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)
