import ssl
import urllib.request
import feedparser
from datetime import datetime
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


def _normalize_timestamp(raw: str) -> str:
    """
    Normalize arXiv published timestamp to ISO format.
    arXiv returns strings like 'Wed, 03 Jun 2026 00:00:00 -0400'.
    Returns ISO string or original string if parsing fails.
    """
    if not raw:
        return ""
    try:
        dt = datetime.strptime(raw.strip(), "%a, %d %b %Y %H:%M:%S %z")
        return dt.isoformat()
    except Exception:
        return raw.strip()


class ArxivSource(BaseSource):

    def __init__(self, categories: list[str] | None = None):
        """
        categories: override default ARXIV_CATEGORIES if provided.
        Example: ArxivSource(categories=["cs.AI", "cs.LG"])
        """
        self.categories = categories or ARXIV_CATEGORIES
        self._status = "ready"
        self._category_counts: dict[str, int] = {}

    @property
    def name(self) -> str:
        return "arXiv"

    @property
    def source_type(self) -> str:
        return "arxiv"

    @property
    def status(self) -> str:
        """
        Returns source health status after fetch.
        Example: 'ok:5_categories:30_articles'
        """
        return self._status

    def fetch(self, limit: int = 50) -> list[Article]:
        articles = []
        seen_urls = set()
        self._category_counts = {}

        # Distribute limit evenly across categories
        # Use ceiling division so we don't undershoot the limit
        per_category = -(-limit // len(self.categories))  # ceiling division

        failed_categories = []

        for category in self.categories:
            url = ARXIV_FEED_URL.format(category=category)
            entries = _fetch_feed(url)

            if not entries:
                failed_categories.append(category)
                self._category_counts[category] = 0
                continue

            count = 0
            for entry in entries[:per_category]:
                url_val = entry.get("link", "")

                # Deduplicate — same paper can appear in multiple categories
                if not url_val or url_val in seen_urls:
                    continue
                seen_urls.add(url_val)

                # Clean up title — arXiv titles sometimes have newlines
                title = entry.get("title", "").replace("\n", " ").strip()

                # Trim abstract — keep enough for scoring, not full text
                summary = entry.get("summary", "")
                # Strip the arXiv preamble "arXiv:XXXX Announce Type: new Abstract:"
                if "Abstract:" in summary:
                    summary = summary.split("Abstract:", 1)[-1].strip()
                summary = summary[:500]

                articles.append(Article(
                    title=title,
                    url=url_val,
                    source=self.source_type,
                    summary=summary,
                    tags=[category],
                    published_at=_normalize_timestamp(entry.get("published", "")),
                    score=0
                ))
                count += 1

            self._category_counts[category] = count

        # Build status string
        active = len(self.categories) - len(failed_categories)
        if failed_categories:
            self._status = (
                f"degraded:{active}/{len(self.categories)}_categories"
                f":{len(articles)}_articles"
                f":failed={','.join(failed_categories)}"
            )
        else:
            self._status = (
                f"ok:{active}_categories:{len(articles)}_articles"
            )

        return articles[:limit]