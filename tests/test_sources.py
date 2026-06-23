"""
Smoke tests for all source adapters.
These make real network calls — run them to verify source health.
Not for CI (network dependent), but useful for local validation
and for demonstrating source readiness in the hackathon submission.

Run with:
    cd backend
    python -m pytest ../tests/test_sources.py -v
"""
import pytest
from stacktwin.pipeline.sources.base import Article
from stacktwin.pipeline.sources.hackernews import HackerNewsSource
from stacktwin.pipeline.sources.arxiv import ArxivSource
from stacktwin.pipeline.sources.devto import DevToSource
from stacktwin.pipeline.sources.github_trending import GitHubTrendingSource
from stacktwin.pipeline.sources.youtube import YouTubeSource


def assert_valid_articles(articles: list, source_name: str, min_count: int = 1):
    """Shared assertions for all sources."""
    assert len(articles) >= min_count, (
        f"{source_name}: expected at least {min_count} articles, got {len(articles)}"
    )
    for article in articles:
        assert isinstance(article, Article), f"{source_name}: result is not an Article"
        assert article.title, f"{source_name}: article has no title"
        assert article.url, f"{source_name}: article has no url"
        assert article.url.startswith("http"), f"{source_name}: url is not valid: {article.url}"
        assert article.source, f"{source_name}: article has no source"


class TestHackerNewsSource:
    def test_fetch_returns_articles(self):
        source = HackerNewsSource()
        articles = source.fetch(limit=10)
        assert_valid_articles(articles, "HackerNews", min_count=5)

    def test_articles_have_scores(self):
        source = HackerNewsSource()
        articles = source.fetch(limit=5)
        assert all(isinstance(a.score, int) for a in articles)

    def test_source_type(self):
        source = HackerNewsSource()
        articles = source.fetch(limit=3)
        assert all(a.source == "hackernews" for a in articles)


class TestArxivSource:
    def test_fetch_returns_articles(self):
        """
        arXiv should return at least some articles, but the exact count
        depends on arXiv's publishing schedule — they do not publish new
        papers on weekends (confirmed via the feed's own skipDays tag).
        We assert a low, realistic floor rather than a fixed high count,
        and rely on test_status_reflects_source_health below to verify
        the status reporting itself works correctly regardless of how
        many categories happen to have content right now.
        """
        source = ArxivSource()
        articles = source.fetch(limit=30)
        assert_valid_articles(articles, "arXiv", min_count=1)

    def test_multiple_categories_contribute_when_available(self):
        """
        When at least 2 of the configured categories have content
        (i.e. the source itself is not degraded below 2 active categories),
        confirm that articles from more than one category appear in the
        combined results. This is the real correctness guarantee — that
        the source properly merges across categories rather than only
        ever returning the first one.

        If fewer than 2 categories are active right now (e.g. weekend,
        arXiv publishing gap), this test is skipped rather than failed,
        since there's nothing meaningful to verify in that state.
        """
        source = ArxivSource(categories=["cs.AI", "cs.LG", "cs.SE"])
        articles = source.fetch(limit=30)

        active_categories = source.status.split(":")[1] if ":" in source.status else ""
        if active_categories.startswith("1/"):
            import pytest
            pytest.skip(
                f"Only 1 category active right now ({source.status}) — "
                "likely arXiv publishing gap (e.g. weekend). "
                "Nothing meaningful to test about multi-category merging "
                "when only one category has content."
            )

        sources_seen = set(a.tags[0] for a in articles if a.tags)
        assert len(sources_seen) > 1, (
            f"arXiv: expected results from multiple categories, got: {sources_seen}"
        )


    def test_status_reflects_source_health(self):
        """
        Regardless of how many categories actually have content right now,
        the status property must accurately report what happened — this is
        the real guarantee we can always test, independent of arXiv's
        publishing schedule.
        """
        source = ArxivSource(categories=["cs.AI", "cs.LG", "cs.SE"])
        articles = source.fetch(limit=30)

        assert source.status != "ready", "status must update after fetch"
        assert "articles" in source.status

        # Status must honestly reflect degraded state when categories fail
        if "degraded" in source.status:
            assert "failed=" in source.status, (
                "degraded status must name which categories failed"
            )
        else:
            assert source.status.startswith("ok:")

    def test_limit_respected(self):
        source = ArxivSource()
        articles = source.fetch(limit=30)
        assert len(articles) <= 30

    def test_status_reported(self):
        source = ArxivSource()
        source.fetch(limit=15)
        assert source.status != "ready"
        assert "articles" in source.status

    def test_timestamps_normalized(self):
        source = ArxivSource()
        articles = source.fetch(limit=5)
        for a in articles:
            if a.published_at:
                assert "T" in a.published_at or a.published_at == "", (
                    f"arXiv: timestamp not normalized: {a.published_at}"
                )

    def test_custom_categories(self):
        source = ArxivSource(categories=["cs.AI"])
        articles = source.fetch(limit=10)
        assert_valid_articles(articles, "arXiv custom", min_count=1)
        assert all("cs.AI" in a.tags for a in articles)


class TestDevToSource:
    def test_fetch_returns_articles(self):
        source = DevToSource()
        articles = source.fetch(limit=10)
        assert_valid_articles(articles, "DevTo", min_count=5)

    def test_articles_have_tags(self):
        source = DevToSource()
        articles = source.fetch(limit=5)
        assert any(len(a.tags) > 0 for a in articles)

    def test_source_type(self):
        source = DevToSource()
        articles = source.fetch(limit=3)
        assert all(a.source == "devto" for a in articles)

    def test_status_reported(self):
        source = DevToSource()
        source.fetch(limit=10)
        assert source.status != "ready"
        assert "articles" in source.status


class TestGitHubTrendingSource:
    def test_fetch_returns_articles(self):
        source = GitHubTrendingSource()
        articles = source.fetch(limit=10)
        assert_valid_articles(articles, "GitHubTrending", min_count=1)

    def test_articles_have_star_scores(self):
        source = GitHubTrendingSource()
        articles = source.fetch(limit=5)
        assert any(a.score > 0 for a in articles)

    def test_source_type(self):
        source = GitHubTrendingSource()
        articles = source.fetch(limit=3)
        assert all(a.source == "github_trending" for a in articles)


class TestYouTubeSource:
    def test_fetch_returns_articles_without_api_key(self):
        """Must work with no API key via RSS fallback."""
        source = YouTubeSource()
        articles = source.fetch(limit=6)
        assert_valid_articles(articles, "YouTube", min_count=1)

    def test_status_reported(self):
        source = YouTubeSource()
        source.fetch(limit=6)
        assert source.status != "ready"

    def test_missing_api_key_does_not_crash(self):
        """Missing credentials must produce empty result not exception."""
        import os
        os.environ.pop("YOUTUBE_API_KEY", None)
        source = YouTubeSource()
        try:
            articles = source.fetch(limit=5)
            assert isinstance(articles, list)
        except Exception as e:
            pytest.fail(f"YouTube source crashed without API key: {e}")

    def test_source_type(self):
        source = YouTubeSource()
        articles = source.fetch(limit=3)
        assert all(a.source == "youtube" for a in articles)