from fastapi.testclient import TestClient
from stacktwin.api.main import app
from stacktwin.api.routes import track as track_routes
from stacktwin.storage.json_storage import JSONStorage

from tests.test_storage import _digest

client = TestClient(app)


def test_track_preview_matches_frontend_contract():
    response = client.get("/api/track/preview")

    assert response.status_code == 200

    track = response.json()
    assert set(track) == {
        "id",
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
    digest = _digest()
    storage.save_digest("ada@example.com", digest)
    monkeypatch.setattr(track_routes, "get_storage", lambda: storage)

    history = client.get("/api/track/history?user_id=ada@example.com")
    detail = client.get(f"/api/track/history/{digest.week_start}?user_id=ada@example.com")

    assert history.status_code == 200
    assert history.json()["weeks"][0]["week_start"] == digest.week_start
    assert detail.status_code == 200
    assert detail.json()["items"][0]["url"] == digest.items[0].url
