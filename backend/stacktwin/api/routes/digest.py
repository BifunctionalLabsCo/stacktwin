import hmac
import json
import os
import subprocess
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from stacktwin.jobs.nebius import submit_weekly_content_prefetch_job, submit_weekly_pipeline_job
from stacktwin.learning.builder import build_weekly_track
from stacktwin.pipeline.digest import DIGEST_SIZE, build_digest
from stacktwin.pipeline.ingest import (
    SOURCE_LIMIT,
    load_or_build_tag_index,
    load_or_fetch,
    prefetch_weekly_content,
)
from stacktwin.pipeline.run import (
    PipelineRun,
    RunStage,
    SourceRunStatus,
    sanitize_failure_summary,
)
from stacktwin.pipeline.score import filter_by_tags, score_articles
from stacktwin.pipeline.sources.base import Article
from stacktwin.profile.schema import ArticleScore
from stacktwin.storage.factory import get_storage

router = APIRouter()

# Structured logging convention for this module: every pipeline log line is
# prefixed with `[pipeline] run_id=<run_id> stage=<stage>` so a single run
# attempt can be correlated across local Uvicorn output and Nebius execution
# logs. Use `_log()` below rather than ad-hoc print() calls during pipeline
# execution.

MAX_RUN_HISTORY = 20


@router.post("/prefetch")
def prefetch_content(x_stacktwin_schedule_token: str | None = Header(default=None)):
    """Refresh the shared weekly source pool; no learner scoring or lesson generation occurs."""
    expected_token = os.getenv("STACKTWIN_SCHEDULE_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=503, detail="Weekly prefetch is not configured.")
    if not x_stacktwin_schedule_token or not hmac.compare_digest(
        x_stacktwin_schedule_token, expected_token
    ):
        raise HTTPException(status_code=401, detail="Invalid schedule token.")

    if os.getenv("STACKTWIN_PIPELINE_EXECUTION", "local") == "nebius_job":
        try:
            job = submit_weekly_content_prefetch_job(str(uuid.uuid4()))
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=502, detail=sanitize_failure_summary(error)) from error
        return JSONResponse(
            status_code=202,
            content={"status": "submitted", "job_id": job.job_id, "job_name": job.name},
        )

    return JSONResponse(content={"status": "prefetched", **prefetch_weekly_content(get_storage())})


@router.post("/prefetch/ensure")
def ensure_prefetched_content():
    """Idempotently ensure the shared weekly content pool is ready for an authenticated app visit."""
    storage = get_storage()
    today = datetime.now(UTC).date()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    snapshot = storage.load_content_snapshot(week_start)
    if snapshot and snapshot.get("tag_index") is not None:
        return {"status": "ready", "week_start": week_start}

    owner_id = str(uuid.uuid4())
    if not storage.acquire_content_prefetch_lease(week_start, owner_id):
        lease = storage.load_content_prefetch_lease(week_start) or {}
        return {"status": lease.get("status", "pending"), "week_start": week_start}

    if os.getenv("STACKTWIN_PIPELINE_EXECUTION", "local") == "nebius_job":
        try:
            job = submit_weekly_content_prefetch_job(owner_id)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            storage.fail_content_prefetch_lease(week_start, owner_id, sanitize_failure_summary(error))
            raise HTTPException(status_code=502, detail=sanitize_failure_summary(error)) from error
        return {"status": "pending", "week_start": week_start, "job_id": job.job_id}

    result = prefetch_weekly_content(storage, owner_id=owner_id)
    return {"status": "ready", **result}


def _log(run_id: str, stage: str, message: str) -> None:
    print(f"[pipeline] run_id={run_id} stage={stage} {message}")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _transition(storage, run: PipelineRun, stage: RunStage, status: str | None = None) -> None:
    run.current_stage = stage
    if status:
        run.status = status
    run.updated_at = _now()
    storage.save_run(run)
    _log(run.run_id, stage, f"status={run.status}")


