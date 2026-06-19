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
