import json
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse


router = APIRouter()

OUTPUTS_DIR = "outputs"


@router.get("/history")
def get_track_history():
    """
    Return all past weekly digests as the learning track history.
    Shows what the developer has been recommended over time.
    """
    if not os.path.exists(OUTPUTS_DIR):
        return JSONResponse(content={"weeks": [], "total": 0})

    digest_files = sorted([
        f for f in os.listdir(OUTPUTS_DIR)
        if f.startswith("digest_") and f.endswith(".json")
    ], reverse=True)

    weeks = []
    for filename in digest_files:
        with open(os.path.join(OUTPUTS_DIR, filename)) as f:
            digest = json.load(f)
            weeks.append({
                "week_start": digest.get("week_start"),
                "generated_at": digest.get("generated_at"),
                "items": len(digest.get("items", [])),
                "total_processed": digest.get("total_items_processed", 0)
            })

    return JSONResponse(content={
        "weeks": weeks,
        "total": len(weeks)
    })


@router.get("/history/{week_start}")
def get_week_digest(week_start: str):
    """
    Return a specific week's digest by date.
    Example: GET /api/track/history/2026-06-09
    """
    filepath = os.path.join(OUTPUTS_DIR, f"digest_{week_start}.json")

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=404,
            detail=f"No digest found for week {week_start}"
        )

    with open(filepath) as f:
        return JSONResponse(content=json.load(f))