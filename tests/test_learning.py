from stacktwin.learning.builder import build_weekly_track
from stacktwin.profile.schema import DeveloperProfile

from tests.test_storage import _digest


def test_digest_builds_stable_reusable_learning_module():
    profile = DeveloperProfile(
        name="Ada",
        current_stack=["Python", "FastAPI"],
        learning_goals=["Build reliable RAG systems"],
        weekly_time_budget_hours=1,
    )
    digest = _digest()

    first = build_weekly_track(digest, profile)
    second = build_weekly_track(digest, profile)
    changed_digest = digest.model_copy(deep=True)
    changed_digest.items[0].url = "https://example.com/revised-source"
    changed = build_weekly_track(changed_digest, profile)

    assert first == second
    assert first.id.startswith(f"track-{digest.week_start}-")
    assert changed.id != first.id
    assert first.learner_focus == "Build reliable RAG systems"
    assert first.weekly_time_budget_minutes == 60
    assert first.modules[0].source_hints[0].url == digest.items[0].url
    assert first.modules[0].personalization_reason == digest.items[0].score.why_this_matters
    assert first.modules[0].objectives
    assert first.modules[0].exercise.instructions
    assert first.modules[0].checkpoint.answer in first.modules[0].checkpoint.options


def test_digest_quiz_answer_is_resolved_to_option_text():
    digest = _digest()
    digest.items[0].quiz = [
        {
            "question": "Which option is correct?",
            "options": ["A) First", "B) Second", "C) Third"],
            "correct": "B",
            "explanation": "The second option matches the source.",
        }
    ]

    track = build_weekly_track(digest, DeveloperProfile())

    assert track.modules[0].checkpoint.answer == "B) Second"
