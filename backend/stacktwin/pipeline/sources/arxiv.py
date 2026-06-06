import ssl
import urllib.request
import feedparser
from stacktwin.pipeline.sources.base import BaseSource, Article


ARXIV_FEEDS = {
    "cs.AI": "https://rss.arxiv.org/rss/cs.AI",
    "cs.LG": "https://rss.arxiv.org/rss/cs.LG",
    "cs.SE": "https://rss.arxiv.org/rss/cs.SE",
}

# Fix SSL on Windows
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


class ArxivSource(BaseSource):

    @property
    def name(self) -> str:
        return "arXiv"

    @property
    def source_type(self) -> str:
        return "arxiv"

    def fetch(self, limit: int = 50) -> list[Article]:
        articles = []
        per_feed = max(1, limit // len(ARXIV_FEEDS))

        for category, feed_url in ARXIV_FEEDS.items():
            try:
                # Fetch raw feed content manually with SSL bypass
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ssl_context)
                )
                response = opener.open(feed_url, timeout=10)
                raw = response.read()

                feed = feedparser.parse(raw)

                for entry in feed.entries[:per_feed]:
                    articles.append(Article(
                        title=entry.get("title", "").replace("\n", " ").strip(),
                        url=entry.get("link", ""),
                        source=self.source_type,
                        summary=entry.get("summary", "")[:300],
                        tags=[category],
                        published_at=entry.get("published", ""),
                        score=0
                    ))

            except Exception as e:
                print(f"[arXiv] failed for {category}: {e}")
                continue

        return articles[:limit]
