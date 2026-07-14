from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from stacktwin.api.models import LessonModuleResponse, WeeklyTrackResponse
from stacktwin.learning.schema import LearningModule, WeeklyTrack
from stacktwin.llm import app_mode
from stacktwin.storage.factory import get_cloud_storage, get_storage

router = APIRouter()


LESSON_DETAILS = {
    "small-agent-workflows": {
        "context_brief": (
            "Agent systems become easier to test and operate when each step has a narrow job, "
            "a typed input, and an observable output."
        ),
        "objectives": [
            "Separate orchestration from model reasoning.",
            "Define one measurable outcome for each agent step.",
            "Recognize when a deterministic function should replace an LLM call.",
        ],
        "key_concepts": [
            "Small agent boundaries reduce prompt coupling.",
            "Typed state makes retries and evaluation practical.",
            "Human review belongs at explicit risk boundaries.",
        ],
        "exercise": {
            "title": "Shrink one workflow",
            "instructions": (
                "Take an existing automation and divide it into collect, decide, and act steps. "
                "Write the input and output shape for each step."
            ),
        },
        "checkpoint": {
            "question": "Which task is the best candidate for deterministic code?",
            "options": [
                "Choosing an ambiguous product strategy",
                "Validating that a response matches a JSON schema",
                "Explaining an unfamiliar research result",
            ],
            "answer": "Validating that a response matches a JSON schema",
            "explanation": (
                "Schema validation is deterministic, testable, and should not consume a model call."
            ),
        },
        "takeaway": "Use models for judgment and software for guarantees.",
        "available_actions": ["explain_deeper", "adapt_difficulty", "regenerate_checkpoint"],
    },
    "rag-evaluation-first": {
        "context_brief": (
            "Adding more context can hide retrieval failures. Evaluate whether the right evidence "
            "was found before tuning generation."
        ),
        "objectives": [
            "Separate retrieval quality from answer quality.",
            "Choose a small evaluation set from real user questions.",
            "Track evidence relevance before changing prompts.",
        ],
        "key_concepts": [
            "Recall measures whether useful evidence was retrieved.",
            "Precision exposes distracting or irrelevant context.",
            "A fixed evaluation set makes pipeline changes comparable.",
        ],
        "exercise": {
            "title": "Create a ten-question evaluation set",
            "instructions": (
                "Select ten representative questions, record the expected source for each, and "
                "score whether retrieval returns that source in the top five results."
            ),
        },
        "checkpoint": {
            "question": "What should be checked before increasing the context window?",
            "options": [
                "Whether retrieval returns relevant evidence",
                "Whether the model temperature is higher",
                "Whether the UI streams tokens",
            ],
            "answer": "Whether retrieval returns relevant evidence",
            "explanation": "More context does not repair missing or irrelevant retrieval results.",
        },
        "takeaway": "Measure retrieval before asking generation to compensate for it.",
        "available_actions": ["explain_deeper", "adapt_difficulty", "regenerate_checkpoint"],
    },
    "trending-repository-review": {
        "context_brief": (
            "Trending repositories are useful signals only when you inspect the engineering idea "
            "behind the attention."
        ),
        "objectives": [
            "Identify the durable idea behind a repository trend.",
            "Inspect maintenance and adoption signals.",
            "Write one practical experiment instead of bookmarking the repository.",
        ],
        "key_concepts": [
            "Stars indicate attention, not production readiness.",
            "Commit activity and issue quality reveal maintenance health.",
            "A small local experiment produces more learning than passive collection.",
        ],
        "exercise": {
            "title": "Run a repository viability scan",
            "instructions": (
                "Inspect the README, recent commits, open issues, and release history. Record one "
                "idea worth testing and one adoption risk."
            ),
        },
        "checkpoint": {
            "question": "Which signal best supports production readiness?",
            "options": [
                "A rapid increase in stars",
                "Maintained releases and responsive issue handling",
                "A polished social announcement",
            ],
            "answer": "Maintained releases and responsive issue handling",
            "explanation": (
                "Maintenance behavior is a stronger operational signal than attention alone."
            ),
        },
        "takeaway": "Translate attention into one testable engineering idea.",
        "available_actions": ["explain_deeper", "adapt_difficulty", "regenerate_checkpoint"],
    },
    "technical-video-notes": {
        "context_brief": (
            "Technical video becomes useful when it produces structured notes, a decision, or a "
            "small implementation task."
        ),
        "objectives": [
            "Extract claims instead of transcribing the video.",
            "Connect each claim to evidence or a source.",
            "Turn one insight into a practical next action.",
        ],
        "key_concepts": [
            "Active notes capture decisions and questions.",
            "Source links preserve provenance for later review.",
            "A time box prevents passive learning from consuming the week.",
        ],
        "exercise": {
            "title": "Create a five-line video brief",
            "instructions": (
                "Record the main claim, two supporting ideas, one disagreement or uncertainty, "
                "and one action to test this week."
            ),
        },
        "checkpoint": {
            "question": "What makes a technical video note actionable?",
            "options": [
                "It captures every spoken sentence",
                "It ends with a specific experiment or decision",
                "It uses several highlight colors",
            ],
            "answer": "It ends with a specific experiment or decision",
            "explanation": (
                "An explicit next action converts passive consumption into applied learning."
            ),
        },
        "takeaway": "Finish media with an action, not another item in the queue.",
        "available_actions": ["explain_deeper", "adapt_difficulty", "regenerate_checkpoint"],
    },
}


