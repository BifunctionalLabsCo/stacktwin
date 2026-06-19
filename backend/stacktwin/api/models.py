from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal["hackernews", "arxiv", "devto", "github_trending", "youtube"]
ModuleStatus = Literal["ready", "queued", "completed", "locked", "failed"]
Difficulty = Literal["Focused", "Intermediate", "Advanced"]


class SourceReferenceResponse(BaseModel):
    title: str
    source: SourceType
    url: str


class LearningModuleResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    status: ModuleStatus
    difficulty: Difficulty
    estimated_minutes: int = Field(alias="estimatedMinutes")
    personalization_reason: str = Field(alias="personalizationReason")
    source_hints: list[SourceReferenceResponse] = Field(alias="sourceHints")


class WeeklyTrackResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    week_label: str = Field(alias="weekLabel")
    generated_at: str = Field(alias="generatedAt")
    learner_focus: str = Field(alias="learnerFocus")
    weekly_time_budget_minutes: int = Field(alias="weeklyTimeBudgetMinutes")
    modules: list[LearningModuleResponse]
