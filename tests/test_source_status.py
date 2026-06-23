"""
Deterministic status tests for Dev.to and YouTube source adapters.
All network calls are mocked — no live network access required.
"""
from unittest.mock import MagicMock, patch

from stacktwin.pipeline.sources.devto import DevToSource
from stacktwin.pipeline.sources.youtube import YouTubeSource


# ── Dev.to ────────────────────────────────────────────────────────────────────

def _devto_item(title="Test Article", url="https://dev.to/test"):
    return {
        "title": title,
        "url": url,
        "description": "A short description.",
        "tag_list": ["python"],
        "published_at": "2026-06-15T10:00:00Z",
        "positive_reactions_count": 42,
    }


def test_devto_status_ok_on_success():
    source = DevToSource()
    mock_response = MagicMock()
    mock_response.json.return_value = [_devto_item(), _devto_item(title="B", url="https://dev.to/b")]

    with patch("stacktwin.pipeline.sources.devto.requests.get", return_value=mock_response):
        articles = source.fetch(limit=10)

    assert len(articles) == 2
    assert source.status.startswith("ok:api:")
    assert "2_articles" in source.status


def test_devto_status_failed_on_network_error():
    source = DevToSource()

    with patch("stacktwin.pipeline.sources.devto.requests.get", side_effect=ConnectionError("timeout")):
        articles = source.fetch(limit=10)

    assert articles == []
    assert source.status.startswith("failed:")


def test_devto_status_degraded_on_empty_response():
    source = DevToSource()
    mock_response = MagicMock()
    mock_response.json.return_value = []

    with patch("stacktwin.pipeline.sources.devto.requests.get", return_value=mock_response):
        articles = source.fetch(limit=10)

    assert articles == []
    assert "degraded" in source.status


def test_devto_status_degraded_on_partial_skip():
    source = DevToSource()
    mock_response = MagicMock()
    mock_response.json.return_value = [
        _devto_item(),
        {"title": "", "url": "", "description": "", "tag_list": [], "published_at": "", "positive_reactions_count": 0},
    ]

    with patch("stacktwin.pipeline.sources.devto.requests.get", return_value=mock_response):
        articles = source.fetch(limit=10)

    assert len(articles) == 1
    assert "degraded" in source.status


# ── YouTube ───────────────────────────────────────────────────────────────────

TWO_CHANNELS = [("ChannelA", "UC_AAA"), ("ChannelB", "UC_BBB")]


def _rss_entry(title="Test Video", url="https://www.youtube.com/watch?v=abc123"):
    return {"title": title, "link": url, "summary": "A technical video.", "published": "2026-06-15T10:00:00Z"}


def test_youtube_rss_status_ok_all_channels_succeed():
    source = YouTubeSource(channels=TWO_CHANNELS)

    with patch("stacktwin.pipeline.sources.youtube._fetch_channel_rss", return_value=[_rss_entry()]):
        source.fetch(limit=10)

    assert source.status.startswith("ok:rss:")


def test_youtube_rss_status_degraded_when_one_channel_fails():
    source = YouTubeSource(channels=TWO_CHANNELS)

    def side_effect(channel_id, **kwargs):
        return [] if channel_id == "UC_AAA" else [_rss_entry()]

    with patch("stacktwin.pipeline.sources.youtube._fetch_channel_rss", side_effect=side_effect):
        articles = source.fetch(limit=10)

    assert len(articles) > 0
    assert "degraded" in source.status
    assert "1_channels_failed" in source.status


def test_youtube_rss_status_failed_when_all_channels_fail():
    source = YouTubeSource(channels=TWO_CHANNELS)

    with patch("stacktwin.pipeline.sources.youtube._fetch_channel_rss", return_value=[]):
        articles = source.fetch(limit=10)

    assert articles == []
    assert source.status.startswith("failed:")


def test_youtube_api_status_degraded_not_overwritten_by_later_success():
    """Earlier channel failure must not be hidden by a later successful channel."""
    source = YouTubeSource(channels=TWO_CHANNELS)
    source.api_key = "fake-key"

    good_response = MagicMock()
    good_response.json.return_value = {
        "items": [{"id": {"videoId": "vid1"}, "snippet": {
            "title": "T", "description": "D", "channelTitle": "ChannelB", "publishedAt": ""
        }}]
    }

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("channel A failed")
        return good_response

    with patch("stacktwin.pipeline.sources.youtube.requests.get", side_effect=side_effect):
        articles = source.fetch(limit=10)

    assert len(articles) > 0
    assert "degraded" in source.status
    assert "1_channels_failed" in source.status


def test_youtube_api_status_ok_when_all_channels_succeed():
    source = YouTubeSource(channels=TWO_CHANNELS)
    source.api_key = "fake-key"

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [{"id": {"videoId": "vid1"}, "snippet": {
            "title": "T", "description": "D", "channelTitle": "C", "publishedAt": ""
        }}]
    }

    with patch("stacktwin.pipeline.sources.youtube.requests.get", return_value=mock_response):
        articles = source.fetch(limit=10)

    assert len(articles) > 0
    assert source.status.startswith("ok:api:")