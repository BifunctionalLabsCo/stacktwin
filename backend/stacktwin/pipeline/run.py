"""
Durable pipeline run records for the digest/track generation pipeline.

A `PipelineRun` is created at the start of every `/api/digest/run` invocation
and updated as the pipeline progresses through its stages. It gives a
user-isolated, storage-backed audit trail so that scheduled and manual runs
are observable without depending on console output.

Structured logging convention: every log line emitted during pipeline
execution is prefixed with `[pipeline] run_id=<run_id> stage=<stage>` so
that log lines for a single attempt can be correlated in local Uvicorn
output and in Nebius execution logs.
"""

from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
    "skipped_existing",
    "retryable",
]

RunStage = Literal[
    "queued",
    "loading_profile",
    "ingesting",
    "scoring",
    "generating",
    "persisting",
    "done",
]

TriggerType = Literal["manual", "scheduled"]

# Bound on stored failure summaries so we never persist a full stack trace
# or raw exception payload that could leak secrets.
MAX_FAILURE_SUMMARY_LENGTH = 300


class SourceRunStatus(BaseModel):
    """Per-source ingestion outcome captured during a single run."""

    source: str
    status: Literal["ok", "failed"] = "ok"
    fetched_count: int = 0
    duration_ms: int = 0
    error: str | None = None


class PipelineRun(BaseModel):
    run_id: str
    user_id: str
    target_week: str
    trigger_type: TriggerType = "manual"
    status: RunStatus = "queued"
    current_stage: RunStage = "queued"
    attempt_number: int = 1
    created_at: str
    updated_at: str
    failure_summary: str | None = None
    track_id: str | None = None
    sources: list[SourceRunStatus] = Field(default_factory=list)

    def learner_status(self) -> str:
        """
        Collapse the operational run state into a small, learner-safe
        summary the frontend can use to distinguish:
        - "no_track_yet": nothing has ever run for this learner/week
        - "pending": a run is queued or in progress
        - "failed": the most recent attempt failed
        - "ready": the run succeeded or resolved to an existing track
        """
        if self.status in ("queued", "running", "retryable"):
            return "pending"
        if self.status == "failed":
            return "failed"
        if self.status in ("succeeded", "skipped_existing"):
            return "ready"
        return "pending"


def sanitize_failure_summary(error: BaseException) -> str:
    """
    Produce a bounded, sanitized one-line failure summary safe to persist.
    Strips stack traces and truncates so accidental inclusion of sensitive
    payloads in long exception messages cannot grow the run record.
    """
    message = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
    summary = f"{type(error).__name__}: {message}"
    if len(summary) > MAX_FAILURE_SUMMARY_LENGTH:
        summary = summary[: MAX_FAILURE_SUMMARY_LENGTH - 1] + "…"
    return summary
