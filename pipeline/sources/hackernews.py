import requests
from pipeline.sources.base import BaseSource, Article


HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


class HackerNewsSource(BaseSource):

    @property
    def name(self) -> str:
        return "Hacker News"

    @property
    def source_type(self) -> str:
        return "hackernews"

    def fetch(self, limit: int = 50) -> list[Article]:
        try:
            # Step 1 — get top story IDs
            response = requests.get(HN_TOP_STORIES_URL, timeout=10)
            response.raise_for_status()
            story_ids = response.json()[:limit]

            articles = []

            # Step 2 — fetch each story
            for story_id in story_ids:
                try:
                    item_response = requests.get(
                        HN_ITEM_URL.format(story_id),
                        timeout=10
                    )
                    item_response.raise_for_status()
                    item = item_response.json()

                    # Skip non-stories (jobs, polls etc)
                    if not item or item.get("type") != "story":
                        continue

                    # Skip stories with no URL (Ask HN, Show HN text posts)
                    if not item.get("url"):
                        continue

                    articles.append(Article(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        source=self.source_type,
                        summary="",  # HN has no summary — LLM will generate later
                        tags=[],
                        published_at=str(item.get("time", "")),
                        score=item.get("score", 0)
                    ))

                except Exception:
                    # Skip any single failing item — never crash the whole fetch
                    continue

            return articles

        except Exception as e:
            print(f"[HackerNews] fetch failed: {e}")
            return []