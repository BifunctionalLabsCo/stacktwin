import json
from datetime import UTC, datetime, timedelta

from stacktwin.pipeline import ingest
from stacktwin.pipeline.sources.base import Article
from stacktwin.storage.json_storage import JSONStorage


def test_prefetch_reuses_a_durable_weekly_content_snapshot(monkeypatch, tmp_path):
    storage = JSONStorage(str(tmp_path / "profiles"), str(tmp_path / "outputs"))
    articles = [Article(title="FastAPI", url="https://example.com/fastapi", source="devto")]
    fetches = []
    tags = []

    monkeypatch.setattr(
        ingest,
        "fetch_all",
        lambda limit_per_source: fetches.append(limit_per_source) or articles,
    )
    monkeypatch.setattr(
        ingest,
        "build_tag_index",
        lambda values: tags.append(values) or {"fastapi": [articles[0].url]},
    )

    first = ingest.prefetch_weekly_content(storage, limit_per_source=10)
    second = ingest.prefetch_weekly_content(storage, limit_per_source=10)

    assert first["articles"] == 1
    assert first["tags"] == 1
    assert second == first
    assert fetches == [10]
    assert tags == [articles]


def test_failed_prefetch_lease_can_be_reclaimed(tmp_path):
    storage = JSONStorage(str(tmp_path / "profiles"), str(tmp_path / "outputs"))

    assert storage.acquire_content_prefetch_lease("2026-07-13", "first-owner")
    storage.fail_content_prefetch_lease("2026-07-13", "first-owner", "job interrupted")

    assert storage.acquire_content_prefetch_lease("2026-07-13", "retry-owner")
    lease = storage.load_content_prefetch_lease("2026-07-13")
    assert lease["owner_id"] == "retry-owner"
    assert lease["status"] == "running"


def test_stale_prefetch_lease_can_be_reclaimed(tmp_path):
    storage = JSONStorage(str(tmp_path / "profiles"), str(tmp_path / "outputs"))
    week_start = "2026-07-13"
    stale_at = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with open(storage._content_lease_path(week_start), "w", encoding="utf-8") as lease_file:
        json.dump(
            {
                "owner_id": "crashed-owner",
                "status": "running",
                "started_at": stale_at,
                "updated_at": stale_at,
            },
            lease_file,
        )

    assert storage.acquire_content_prefetch_lease(week_start, "retry-owner")
    assert storage.load_content_prefetch_lease(week_start)["owner_id"] == "retry-owner"
