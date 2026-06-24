from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from stacktwin.api.main import app
from stacktwin.api.routes import digest as digest_routes
from stacktwin.pipeline.sources.base import Article
from stacktwin.profile.schema import DeveloperProfile
from stacktwin.storage.json_storage import JSONStorage

from tests.test_storage import _digest

client = TestClient(app)


def _week_start() -> str:
    today = datetime.now(UTC).date()
    return (today - timedelta(days=today.weekday())).isoformat()


def _storage_with_profile(tmp_path, user_id: str = "ada@example.com") -> JSONStorage:
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    storage.save_profile(user_id, DeveloperProfile(name="Ada"))
    return storage


def _fake_articles():
    return [
        Article(title="A", url="https://example.com/a", source="devto", summary="s"),
        Article(title="B", url="https://example.com/b", source="hackernews", summary="s"),
    ]


def test_run_success_records_succeeded_run(monkeypatch, tmp_path):
    storage = _storage_with_profile(tmp_path)
    monkeypatch.setattr(digest_routes, "get_storage", lambda: storage)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    from stacktwin.pipeline import ingest as ingest_module

    monkeypatch.setattr(ingest_module, "load_or_fetch", lambda **kwargs: _fake_articles())

    response = client.post("/api/digest/run?user_id=ada@example.com")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "computed"
    assert body["run"]["status"] == "succeeded"
    assert body["run"]["current_stage"] == "done"
    assert body["run"]["track_id"] == body["track_id"]
    assert body["run"]["failure_summary"] is None
    sources = {s["source"]: s["fetched_count"] for s in body["run"]["sources"]}
    assert sources == {"devto": 1, "hackernews": 1}

    latest = client.get("/api/digest/runs/latest?user_id=ada@example.com")
    assert latest.status_code == 200
    assert latest.json()["status"] == "succeeded"
    assert latest.json()["learner_status"] == "ready"


def test_run_failure_records_failed_run_with_sanitized_summary(monkeypatch, tmp_path):
    storage = _storage_with_profile(tmp_path)
    monkeypatch.setattr(digest_routes, "get_storage", lambda: storage)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    from stacktwin.pipeline import ingest as ingest_module

    def _boom(**kwargs):
        raise RuntimeError("network exploded with secret-key=abc123\nTraceback (most recent...)")

    monkeypatch.setattr(ingest_module, "load_or_fetch", _boom)

    response = client.post("/api/digest/run?user_id=ada@example.com")
    assert response.status_code == 500

    latest = client.get("/api/digest/runs/latest?user_id=ada@example.com")
    assert latest.status_code == 200
    body = latest.json()
    assert body["status"] == "failed"
    assert body["learner_status"] == "failed"
    assert "Traceback" not in body["failure_summary"]
    assert len(body["failure_summary"]) <= 300


def test_retry_after_failure_creates_new_run_id(monkeypatch, tmp_path):
    storage = _storage_with_profile(tmp_path)
    monkeypatch.setattr(digest_routes, "get_storage", lambda: storage)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    from stacktwin.pipeline import ingest as ingest_module

    def _boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ingest_module, "load_or_fetch", _boom)
    client.post("/api/digest/run?user_id=ada@example.com")
    failed_run_id = storage.load_latest_run("ada@example.com").run_id

    monkeypatch.setattr(ingest_module, "load_or_fetch", lambda **kwargs: _fake_articles())
    retry_response = client.post("/api/digest/run?user_id=ada@example.com")
    assert retry_response.status_code == 200
    retried_run_id = retry_response.json()["run"]["run_id"]

    assert retried_run_id != failed_run_id

    history = client.get("/api/digest/runs/history?user_id=ada@example.com").json()["runs"]
    assert len(history) == 2
    assert history[0]["run_id"] == retried_run_id
    assert history[0]["status"] == "succeeded"
    assert history[1]["run_id"] == failed_run_id
    assert history[1]["status"] == "failed"


def test_skipped_existing_run_is_distinguishable_from_fresh_run(monkeypatch, tmp_path):
    storage = _storage_with_profile(tmp_path)
    week_start = _week_start()
    storage.save_digest("ada@example.com", _digest(week_start))
    from stacktwin.learning.builder import build_weekly_track

    profile = storage.load_profile("ada@example.com")
    storage.save_track("ada@example.com", build_weekly_track(_digest(week_start), profile))
    monkeypatch.setattr(digest_routes, "get_storage", lambda: storage)

    response = client.post("/api/digest/run?user_id=ada@example.com")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "digest-already-exists"
    assert body["run"]["status"] == "skipped_existing"

    latest = client.get("/api/digest/runs/latest?user_id=ada@example.com")
    assert latest.json()["status"] == "skipped_existing"
    assert latest.json()["learner_status"] == "ready"


def test_run_routes_enforce_user_isolation(monkeypatch, tmp_path):
    storage = _storage_with_profile(tmp_path, user_id="ada@example.com")
    storage.save_profile("bo@example.com", DeveloperProfile(name="Bo"))
    monkeypatch.setattr(digest_routes, "get_storage", lambda: storage)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    from stacktwin.pipeline import ingest as ingest_module

    monkeypatch.setattr(ingest_module, "load_or_fetch", lambda **kwargs: _fake_articles())

    client.post("/api/digest/run?user_id=ada@example.com")

    bo_latest = client.get("/api/digest/runs/latest?user_id=bo@example.com")
    assert bo_latest.status_code == 404

    bo_history = client.get("/api/digest/runs/history?user_id=bo@example.com")
    assert bo_history.status_code == 200
    assert bo_history.json()["runs"] == []

    ada_latest = client.get("/api/digest/runs/latest?user_id=ada@example.com")
    assert ada_latest.status_code == 200
    assert ada_latest.json()["user_id"] == "ada@example.com"


@pytest.mark.parametrize("user_id", ["ada@example.com"])
def test_no_track_yet_has_no_run_record(monkeypatch, tmp_path, user_id):
    storage = _storage_with_profile(tmp_path, user_id=user_id)
    monkeypatch.setattr(digest_routes, "get_storage", lambda: storage)

    response = client.get(f"/api/digest/runs/latest?user_id={user_id}")
    assert response.status_code == 404