@router.get("/preview", response_model=WeeklyTrackResponse)
def get_track_preview() -> WeeklyTrackResponse:
    """Return a small API-backed track for frontend integration testing."""
    now = datetime.now(UTC)
    week_start = now.date() - timedelta(days=now.weekday())

    return WeeklyTrackResponse(
        id=f"preview-{week_start.isoformat()}",
        week_start=week_start.isoformat(),
        week_label=f"Week of {week_start.strftime('%B')} {week_start.day}",
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


@router.get("/preview/{module_id}", response_model=LessonModuleResponse)
def get_lesson_preview(module_id: str) -> LessonModuleResponse:
    track = get_track_preview()
    module = next((item for item in track.modules if item.id == module_id), None)
    details = LESSON_DETAILS.get(module_id)

    if not module or not details:
        raise HTTPException(status_code=404, detail=f"Unknown preview module: {module_id}")

    module_index = next(index for index, item in enumerate(track.modules) if item.id == module_id)
    next_module_id = (
        track.modules[module_index + 1].id if module_index + 1 < len(track.modules) else None
    )

    return LessonModuleResponse(
        **module.model_dump(),
        **details,
        track_id=track.id,
        next_module_id=next_module_id,
    )


@router.get("/current", response_model=WeeklyTrackResponse)
def get_current_track(user_id: str = Query(..., description="User email address")):
    storage = get_storage()
    if not storage.load_profile(user_id):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "profile_required",
                "message": "Create a developer profile before generating a weekly track.",
            },
        )

    today = datetime.now(UTC).date()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    track = storage.load_track_by_week(user_id, week_start)
    if not track and app_mode() == "local":
        try:
            track = get_cloud_storage().load_track_by_week(user_id, week_start)
            if track:
                storage.save_track(user_id, track)
        except OSError:
            pass
    if not track:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "track_not_ready",
                "message": "No generated weekly track is ready for this learner.",
            },
        )
    return WeeklyTrackResponse.model_validate(track, from_attributes=True)


@router.get("/latest", response_model=WeeklyTrackResponse)
def get_latest_track(user_id: str = Query(..., description="User email address")):
    """Return the newest available track, preferring local storage over cloud fallback."""
    storage = get_storage()
    track = storage.load_latest_track(user_id)
    if not track and app_mode() == "local":
        try:
            track = get_cloud_storage().load_latest_track(user_id)
        except OSError:
            pass
    if not track:
        raise HTTPException(status_code=404, detail="No previous weekly track is available.")
    return WeeklyTrackResponse.model_validate(track, from_attributes=True)


@router.get(
    "/{week_start}/modules/{module_id}",
    response_model=LessonModuleResponse,
)
def get_track_lesson(
    week_start: str,
    module_id: str,
    user_id: str = Query(..., description="User email address"),
):
    storage = get_storage()
    track = storage.load_track_by_week(user_id, week_start)
    if not track:
        raise HTTPException(status_code=404, detail="This weekly track could not be found.")

    module = next((item for item in track.modules if item.id == module_id), None)
    if not module:
        raise HTTPException(status_code=404, detail="This lesson could not be found.")
    return _lesson_response(track, module)


@router.get("/history")
def get_track_history(user_id: str = Query(..., description="User email address")):
    storage = get_storage()
    history = storage.load_track_history(user_id)

    return JSONResponse(content={"user_id": user_id, "weeks": history, "total": len(history)})


@router.get("/history/{week_start}")
def get_week_digest(week_start: str, user_id: str = Query(..., description="User email address")):
    storage = get_storage()
    track = storage.load_track_by_week(user_id, week_start)

    if not track:
        raise HTTPException(
            status_code=404, detail=f"No track found for user {user_id} on week {week_start}"
        )

    return WeeklyTrackResponse.model_validate(track, from_attributes=True)


def _lesson_response(track: WeeklyTrack, module: LearningModule) -> LessonModuleResponse:
    module_index = next(index for index, item in enumerate(track.modules) if item.id == module.id)
    next_module_id = (
        track.modules[module_index + 1].id if module_index + 1 < len(track.modules) else None
    )
    return LessonModuleResponse(
        **module.model_dump(),
        track_id=track.id,
        next_module_id=next_module_id,
    )
