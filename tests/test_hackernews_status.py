"""
Deterministic tests for HackerNews source improvements.
All network calls are mocked — no live network access required.
"""
from unittest.mock import patch

from stacktwin.pipeline.sources.hackernews import (
    HackerNewsSource,
    _item_tags,
    _strip_html,
    _unix_to_iso,
)


# ── Pure function tests ───────────────────────────────────────────────────────

def test_unix_to_iso_known_value():
    result = _unix_to_iso(1718448000)
    assert result.startswith("2024-06-15T")
    assert result.endswith("+00:00")


def test_unix_to_iso_none_returns_empty():
    assert _unix_to_iso(None) == ""


def test_unix_to_iso_empty_string_returns_empty():
    assert _unix_to_iso("") == ""


def test_unix_to_iso_result_is_iso_format():
    result = _unix_to_iso(1718448000)
    assert "T" in result
    assert "+" in result or result.endswith("Z")


def test_strip_html_removes_tags():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_decodes_entities():
    assert "&amp;" not in _strip_html("A &amp; B")
    assert "&gt;" not in _strip_html("x &gt; y")


def test_strip_html_empty_returns_empty():
    assert _strip_html("") == ""
    assert _strip_html(None) == ""


def test_item_tags_ask_hn():
    assert _item_tags({"title": "Ask HN: Best distributed systems tools?", "type": "story"}) == ["discussion"]


def test_item_tags_show_hn():
    assert _item_tags({"title": "Show HN: My new open source tool", "type": "story"}) == ["show"]


def test_item_tags_job():
    assert _item_tags({"title": "Backend Engineer at Startup", "type": "job"}) == ["job"]


def test_item_tags_linked_story():
    assert _item_tags({"title": "Why Rust is fast", "type": "story"}) == ["linked"]


# ── Fetch behavior tests ──────────────────────────────────────────────────────

def _linked_item(story_id=1):
    return {
        "id": story_id,
        "type": "story",
        "title": f"Story {story_id}",
        "url": f"https://example.com/{story_id}",
        "time": 1718448000,
        "score": 50,
    }


def _ask_hn_item(story_id=10):
    return {
        "id": story_id,
        "type": "story",
        "title": "Ask HN: What are you working on?",
        "text": "Share what <b>you</b> are building this week.",
        "time": 1718448000,
        "score": 200,
    }


def test_ask_hn_text_post_uses_hn_url_and_stripped_summary():
    source = HackerNewsSource()

    with patch("stacktwin.pipeline.sources.hackernews.requests.get") as mock_get:
        mock_get.return_value.json.return_value = [10]
        with patch("stacktwin.pipeline.sources.hackernews._fetch_item", return_value=_ask_hn_item()):
            articles = source.fetch(limit=1)

    assert len(articles) == 1
    assert "news.ycombinator.com" in articles[0].url
    assert "you" in articles[0].summary  # HTML stripped, text preserved
    assert articles[0].tags == ["discussion"]


def test_published_at_is_iso_not_unix_integer():
    source = HackerNewsSource()

    with patch("stacktwin.pipeline.sources.hackernews.requests.get") as mock_get:
        mock_get.return_value.json.return_value = [1]
        with patch("stacktwin.pipeline.sources.hackernews._fetch_item", return_value=_linked_item()):
            articles = source.fetch(limit=1)

    assert "T" in articles[0].published_at
    assert articles[0].published_at != "1718448000"


def test_concurrent_item_failure_does_not_crash():
    source = HackerNewsSource()

    def fetch_side_effect(story_id):
        return None if story_id == 2 else _linked_item(story_id)

    with patch("stacktwin.pipeline.sources.hackernews.requests.get") as mock_get:
        mock_get.return_value.json.return_value = [1, 2, 3]
        with patch("stacktwin.pipeline.sources.hackernews._fetch_item", side_effect=fetch_side_effect):
            articles = source.fetch(limit=3)

    assert len(articles) == 2
    assert "1_failed" in source.status


def test_status_reports_all_counts():
    source = HackerNewsSource()

    with patch("stacktwin.pipeline.sources.hackernews.requests.get") as mock_get:
        mock_get.return_value.json.return_value = [1, 2]
        with patch("stacktwin.pipeline.sources.hackernews._fetch_item", side_effect=[_linked_item(1), _linked_item(2)]):
            articles = source.fetch(limit=2)

    assert len(articles) == 2
    assert source.status.startswith("ok:")
    assert "_articles" in source.status
    assert "_skipped" in source.status
    assert "_failed" in source.status


def test_top_stories_failure_returns_empty_and_failed_status():
    source = HackerNewsSource()

    with patch("stacktwin.pipeline.sources.hackernews.requests.get", side_effect=ConnectionError("down")):
        articles = source.fetch(limit=10)

    assert articles == []
    assert source.status.startswith("failed:")