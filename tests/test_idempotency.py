from fastapi.testclient import TestClient
from stacktwin.api.main import app
from stacktwin.api.routes import digest as digest_routes
from stacktwin.api.routes import profile as profile_routes
from stacktwin.profile.schema import DeveloperProfile
from stacktwin.storage.json_storage import JSONStorage

from tests.test_storage import _digest

client = TestClient(app)


def test_identical_profile_upload_skips_extraction(monkeypatch, tmp_path):
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    monkeypatch.setattr(profile_routes, "get_storage", lambda: storage)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    content = (
        b"Experienced Python backend engineer working with FastAPI, distributed systems, "
        b"and retrieval augmented generation."
    )

    first = client.post(
        "/api/profile/upload?user_id=ada@example.com",
        files={"file": ("profile.txt", content, "text/plain")},
    )
    second = client.post(
        "/api/profile/upload?user_id=ada@example.com",
        files={"file": ("profile.txt", content, "text/plain")},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "computed"
    assert second.status_code == 200
    assert second.json()["status"] == "profile-cache-hit"
    assert second.json()["source_hash"] == first.json()["source_hash"]


def test_changed_profile_content_invalidates_hash(monkeypatch, tmp_path):
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    monkeypatch.setattr(profile_routes, "get_storage", lambda: storage)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    responses = []
    for suffix in (b"cloud systems", b"machine learning systems"):
        responses.append(
            client.post(
                "/api/profile/upload?user_id=ada@example.com",
                files={
                    "file": (
                        "profile.txt",
                        (
                            b"Experienced Python backend engineer with production experience in "
                            + suffix
                        ),
                        "text/plain",
                    )
                },
            )
        )

    assert [response.json()["status"] for response in responses] == ["computed", "computed"]
    assert responses[0].json()["source_hash"] != responses[1].json()["source_hash"]


def test_existing_weekly_digest_backfills_track_without_pipeline(monkeypatch, tmp_path):
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    storage.save_profile("ada@example.com", DeveloperProfile(name="Ada"))

    from datetime import UTC, datetime, timedelta

    today = datetime.now(UTC).date()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    storage.save_digest("ada@example.com", _digest(week_start))
    monkeypatch.setattr(digest_routes, "get_storage", lambda: storage)

    response = client.post("/api/digest/run?user_id=ada@example.com")
    repeated = client.post("/api/digest/run?user_id=ada@example.com")

    assert response.status_code == 200
    assert response.json()["status"] == "track-backfilled"
    assert response.json()["week_start"] == week_start
    assert storage.track_exists("ada@example.com", week_start)
    assert repeated.json()["status"] == "digest-already-exists"
