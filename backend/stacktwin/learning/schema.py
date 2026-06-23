from typing import Literal

from pydantic import BaseModel, Field

ModuleStatus = Literal["ready", "queued", "completed", "locked", "failed", "stale"]
Difficulty = Literal["Focused", "Intermediate", "Advanced"]


class SourceReference(BaseModel):
    title: str
    source: str
    url: str


class Exercise(BaseModel):
    title: str
    instructions: str


class Checkpoint(BaseModel):
    question: str
    options: list[str]
    answer: str
    explanation: str


class LearningModule(BaseModel):
    id: str
    title: str
    status: ModuleStatus = "ready"
    difficulty: Difficulty
    estimated_minutes: int = Field(ge=1)
    personalization_reason: str
    source_hints: list[SourceReference]
    context_brief: str
    objectives: list[str]
    key_concepts: list[str]
    exercise: Exercise
    checkpoint: Checkpoint
    takeaway: str
    available_actions: list[str] = Field(default_factory=list)


class WeeklyTrack(BaseModel):
    id: str
    week_start: str
    week_label: str
    generated_at: str
    learner_focus: str
    weekly_time_budget_minutes: int = Field(ge=1)
    modules: list[LearningModule]
