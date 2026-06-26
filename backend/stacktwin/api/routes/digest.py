from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from stacktwin.storage.factory import get_storage
from stacktwin.pipeline.digest import DIGEST_SIZE, build_digest
from stacktwin.pipeline.ingest import SOURCE_LIMIT, load_or_fetch, load_or_build_tag_index
from stacktwin.pipeline.score import filter_by_tags, score_articles
from stacktwin.learning.builder import build_weekly_track

router = APIRouter()


@router.post("/run")
def run_pipeline(user_id: str = Query(..., description="User email address")):
    """
    Trigger the full pipeline for a specific user.
    Uses today's article cache if available and skips re-fetching.
    """
    try:
        storage = get_storage()
        today = datetime.now(UTC).date()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        existing_digest = storage.load_digest_by_week(user_id, week_start)
        existing_track = storage.load_track_by_week(user_id, week_start)

        if existing_digest and existing_track:
            return JSONResponse(
                content={
                    "status": "digest-already-exists",
                    "user_id": user_id,
                    "week_start": week_start,
                    "track_id": existing_track.id,
                    "items": len(existing_track.modules),
                    "total_processed": existing_digest.total_items_processed,
                }
            )

        profile = storage.load_profile(user_id)

        if not profile:
            raise HTTPException(
                status_code=404, detail="No profile found for this user. Upload a CV first."
            )

        if existing_digest:
            track = build_weekly_track(existing_digest, profile)
            track_path = storage.save_track(user_id, track)
            return JSONResponse(
                content={
                    "status": "track-backfilled",
                    "user_id": user_id,
                    "week_start": week_start,
                    "track_id": track.id,
                    "track_path": track_path,
                    "items": len(track.modules),
                    "total_processed": existing_digest.total_items_processed,
                }
            )

        print(f"[pipeline] running for user: {user_id}")
        articles = load_or_fetch(limit_per_source=SOURCE_LIMIT)
        tag_index = load_or_build_tag_index(articles)
        filtered = filter_by_tags(articles, profile, tag_index)
        scored = score_articles(filtered, profile)
        digest = build_digest(scored, profile, top_n=DIGEST_SIZE, week_start=week_start)
        digest_path = storage.save_digest(user_id, digest)
        track = build_weekly_track(digest, profile)
        track_path = storage.save_track(user_id, track)

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
            }
        )

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


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