@router.post("/run")
def run_pipeline(user_id: str = Query(..., description="User email address")):
    """
    Trigger the full pipeline for a specific user.
    Uses today's article cache if available and skips re-fetching.

    Every invocation creates or resolves to a durable PipelineRun record
    (see stacktwin.pipeline.run.PipelineRun) keyed by (user_id, target_week).
    The run record is persisted via the storage backend and returned to the
    caller alongside the existing pipeline result fields.
    """
    if os.getenv("STACKTWIN_PIPELINE_EXECUTION", "local") == "nebius_job":
        try:
            job = submit_weekly_pipeline_job(user_id)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=502, detail=sanitize_failure_summary(error)) from error
        return JSONResponse(
            status_code=202,
            content={
                "status": "submitted",
                "user_id": user_id,
                "job_id": job.job_id,
                "job_name": job.name,
                "job_state": job.state,
            },
        )

    storage = get_storage()
    today = datetime.now(UTC).date()
    week_start = (today - timedelta(days=today.weekday())).isoformat()

    run = PipelineRun(
        run_id=str(uuid.uuid4()),
        user_id=user_id,
        target_week=week_start,
        trigger_type="manual",
        status="running",
        current_stage="queued",
        attempt_number=1,
        created_at=_now(),
        updated_at=_now(),
    )
    storage.save_run(run)
    _log(run.run_id, run.current_stage, f"created for user={user_id} week={week_start}")

    try:
        existing_digest = storage.load_digest_by_week(user_id, week_start)
        existing_track = storage.load_track_by_week(user_id, week_start)

        if existing_digest and existing_track:
            run.track_id = existing_track.id
            _transition(storage, run, "done", "skipped_existing")
            return JSONResponse(
                content={
                    "status": "digest-already-exists",
                    "user_id": user_id,
                    "week_start": week_start,
                    "track_id": existing_track.id,
                    "items": len(existing_track.modules),
                    "total_processed": existing_digest.total_items_processed,
                    "run": run.model_dump(mode="json"),
                }
            )

        _transition(storage, run, "loading_profile")
        profile = storage.load_profile(user_id)

        if not profile:
            run.failure_summary = "No profile found for this user."
            _transition(storage, run, "loading_profile", "failed")
            raise HTTPException(
                status_code=404, detail="No profile found for this user. Upload a CV first."
            )

        if existing_digest:
            _transition(storage, run, "generating")
            track = build_weekly_track(existing_digest, profile)
            _transition(storage, run, "persisting")
            track_path = storage.save_track(user_id, track)
            run.track_id = track.id
            _transition(storage, run, "done", "succeeded")
            return JSONResponse(
                content={
                    "status": "track-backfilled",
                    "user_id": user_id,
                    "week_start": week_start,
                    "track_id": track.id,
                    "track_path": track_path,
                    "items": len(track.modules),
                    "total_processed": existing_digest.total_items_processed,
                    "run": run.model_dump(mode="json"),
                }
            )

        _transition(storage, run, "ingesting")
        ingest_started = time.monotonic()
        articles = load_or_fetch(
            limit_per_source=SOURCE_LIMIT, storage=storage, week_start=week_start
        )
        ingest_duration_ms = int((time.monotonic() - ingest_started) * 1000)
        run.sources = _summarize_sources(articles, ingest_duration_ms)
        storage.save_run(run)
        _log(run.run_id, "ingesting", f"fetched {len(articles)} articles total")

        _transition(storage, run, "scoring")
        # Load any articles already scored in a prior failed attempt (S3 is source of truth).
        raw_checkpoint = storage.load_scored_articles_for_week(user_id, week_start)
        already_scored = _deserialize_scored(raw_checkpoint)
        if already_scored:
            _log(
                run.run_id, "scoring", f"checkpoint: {len(already_scored)} articles already scored"
            )

        tag_index = load_or_build_tag_index(articles, storage=storage, week_start=week_start)
        filtered = filter_by_tags(articles, profile, tag_index)

        def _persist_scored(article: Article, score: ArticleScore) -> None:
            storage.save_scored_article(
                user_id,
                week_start,
                article.url,
                {
                    "article": article.to_dict(),
                    "score": score.model_dump(mode="json"),
                },
            )

        scored = score_articles(
            filtered,
            profile,
            already_scored=already_scored,
            on_scored=_persist_scored,
        )

        _transition(storage, run, "generating")
        digest = build_digest(scored, profile, top_n=DIGEST_SIZE, week_start=week_start)

        _transition(storage, run, "persisting")
        digest_path = storage.save_digest(user_id, digest)
        track = build_weekly_track(digest, profile)
        track_path = storage.save_track(user_id, track)
        # Clear checkpoint only after both digest and track are persisted successfully.
        # If track generation or save_track fails, the checkpoint is preserved so
        # a retry can resume without rescoring from scratch.
        storage.clear_scored_checkpoint(user_id, week_start)

        run.track_id = track.id
        _transition(storage, run, "done", "succeeded")

        return JSONResponse(
            content={
                "status": "computed",
                "user_id": user_id,
                "week_start": week_start,
                "track_id": track.id,
                "digest_path": digest_path,
                "track_path": track_path,
                "items": len(track.modules),
                "total_processed": digest.total_items_processed,
                "run": run.model_dump(mode="json"),
            }
        )

    except HTTPException:
        raise
    except Exception as error:
        run.failure_summary = sanitize_failure_summary(error)
        _transition(storage, run, run.current_stage, "failed")
        raise HTTPException(status_code=500, detail=str(error)) from error


