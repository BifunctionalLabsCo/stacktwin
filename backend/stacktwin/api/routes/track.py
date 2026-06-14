from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from stacktwin.storage.factory import get_storage


router = APIRouter()


@router.get("/history")
def get_track_history(
    user_id: str = Query(..., description="User email address")
):
    storage = get_storage()
    history = storage.load_digest_history(user_id)

    return JSONResponse(content={
        "user_id": user_id,
        "weeks": history,
        "total": len(history)
    })


@router.get("/history/{week_start}")
def get_week_digest(
    week_start: str,
    user_id: str = Query(..., description="User email address")
):
    storage = get_storage()
    digest = storage.load_digest_by_week(user_id, week_start)

    if not digest:
        raise HTTPException(
            status_code=404,
            detail=f"No digest found for user {user_id} on week {week_start}"
        )

    return JSONResponse(content=digest.model_dump())