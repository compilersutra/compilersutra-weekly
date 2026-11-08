# SPDX-License-Identifier: Apache-2.0
"""Shared schemas. Facts vs editorial interpretation stay distinct."""

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
    """Legacy ranking used by collectors/tests."""

    HIGHLIGHT = "highlight"
    NOTABLE = "notable"
    OTHER = "other"


class SignalLevel(str, Enum):
    """Editorial signal for the published newsletter."""

    HIGH_SIGNAL = "high_signal"
    WORTH_KNOWING = "worth_knowing"
    DEEP_DIVE = "deep_dive"
    SKIP = "skip"


class ChangeType(str, Enum):
    OPTIMIZATION = "Optimization"
    NEW_CAPABILITY = "New capability"
    BUG_FIX = "Bug fix"
    BACKEND = "Backend"
    FRONTEND = "Frontend"
    IR = "IR"
    CODEGEN = "Code generation"
    RUNTIME = "Runtime"
    TOOLING = "Tooling"
    INFRASTRUCTURE = "Infrastructure"
    PERFORMANCE = "Performance"
    RESEARCH = "Research"
    OTHER = "Other"


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
    # Editorial intelligence layer
    story_id: str | None = None
    what_changed: str | None = None
    technical_context: str | None = None
    why_it_matters: str | None = None
    who_should_care: list[str] = Field(default_factory=list)
    uncertainty_note: str | None = None
    change_type: str | None = None
    signal: SignalLevel = SignalLevel.SKIP
    stages: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    technical_areas: list[str] = Field(default_factory=list)
    hardware_targets: list[str] = Field(default_factory=list)
    impact_uncertain: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)
    analysis_generated: bool = False


class ChangeGroup(BaseModel):
    """Grouped commits forming one editorial story (canonical unit)."""

    id: str
    title: str
    category: str
    project: str
    areas: list[str] = Field(default_factory=list)
    importance: Importance = Importance.OTHER
    stories: list[Story] = Field(default_factory=list)
    story_id: str | None = None
    what_changed: str | None = None
    technical_context: str | None = None
    why_it_matters: str | None = None
    who_should_care: list[str] = Field(default_factory=list)
    uncertainty_note: str | None = None
    change_type: str | None = None
    signal: SignalLevel = SignalLevel.SKIP
    stages: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    technical_areas: list[str] = Field(default_factory=list)
    hardware_targets: list[str] = Field(default_factory=list)
    impact_uncertain: bool = False
    deep_dive_notes: dict[str, str] = Field(default_factory=dict)


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
    week_overview: list[str] = Field(default_factory=list)
    high_signal: list[ChangeGroup] = Field(default_factory=list)
    worth_knowing: list[ChangeGroup] = Field(default_factory=list)
    deep_dive: ChangeGroup | None = None
    moving_stories: dict[str, list[str]] = Field(default_factory=dict)
