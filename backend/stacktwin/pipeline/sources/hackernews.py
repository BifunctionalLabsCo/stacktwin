import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC
from stacktwin.pipeline.sources.base import BaseSource, Article


HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

# Bounded concurrency — enough to be fast, not enough to hammer HN's API
MAX_CONCURRENT_REQUESTS = 10


def _fetch_item(story_id: int, timeout: int = 10) -> dict | None:
    """Fetch a single HN item by ID. Returns None on any failure."""
    try:
        response = requests.get(HN_ITEM_URL.format(story_id), timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _normalize_hn_timestamp(unix_time) -> str:
    """
    Convert HN's Unix epoch integer to a timezone-aware ISO string.
    Returns empty string if conversion fails.
    """
    if not unix_time:
        return ""
    try:
        return datetime.fromtimestamp(int(unix_time), tz=UTC).isoformat()
    except (ValueError, TypeError, OSError):
        return ""


class HackerNewsSource(BaseSource):

    def __init__(self):
        self._status = "ready"

    @property
    def name(self) -> str:
        return "Hacker News"

    @property
    def source_type(self) -> str:
        return "hackernews"

    @property
    def status(self) -> str:
        """
        Returns source health status after fetch.
        Example: 'ok:fetched=45:skipped=3:failed=2'
        """
        return self._status

    def fetch(self, limit: int = 50) -> list[Article]:
        try:
            response = requests.get(HN_TOP_STORIES_URL, timeout=10)
            response.raise_for_status()
            story_ids = response.json()[:limit]
        except Exception as e:
            print(f"[HackerNews] failed to fetch story ID list: {e}")
            self._status = f"failed:{str(e)[:80]}"
            return []

        articles = []
        skipped = 0
        failed = 0

        # Bounded concurrent fetching — replaces sequential one-at-a-time calls
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            future_to_id = {
                executor.submit(_fetch_item, story_id): story_id
                for story_id in story_ids
            }

            for future in as_completed(future_to_id):
                item = future.result()

                if item is None:
                    failed += 1
                    continue

                item_type = item.get("type")

                # Ask HN / Show HN — text posts with no external URL.
                # Previously skipped entirely. Now mapped using their text body.
                if item_type == "story" and not item.get("url"):
                    title = item.get("title", "")
                    text = item.get("text", "")

                    if not title:
                        skipped += 1
                        continue

                    tag = "ask_hn" if title.lower().startswith("ask hn") else "show_hn"

                    articles.append(Article(
                        title=title,
                        url=f"https://news.ycombinator.com/item?id={item.get('id', '')}",
                        source=self.source_type,
                        summary=text[:500] if text else "",
                        tags=[tag, "discussion"],
                        published_at=_normalize_hn_timestamp(item.get("time")),
                        score=item.get("score", 0)
                    ))
                    continue

                # Regular linked story
                if item_type == "story" and item.get("url"):
                    articles.append(Article(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        source=self.source_type,
                        summary="",  # HN gives no description for linked stories
                        tags=["linked_story"],
                        published_at=_normalize_hn_timestamp(item.get("time")),
                        score=item.get("score", 0)
                    ))
                    continue

                # Jobs, polls, comments — not useful content for the digest
                skipped += 1

        self._status = f"ok:fetched={len(articles)}:skipped={skipped}:failed={failed}"
        return articles[:limit]