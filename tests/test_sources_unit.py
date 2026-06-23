"""
Deterministic unit tests — no network calls.
Mocks the HTTP layer to test parsing logic in isolation.
Fast, reliable, safe to run in CI.

For real network smoke tests, see test_sources.py instead.

Run with:
    cd backend
    python -m pytest ../tests/test_sources_unit.py -v
"""
from unittest.mock import patch, MagicMock
from stacktwin.pipeline.sources.devto import DevToSource
from stacktwin.pipeline.sources.hackernews import HackerNewsSource


class TestDevToSourceUnit:

    @patch("stacktwin.pipeline.sources.devto.requests.get")
    def test_fetch_parses_response_correctly(self, mock_get):
        # Fake what Dev.to's API would actually return
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "title": "Test Article",
                "url": "https://dev.to/test/article",
                "description": "A test description",
                "tag_list": ["python", "testing"],
                "published_at": "2026-06-19T00:00:00Z",
                "positive_reactions_count": 42
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        source = DevToSource()
        # Use limit=1 to match the single mocked article — this confirms
        # "ok" status when the requested count is actually met
        articles = source.fetch(limit=1)

        assert len(articles) == 1
        assert articles[0].title == "Test Article"
        assert articles[0].score == 42
        assert "python" in articles[0].tags
        assert source.status == "ok:1_articles"

    @patch("stacktwin.pipeline.sources.devto.requests.get")
    def test_fetch_handles_network_failure_gracefully(self, mock_get):
        mock_get.side_effect = Exception("connection refused")

        source = DevToSource()
        articles = source.fetch(limit=10)

        assert articles == []
        assert source.status.startswith("failed:")

    @patch("stacktwin.pipeline.sources.devto.requests.get")
    def test_status_reflects_undershoot(self, mock_get):
        # API returns fewer articles than requested
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"title": "Only One", "url": "https://dev.to/x", "description": "",
             "tag_list": [], "published_at": "", "positive_reactions_count": 1}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        source = DevToSource()
        articles = source.fetch(limit=20)

        assert "degraded" in source.status


class TestHackerNewsSourceUnit:

    @patch("stacktwin.pipeline.sources.hackernews.requests.get")
    def test_fetch_skips_non_story_items(self, mock_get):
        # Simulate: 1 story ID list call, then 2 item calls — one story, one job (skip)
        story_ids_response = MagicMock()
        story_ids_response.json.return_value = [111, 222]
        story_ids_response.raise_for_status.return_value = None

        story_item_response = MagicMock()
        story_item_response.json.return_value = {
            "type": "story",
            "title": "Real Story",
            "url": "https://example.com/story",
            "score": 100,
            "time": 1780000000
        }
        story_item_response.raise_for_status.return_value = None

        job_item_response = MagicMock()
        job_item_response.json.return_value = {
            "type": "job",  # should be skipped
            "title": "We're hiring",
        }
        job_item_response.raise_for_status.return_value = None

        # First call returns ID list, then alternates between item responses
        mock_get.side_effect = [story_ids_response, story_item_response, job_item_response]

        source = HackerNewsSource()
        articles = source.fetch(limit=2)

        assert len(articles) == 1
        assert articles[0].title == "Real Story"

    @patch("stacktwin.pipeline.sources.hackernews.requests.get")
    def test_fetch_handles_total_failure(self, mock_get):
        mock_get.side_effect = Exception("DNS resolution failed")

        source = HackerNewsSource()
        articles = source.fetch(limit=10)

        assert articles == []

    def test_timestamp_normalization(self):
        from stacktwin.pipeline.sources.hackernews import _normalize_hn_timestamp
        result = _normalize_hn_timestamp(1780000000)
        assert "T" in result
        assert result.endswith("+00:00")

    def test_timestamp_normalization_handles_invalid_input(self):
        from stacktwin.pipeline.sources.hackernews import _normalize_hn_timestamp
        assert _normalize_hn_timestamp(None) == ""
        assert _normalize_hn_timestamp("not_a_number") == ""

    @patch("stacktwin.pipeline.sources.hackernews._fetch_item")
    @patch("stacktwin.pipeline.sources.hackernews.requests.get")
    def test_ask_hn_text_post_mapped_to_summary(self, mock_get, mock_fetch_item):
        mock_ids_response = MagicMock()
        mock_ids_response.json.return_value = [123]
        mock_ids_response.raise_for_status.return_value = None
        mock_get.return_value = mock_ids_response

        mock_fetch_item.return_value = {
            "type": "story",
            "title": "Ask HN: What's your favorite tool?",
            "text": "I want to know what tools the community loves.",
            "score": 50,
            "time": 1780000000,
            "id": 123
            # deliberately no "url" — this is what makes it Ask HN
        }

        source = HackerNewsSource()
        articles = source.fetch(limit=1)

        assert len(articles) == 1
        assert "ask_hn" in articles[0].tags
        assert articles[0].summary == "I want to know what tools the community loves."

    @patch("stacktwin.pipeline.sources.hackernews._fetch_item")
    @patch("stacktwin.pipeline.sources.hackernews.requests.get")
    def test_concurrent_failure_does_not_crash_fetch(self, mock_get, mock_fetch_item):
        mock_ids_response = MagicMock()
        mock_ids_response.json.return_value = [1, 2, 3]
        mock_ids_response.raise_for_status.return_value = None
        mock_get.return_value = mock_ids_response

        # Simulate: item 1 fails (returns None), item 2 succeeds, item 3 fails
        mock_fetch_item.side_effect = [
            None,
            {"type": "story", "title": "Good Story", "url": "https://example.com",
             "score": 10, "time": 1780000000},
            None,
        ]

        source = HackerNewsSource()
        articles = source.fetch(limit=3)

        # Should get the 1 successful item, not crash on the 2 failures
        assert len(articles) == 1
        assert articles[0].title == "Good Story"
        assert "failed=2" in source.status