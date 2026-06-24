import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC

from stacktwin.pipeline.sources.base import BaseSource, Article


HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_ITEM_PAGE_URL = "https://news.ycombinator.com/item?id={}"
MAX_WORKERS = 10


def _unix_to_iso(unix_ts) -> str:
    """Convert a Unix timestamp to a timezone-aware ISO 8601 string."""
    if not unix_ts:
        return ""
    try:
        return datetime.fromtimestamp(int(unix_ts), tz=UTC).isoformat()
    except (ValueError, TypeError, OSError):
        return ""


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode common entities from HN item text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&gt;", ">")
            .replace("&lt;", "<")
            .replace("&amp;", "&")
            .replace("&#x27;", "'")
            .replace("&quot;", '"')
    )
    return " ".join(text.split())[:500]


def _item_tags(item: dict) -> list[str]:
    """Derive content tags from an HN item."""
    title = item.get("title", "").lower()
    item_type = item.get("type", "story")
    if title.startswith("ask hn"):
        return ["discussion"]
    if title.startswith("show hn"):
        return ["show"]
    if item_type == "job":
        return ["job"]
    return ["linked"]


def _fetch_item(story_id: int) -> dict | None:
    """Fetch a single HN item. Returns None on any failure."""
    try:
        response = requests.get(HN_ITEM_URL.format(story_id), timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


class HackerNewsSource(BaseSource):

    def __init__(self, max_workers: int = MAX_WORKERS):
        self.max_workers = max_workers
        self._status = "ready"

    @property
    def name(self) -> str:
        return "Hacker News"

    @property
    def source_type(self) -> str:
        return "hackernews"

    @property
    def status(self) -> str:
        return self._status

    def fetch(self, limit: int = 50) -> list[Article]:
        try:
            response = requests.get(HN_TOP_STORIES_URL, timeout=10)
            response.raise_for_status()
            story_ids = response.json()[:limit]
        except Exception as e:
            self._status = f"failed:{type(e).__name__}"
            print(f"[HackerNews] fetch failed: {e}")
            return []

        # Fetch items concurrently with a bounded worker pool
        items: list[dict | None] = [None] * len(story_ids)
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(_fetch_item, sid): i for i, sid in enumerate(story_ids)}
            for future in as_completed(futures):
                items[futures[future]] = future.result()

        articles = []
        skipped = 0
        failed = 0

        for item in items:
            if item is None:
                failed += 1
                continue

            title = item.get("title", "")
            item_type = item.get("type", "")

            if not title or item_type == "poll":
                skipped += 1
                continue

            url = item.get("url", "")
            if not url:
                url = HN_ITEM_PAGE_URL.format(item.get("id", ""))
                summary = _strip_html(item.get("text", ""))
            else:
                summary = ""

            articles.append(Article(
                title=title,
                url=url,
                source=self.source_type,
                summary=summary,
                tags=_item_tags(item),
                published_at=_unix_to_iso(item.get("time")),
                score=item.get("score", 0),
            ))

        self._status = f"ok:{len(articles)}_articles,{skipped}_skipped,{failed}_failed"
        return articles