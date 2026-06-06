import requests
from stacktwin.pipeline.sources.base import BaseSource, Article


DEVTO_API_URL = "https://dev.to/api/articles"


class DevToSource(BaseSource):

    @property
    def name(self) -> str:
        return "Dev.to"

    @property
    def source_type(self) -> str:
        return "devto"

    def fetch(self, limit: int = 50) -> list[Article]:
        try:
            response = requests.get(
                DEVTO_API_URL,
                params={
                    "per_page": limit,
                    "top": 7          # top articles from last 7 days
                },
                timeout=10
            )
            response.raise_for_status()
            items = response.json()

            articles = []
            for item in items:
                articles.append(Article(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    source=self.source_type,
                    summary=item.get("description", ""),
                    tags=item.get("tag_list", []),
                    published_at=item.get("published_at", ""),
                    score=item.get("positive_reactions_count", 0)
                ))

            return articles

        except Exception as e:
            print(f"[Dev.to] fetch failed: {e}")
            return []
