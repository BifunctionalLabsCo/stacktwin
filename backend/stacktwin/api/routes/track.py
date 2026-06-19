from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from stacktwin.api.models import WeeklyTrackResponse
from stacktwin.storage.factory import get_storage


router = APIRouter()


@router.get("/preview", response_model=WeeklyTrackResponse)
def get_track_preview() -> WeeklyTrackResponse:
    """Return a small API-backed track for frontend integration testing."""
    now = datetime.now(UTC)

    return WeeklyTrackResponse(
        id=f"preview-{now.strftime('%Y-%m-%d')}",
        week_label=f"Week of {now.strftime('%B')} {now.day}",
        generated_at=now.isoformat(),
        learner_focus="Backend AI systems, retrieval quality, and practical agent workflows",
        weekly_time_budget_minutes=150,
        modules=[
            {
                "id": "small-agent-workflows",
                "title": "Ship smaller AI agents",
                "status": "ready",
                "difficulty": "Intermediate",
                "estimated_minutes": 42,
                "personalization_reason": (
                    "Chosen for backend engineers moving from automation scripts "
                    "to production workflows."
                ),
                "source_hints": [
                    {
                        "title": "Agent workflow signals",
                        "source": "hackernews",
                        "url": "https://news.ycombinator.com/",
                    },
                    {
                        "title": "Production implementation notes",
                        "source": "devto",
                        "url": "https://dev.to/",
                    },
                ],
            },
            {
                "id": "rag-evaluation-first",
                "title": "Evaluate RAG before adding more context",
                "status": "completed",
                "difficulty": "Advanced",
                "estimated_minutes": 35,
                "personalization_reason": (
                    "A practical checkpoint for teams building retrieval systems "
                    "under real constraints."
                ),
                "source_hints": [
                    {
                        "title": "Retrieval evaluation research",
                        "source": "arxiv",
                        "url": "https://arxiv.org/",
                    }
                ],
            },
            {
                "id": "trending-repository-review",
                "title": "Review one trending repository",
                "status": "ready",
                "difficulty": "Focused",
                "estimated_minutes": 28,
                "personalization_reason": (
                    "Use a live repository signal to separate durable engineering ideas "
                    "from weekly hype."
                ),
                "source_hints": [
                    {
                        "title": "GitHub Trending",
                        "source": "github_trending",
                        "url": "https://github.com/trending",
                    }
                ],
            },
            {
                "id": "technical-video-notes",
                "title": "Turn one technical video into working notes",
                "status": "queued",
                "difficulty": "Intermediate",
                "estimated_minutes": 32,
                "personalization_reason": (
                    "Convert a high-signal video into concepts and actions that fit "
                    "this week's learning budget."
                ),
                "source_hints": [
                    {
                        "title": "YouTube technical feed",
                        "source": "youtube",
                        "url": "https://www.youtube.com/",
                    }
                ],
            },
        ],
    )


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
