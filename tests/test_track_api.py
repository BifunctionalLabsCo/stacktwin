from fastapi.testclient import TestClient

from stacktwin.api.main import app


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
