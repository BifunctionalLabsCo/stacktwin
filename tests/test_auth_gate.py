from fastapi.testclient import TestClient
from stacktwin.api.main import app
from stacktwin.api.routes import digest
from stacktwin.jobs.nebius import SubmittedJob


def _submitted_prefetch_job(owner_id):
    return SubmittedJob("job-test", "stacktwin-prefetch-test", "STARTING")


def _prefetch_failure(owner_id):
    raise OSError("source unavailable")


def test_schedule_token_prefetch_bypasses_browser_password_gate(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_PASSWORD", "shared-password")
    monkeypatch.setenv("STACKTWIN_SCHEDULE_TOKEN", "schedule-token")
    monkeypatch.setenv("STACKTWIN_APP_MODE", "local")
    monkeypatch.setattr(digest, "submit_weekly_content_prefetch_job", _submitted_prefetch_job)

    response = TestClient(app).post(
        "/api/digest/prefetch",
        headers={"X-Stacktwin-Schedule-Token": "schedule-token"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "submitted"


def test_local_prefetch_failures_return_a_sanitized_http_error(monkeypatch):
    monkeypatch.delenv("STACKTWIN_APP_PASSWORD", raising=False)
    monkeypatch.setenv("STACKTWIN_SCHEDULE_TOKEN", "schedule-token")
    monkeypatch.setenv("STACKTWIN_APP_MODE", "local")
    monkeypatch.setattr(digest, "submit_weekly_content_prefetch_job", _prefetch_failure)

    response = TestClient(app).post(
        "/api/digest/prefetch",
        headers={"X-Stacktwin-Schedule-Token": "schedule-token"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "OSError: source unavailable"
