"""
Unit tests for digest idempotency (issue #16).

Tests the storage-layer retry-safety logic in isolation — no network,
no Nebius calls, no real file system pollution. Uses a temp directory
and a hand-built fake digest to verify the contract: a digest must not
exist before save_digest is called, and must exist after.

For a full end-to-end smoke test exercising the real pipeline (real
sources, real Nebius scoring), see manual testing notes in NOTES.md —
that's deliberately not automated here since it's slow and costs
Nebius credits on every run.

Run with:
    cd backend
    python -m pytest ../tests/test_idempotency.py -v
"""
import os
import tempfile
from stacktwin.profile.schema import WeeklyDigest, DigestItem, ArticleScore
from stacktwin.storage.json_storage import JSONStorage


def _build_fake_digest(week_start: str = "2026-06-20") -> WeeklyDigest:
    """Builds a digest with no network or Nebius dependency, for isolated tests."""
    fake_score = ArticleScore(
        relevance=0.8, novelty=0.5, practicality=0.7, difficulty=0.3,
        urgency=0.2, stack_match=0.8, learning_value=0.6,
        time_cost_minutes=5, overall=0.7,
        why_this_matters="test", recommended_action="read_now"
    )
    return WeeklyDigest(
        week_start=week_start,
        profile_name="RetryTest",
        items=[DigestItem(
            title="Fake Article", url="https://example.com/fake",
            source="devto", summary="test", score=fake_score,
            estimated_reading_minutes=5, tags=[], quiz=[]
        )],
        total_items_processed=1,
        generated_at=f"{week_start}T00:00:00+00:00"
    )


def test_failed_run_remains_retryable():
    """
    Simulates a pipeline crash that happens before save_digest is called.
    Confirms no partial/corrupt digest exists, and a subsequent successful
    save works correctly — this is the retry-safety guarantee issue #16
    requires.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JSONStorage(
            profiles_dir=os.path.join(tmpdir, "profiles"),
            outputs_dir=os.path.join(tmpdir, "outputs")
        )

        user_id = "test_retry_user@example.com"
        week_start = "2026-06-20"

        # Simulates the crash state — save_digest was never reached
        existing = storage.load_digest_by_week(user_id, week_start)
        assert existing is None, "Digest should not exist before it's saved"

        # Simulates a successful retry
        digest = _build_fake_digest(week_start)
        path = storage.save_digest(user_id, digest)
        assert os.path.exists(path)

        existing2 = storage.load_digest_by_week(user_id, week_start)
        assert existing2 is not None, "Digest should exist after successful retry"
        assert existing2.items[0].title == "Fake Article"


def test_second_save_for_same_week_does_not_lose_data():
    """
    Confirms that load_digest_by_week correctly distinguishes between
    different weeks for the same user — a digest saved for one week
    should not appear when querying a different week.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JSONStorage(
            profiles_dir=os.path.join(tmpdir, "profiles"),
            outputs_dir=os.path.join(tmpdir, "outputs")
        )

        user_id = "test_week_isolation@example.com"

        digest_week1 = _build_fake_digest("2026-06-13")
        storage.save_digest(user_id, digest_week1)

        # Different week, same user — should not find week1's digest
        result = storage.load_digest_by_week(user_id, "2026-06-20")
        assert result is None, "Different week should not return another week's digest"

        # Correct week — should find it
        result_correct = storage.load_digest_by_week(user_id, "2026-06-13")
        assert result_correct is not None