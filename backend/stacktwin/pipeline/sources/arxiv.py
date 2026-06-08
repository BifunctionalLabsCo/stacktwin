import ssl
import urllib.request
import feedparser
from stacktwin.pipeline.sources.base import BaseSource, Article


# Configurable — add or remove categories here
# Full list at https://arxiv.org/category_taxonomy
ARXIV_CATEGORIES = [
    "cs.AI",   # Artificial Intelligence
    "cs.LG",   # Machine Learning
    "cs.SE",   # Software Engineering
    "cs.DC",   # Distributed Computing
    "cs.DB",   # Databases
]

ARXIV_FEED_URL = "https://rss.arxiv.org/rss/{category}"

# SSL context — fixes certificate verification on Windows
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def _fetch_feed(url: str, timeout: int = 10) -> list:
    """
    Fetch and parse an RSS feed with SSL bypass.
    Returns list of feed entries or empty list on failure.
    """
    try:
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=_SSL_CONTEXT)
        )
        response = opener.open(url, timeout=timeout)
        raw = response.read()
        feed = feedparser.parse(raw)
        return feed.entries
    except Exception as e:
        print(f"[arXiv] failed to fetch {url}: {e}")
        return []


class ArxivSource(BaseSource):

    def __init__(self, categories: list[str] | None = None):
        """
        categories: override default ARXIV_CATEGORIES if provided.
        Example: ArxivSource(categories=["cs.AI", "cs.LG"])
        """
        self.categories = categories or ARXIV_CATEGORIES

    @property
    def name(self) -> str:
        return "arXiv"

    @property
    def source_type(self) -> str:
        return "arxiv"

    def fetch(self, limit: int = 50) -> list[Article]:
        articles = []
        seen_urls = set()
        per_category = max(1, limit // len(self.categories))

        for category in self.categories:
            url = ARXIV_FEED_URL.format(category=category)
            entries = _fetch_feed(url)

            for entry in entries[:per_category]:
                url_val = entry.get("link", "")

                # Deduplicate within arXiv (same paper in multiple categories)
                if url_val in seen_urls:
                    continue
                seen_urls.add(url_val)

                articles.append(Article(
                    title=entry.get("title", "").replace("\n", " ").strip(),
                    url=url_val,
                    source=self.source_type,
                    summary=entry.get("summary", "")[:500],
                    tags=[category],
                    published_at=entry.get("published", ""),
                    score=0
                ))

        return articles[:limit]