def _deserialize_scored(raw: list[dict]) -> list[tuple[Article, ArticleScore]]:
    """Convert raw checkpoint dicts back to (Article, ArticleScore) tuples."""
    result = []
    for item in raw:
        try:
            article = Article(**item["article"])
            score = ArticleScore(**item["score"])
            result.append((article, score))
        except Exception as exc:
            print(f"[pipeline] skipping corrupted checkpoint entry: {exc}")
    return result


def _summarize_sources(articles, duration_ms: int) -> list[SourceRunStatus]:
    """Group fetched articles by source to produce a per-source run summary."""
    counts: dict[str, int] = defaultdict(int)
    for article in articles:
        counts[article.source] += 1
    return [
        SourceRunStatus(source=source, status="ok", fetched_count=count, duration_ms=duration_ms)
        for source, count in counts.items()
    ]


@router.get("/runs/latest")
def get_latest_run(user_id: str = Query(..., description="User email address")):
    """Return the most recent pipeline run for the requesting user."""
    storage = get_storage()
    run = storage.load_latest_run(user_id)
    if not run:
        raise HTTPException(status_code=404, detail="No pipeline runs found for this user.")
    return JSONResponse(
        content={**run.model_dump(mode="json"), "learner_status": run.learner_status()}
    )


@router.get("/runs/history")
def get_run_history(user_id: str = Query(..., description="User email address")):
    """Return bounded pipeline run history for the requesting user, newest first."""
    storage = get_storage()
    runs = storage.load_run_history(user_id, limit=MAX_RUN_HISTORY)
    return JSONResponse(
        content={
            "user_id": user_id,
            "runs": [
                {**run.model_dump(mode="json"), "learner_status": run.learner_status()}
                for run in runs
            ],
            "total": len(runs),
        }
    )


@router.get("/latest")
def get_latest_digest(user_id: str = Query(..., description="User email address")):
    storage = get_storage()
    digest = storage.load_latest_digest(user_id)

    if not digest:
        raise HTTPException(status_code=404, detail="No digest found. Run the pipeline first.")

    return JSONResponse(content=digest.model_dump())


@router.get("/export")
def export_digest(
    user_id: str = Query(..., description="User email address"), format: str = "markdown"
):
    storage = get_storage()
    digest = storage.load_latest_digest(user_id)

    if not digest:
        raise HTTPException(status_code=404, detail="No digest found.")

    if format == "markdown":
        lines = [
            "# StackTwin Weekly Digest",
            f"**Week:** {digest.week_start}",
            f"**Developer:** {digest.profile_name}",
            f"**Articles processed:** {digest.total_items_processed}",
            "",
            "---",
            "",
        ]

        for i, item in enumerate(digest.items, 1):
            lines += [
                f"## {i}. {item.title}",
                f"**Source:** {item.source} | "
                f"**Reading time:** {item.estimated_reading_minutes} min | "
                f"**Score:** {item.score.overall:.2f}",
                f"**Link:** {item.url}",
                "",
                item.summary,
                "",
                f"> **Why this matters:** {item.score.why_this_matters}",
                "",
            ]

            if item.quiz:
                lines.append("**Quiz:**")
                for q in item.quiz:
                    lines.append(f"- {q['question']}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return PlainTextResponse(
            content="\n".join(lines),
            media_type="text/markdown",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=stacktwin-digest-{digest.week_start}.md"
                )
            },
        )

    raise HTTPException(
        status_code=400, detail=f"Unsupported format: {format}. Supported: markdown"
    )
