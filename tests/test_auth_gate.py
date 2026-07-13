from fastapi.testclient import TestClient
from stacktwin.api.main import app
from stacktwin.api.routes import digest


def _prefetched_content(storage, fallback_storage=None):
    return {"week_start": "2026-07-13", "articles": 1, "tags": 1}


def _prefetch_failure(storage, fallback_storage=None):
    raise ValueError("source unavailable")


def test_schedule_token_prefetch_bypasses_browser_password_gate(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_PASSWORD", "shared-password")
    monkeypatch.setenv("STACKTWIN_SCHEDULE_TOKEN", "schedule-token")
    monkeypatch.setenv("STACKTWIN_APP_MODE", "local")
    monkeypatch.setattr(digest, "get_storage", lambda: object())
    monkeypatch.setattr(digest, "prefetch_weekly_content", _prefetched_content)

    response = TestClient(app).post(
        "/api/digest/prefetch",
        headers={"X-Stacktwin-Schedule-Token": "schedule-token"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "prefetched"


def test_local_prefetch_failures_return_a_sanitized_http_error(monkeypatch):
    monkeypatch.delenv("STACKTWIN_APP_PASSWORD", raising=False)
    monkeypatch.setenv("STACKTWIN_SCHEDULE_TOKEN", "schedule-token")
    monkeypatch.setenv("STACKTWIN_APP_MODE", "local")
    monkeypatch.setattr(digest, "get_storage", lambda: object())
    monkeypatch.setattr(digest, "prefetch_weekly_content", _prefetch_failure)

    response = TestClient(app).post(
        "/api/digest/prefetch",
        headers={"X-Stacktwin-Schedule-Token": "schedule-token"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "ValueError: source unavailable"
