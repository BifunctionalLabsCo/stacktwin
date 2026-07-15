import json

from stacktwin.learning import builder
from stacktwin.pipeline import digest, ingest, score
from stacktwin.pipeline.sources.base import Article
from stacktwin.profile.schema import ArticleScore, DeveloperProfile


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _completion(content: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def _articles() -> list[Article]:
    return [
        Article(
            title="FastAPI dependency patterns",
            url="https://example.com/fastapi",
            source="devto",
            summary="A practical comparison of dependency injection patterns in FastAPI.",
            tags=["python", "fastapi"],
        ),
        Article(
            title="React Server Components tradeoffs",
            url="https://example.com/react",
            source="hackernews",
            summary="A measured review of data loading and caching tradeoffs.",
            tags=["react", "frontend"],
        ),
    ]


def _profile() -> DeveloperProfile:
    return DeveloperProfile(
        name="Engineer",
        current_role="Software Engineer",
        current_stack=["Python", "React"],
        learning=["FastAPI"],
        learning_goals=["Build reliable APIs"],
    )


def _score(overall: float = 0.9) -> ArticleScore:
    return ArticleScore(
        relevance=0.9,
        novelty=0.7,
        practicality=0.9,
        difficulty=0.5,
        urgency=0.4,
        stack_match=0.9,
        learning_value=0.9,
        time_cost_minutes=12,
        overall=overall,
        why_this_matters="Supports the learner's FastAPI goal.",
        recommended_action="read_now",
    )


def test_tagging_uses_compact_ids_and_maps_them_back_to_urls(monkeypatch):
    monkeypatch.setattr(ingest, "NEBIUS_API_KEY", "job-token")
    captured = {}

    def post(url, **kwargs):
        captured["payload"] = kwargs["json"]
        return _Response(
            _completion(
                {
                    "items": [
                        {"id": "a1", "tags": ["fastapi", "python", "backend"]},
                        {"id": "a2", "tags": ["react", "frontend", "web-development"]},
                    ]
                }
            )
        )

    monkeypatch.setattr(ingest.httpx, "post", post)

    tagged = ingest._call_nebius_for_tags(_articles())

    assert tagged[0]["url"] == "https://example.com/fastapi"
    assert tagged[1]["tags"][0] == "react"
    assert "https://example.com/fastapi" not in captured["payload"]["messages"][1]["content"]


def test_ranking_scores_a_comparative_batch_with_one_profile_context(monkeypatch):
    monkeypatch.setattr(score, "NEBIUS_API_KEY", "job-token")
    captured = {}
    items = []
    for index in range(2):
        value = _score(0.9 - index * 0.2).model_dump(mode="json")
        items.append({"id": f"a{index + 1}", **value})

    def post(url, **kwargs):
        captured["payload"] = kwargs["json"]
        return _Response(_completion({"items": items}))

    monkeypatch.setattr(score.httpx, "post", post)

    scores = score._score_batch(_articles(), _profile())

    assert [value.overall for value in scores] == [0.9, 0.7]
    user_prompt = captured["payload"]["messages"][1]["content"]
    assert user_prompt.count("LEARNER PROFILE") == 1
    assert '"id": "a2"' in user_prompt


def test_digest_prepares_ranked_sources_in_one_batch(monkeypatch):
    result = {
        "items": [
            {
                "id": "a1",
                "summary": "FastAPI dependencies make service boundaries explicit.",
                "why_this_matters": "Use this to improve your FastAPI API architecture.",
                "estimated_reading_minutes": 11,
                "quiz": [],
            },
            {
                "id": "a2",
                "summary": "Server Components shift data work across the React boundary.",
                "why_this_matters": "Compare this with your current React data flow.",
                "estimated_reading_minutes": 13,
                "quiz": [],
            },
        ]
    }
    monkeypatch.setattr(digest, "_call_nebius", lambda *args, **kwargs: json.dumps(result))
    batch = list(zip(_articles(), [_score(), _score(0.8)], strict=True))

    briefs = digest._prepare_digest_batch(batch, _profile(), {"a1"})

    assert len(briefs) == 2
    assert "FastAPI API architecture" in briefs[0]["why_this_matters"]
    assert briefs[1]["estimated_reading_minutes"] == 13


def test_track_authoring_uses_generated_lesson_content(monkeypatch):
    from tests.test_storage import _digest

    item = _digest("2026-07-13").items[0]
    generated = {
        "items": [
            {
                "id": "a1",
                "difficulty": "Intermediate",
                "estimated_minutes": 24,
                "personalization_reason": "Connects directly to your API reliability goal.",
                "context_brief": "The lesson explains a concrete reliability tradeoff.",
                "objectives": ["Compare two approaches", "Evaluate failure modes", "Test one"],
                "key_concepts": ["Boundary: isolates change", "Signal: measures failure"],
                "exercise": {
                    "title": "Run a boundary test",
                    "instructions": (
                        "Write one failing case, implement the boundary, and record the result."
                    ),
                },
                "checkpoint": {
                    "question": "Which test gives the clearest evidence?",
                    "options": ["A", "B", "C", "D"],
                    "answer_index": 0,
                    "explanation": "A measures the intended boundary directly.",
                },
                "takeaway": "Measure the boundary before expanding the change.",
            }
        ]
    }
    monkeypatch.setenv("STACKTWIN_PIPELINE_LLM_ACTIVE", "true")
    monkeypatch.setenv("NEBIUS_API_KEY", "job-token")
    monkeypatch.setattr(
        builder.httpx, "post", lambda *args, **kwargs: _Response(_completion(generated))
    )

    modules = builder._build_modules([item], _profile(), 120)

    assert modules[0].exercise.title == "Run a boundary test"
    assert modules[0].checkpoint.answer == "A"
    assert modules[0].context_brief.startswith("The lesson explains")
