from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ExperienceLevel(str, Enum):
    junior = "junior"
    mid = "mid"
    senior = "senior"
    staff = "staff"


class ContentFormat(str, Enum):
    short_summary = "short_summary"
    hands_on = "hands_on"
    deep_dive = "deep_dive"
    quiz = "quiz"
    video = "video"
    podcast = "podcast"


class DeveloperProfile(BaseModel):
    # Identity
    name: Optional[str] = None
    current_role: Optional[str] = None
    experience_years: Optional[int] = None
    seniority: Optional[ExperienceLevel] = None

    # Stack
    current_stack: list[str] = Field(default_factory=list)
    learning: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    # Goals
    career_direction: Optional[str] = None
    learning_goals: list[str] = Field(default_factory=list)
    topics_to_track: list[str] = Field(default_factory=list)
    topics_to_avoid: list[str] = Field(default_factory=list)

    # Preferences
    weekly_time_budget_hours: float = 2.0
    preferred_formats: list[ContentFormat] = Field(default_factory=list)

    # Source
    profile_source: Optional[str] = None  # "cv", "linkedin", "manual"
    raw_text: Optional[str] = None        # original extracted text kept for re-processing


class ArticleScore(BaseModel):
    relevance: float = Field(ge=0, le=1)
    novelty: float = Field(ge=0, le=1)
    practicality: float = Field(ge=0, le=1)
    difficulty: float = Field(ge=0, le=1)
    urgency: float = Field(ge=0, le=1)
    stack_match: float = Field(ge=0, le=1)
    learning_value: float = Field(ge=0, le=1)
    time_cost_minutes: int
    overall: float = Field(ge=0, le=1)
    why_this_matters: str
    recommended_action: Optional[str] = None


class DigestItem(BaseModel):
    title: str
    url: str
    source: str
    summary: str
    score: ArticleScore
    estimated_reading_minutes: int
    tags: list[str] = Field(default_factory=list)


class WeeklyDigest(BaseModel):
    week_start: str
    profile_name: Optional[str] = None
    items: list[DigestItem]
    total_items_processed: int
    generated_at: str