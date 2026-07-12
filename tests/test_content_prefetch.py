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
