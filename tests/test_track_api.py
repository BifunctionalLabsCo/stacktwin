from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from stacktwin.api.main import app
from stacktwin.api.routes import track as track_routes
from stacktwin.learning.builder import build_weekly_track
from stacktwin.storage.json_storage import JSONStorage

from tests.test_storage import _digest, _profile

client = TestClient(app)


def test_track_preview_matches_frontend_contract():
    response = client.get("/api/track/preview")

    assert response.status_code == 200

    track = response.json()
    assert set(track) == {
        "id",
        "weekStart",
        "weekLabel",
        "generatedAt",
        "learnerFocus",
        "weeklyTimeBudgetMinutes",
        "modules",
    }
    assert 3 <= len(track["modules"]) <= 7

    module = track["modules"][0]
    assert set(module) == {
        "id",
        "title",
        "status",
        "difficulty",
        "estimatedMinutes",
        "personalizationReason",
        "sourceHints",
    }
    assert module["sourceHints"]


def test_health_endpoint_is_available_with_frontend_api():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_every_preview_module_has_lesson_content():
    track = client.get("/api/track/preview").json()

    for module in track["modules"]:
        response = client.get(f"/api/track/preview/{module['id']}")
        assert response.status_code == 200

        lesson = response.json()
        assert lesson["trackId"] == track["id"]
        assert lesson["contextBrief"]
        assert lesson["objectives"]
        assert lesson["keyConcepts"]
        assert lesson["exercise"]["instructions"]
        assert lesson["checkpoint"]["options"]
        assert lesson["takeaway"]
        assert lesson["availableActions"]


def test_unknown_preview_lesson_returns_not_found():
    response = client.get("/api/track/preview/not-a-module")

    assert response.status_code == 404


def test_track_history_exposes_week_summaries_and_detail(monkeypatch, tmp_path):
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    track = build_weekly_track(_digest(), _profile())
    storage.save_track("ada@example.com", track)
    monkeypatch.setattr(track_routes, "get_storage", lambda: storage)

    history = client.get("/api/track/history?user_id=ada@example.com")
    detail = client.get(f"/api/track/history/{track.week_start}?user_id=ada@example.com")

    assert history.status_code == 200
    assert history.json()["weeks"][0]["week_start"] == track.week_start
    assert detail.status_code == 200
    assert detail.json()["modules"][0]["id"] == track.modules[0].id


def test_current_track_requires_profile(monkeypatch, tmp_path):
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    monkeypatch.setattr(track_routes, "get_storage", lambda: storage)

    response = client.get("/api/track/current?user_id=missing@example.com")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "profile_required"


def test_current_track_distinguishes_missing_generation(monkeypatch, tmp_path):
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    storage.save_profile("ada@example.com", _profile())
    monkeypatch.setattr(track_routes, "get_storage", lambda: storage)

    response = client.get("/api/track/current?user_id=ada@example.com")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "track_not_ready"


def test_latest_track_returns_a_previous_week_when_current_week_is_missing(monkeypatch, tmp_path):
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    previous_week = (datetime.now(UTC).date() - timedelta(days=7)).isoformat()
    track = build_weekly_track(_digest(previous_week), _profile())
    storage.save_track("ada@example.com", track)
    monkeypatch.setattr(track_routes, "get_storage", lambda: storage)

    response = client.get("/api/track/latest?user_id=ada@example.com")

    assert response.status_code == 200
    assert response.json()["weekStart"] == previous_week


def test_current_track_and_lesson_use_persisted_content(monkeypatch, tmp_path):
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    profile = _profile()
    today = datetime.now(UTC).date()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    track = build_weekly_track(_digest(week_start), profile)
    storage.save_profile("ada@example.com", profile)
    storage.save_track("ada@example.com", track)
    monkeypatch.setattr(track_routes, "get_storage", lambda: storage)

    current = client.get("/api/track/current?user_id=ada@example.com")
    lesson = client.get(
        f"/api/track/{track.week_start}/modules/{track.modules[0].id}?user_id=ada@example.com"
    )
    other_user = client.get(
        f"/api/track/{track.week_start}/modules/{track.modules[0].id}?user_id=grace@example.com"
    )

    assert current.status_code == 200
    assert current.json()["id"] == track.id
    assert lesson.status_code == 200
    assert lesson.json()["contextBrief"] == track.modules[0].context_brief
    assert other_user.status_code == 404
