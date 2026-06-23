import os
from datetime import datetime, UTC
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from stacktwin.storage.factory import get_storage


router = APIRouter()


def _current_week_start() -> str:
    """Returns today's date as the week identifier — matches digest.py's format."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


@router.post("/run")
def run_pipeline(
    user_id: str = Query(..., description="User email address")
):
    """
    Trigger the full pipeline for a specific user.
    Idempotent — if a digest already exists for this user and week,
    returns it directly instead of recomputing. Prevents double work
    if the job is retried after a crash or called twice accidentally.
    """
    try:
        storage = get_storage()
        profile = storage.load_profile(user_id)

        if not profile:
            raise HTTPException(
                status_code=404,
                detail="No profile found for this user. Upload a CV first."
            )

        week_start = _current_week_start()
        existing_digest = storage.load_digest_by_week(user_id, week_start)

        if existing_digest:
            return JSONResponse(content={
                "status": "digest_already_exists",
                "user_id": user_id,
                "week_start": week_start,
                "items": len(existing_digest.items),
                "total_processed": existing_digest.total_items_processed
            })

        from stacktwin.pipeline.ingest import load_or_fetch, cleanup_raw_cache
        from stacktwin.pipeline.score import score_articles
        from stacktwin.pipeline.digest import build_digest

        print(f"[pipeline] running for user: {user_id}")
        articles = load_or_fetch(limit_per_source=30)
        scored = score_articles(articles, profile, user_id=user_id)
        digest = build_digest(scored, profile, top_n=10)
        path = storage.save_digest(user_id, digest)
        cleanup_raw_cache(cache_dir=os.getenv("OUTPUTS_DIR", "outputs"))

        return JSONResponse(content={
            "status": "computed",
            "user_id": user_id,
            "digest_path": path,
            "items": len(digest.items),
            "total_processed": digest.total_items_processed
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest")
def get_latest_digest(
    user_id: str = Query(..., description="User email address")
):
    storage = get_storage()
    digest = storage.load_latest_digest(user_id)

    if not digest:
        raise HTTPException(
            status_code=404,
            detail="No digest found. Run the pipeline first."
        )

    return JSONResponse(content=digest.model_dump())


@router.get("/export")
def export_digest(
    user_id: str = Query(..., description="User email address"),
    format: str = "markdown"
):
    storage = get_storage()
    digest = storage.load_latest_digest(user_id)

    if not digest:
        raise HTTPException(status_code=404, detail="No digest found.")

    if format == "markdown":
        lines = [
            f"# StackTwin Weekly Digest",
            f"**Week:** {digest.week_start}",
            f"**Developer:** {digest.profile_name}",
            f"**Articles processed:** {digest.total_items_processed}",
            "",
            "---",
            ""
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
                "Content-Disposition": f"attachment; filename=stacktwin-digest-{digest.week_start}.md"
            }
        )

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported format: {format}. Supported: markdown"
    )