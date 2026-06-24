import requests
from stacktwin.pipeline.sources.base import BaseSource, Article


DEVTO_API_URL = "https://dev.to/api/articles"


class DevToSource(BaseSource):

    def __init__(self):
        self._status = "ready"

    @property
    def name(self) -> str:
        return "Dev.to"

    @property
    def source_type(self) -> str:
        return "devto"

    @property
    def status(self) -> str:
        return self._status

    def fetch(self, limit: int = 50) -> list[Article]:
        try:
            response = requests.get(
                DEVTO_API_URL,
                params={"per_page": limit, "top": 7},
                timeout=10,
            )
            response.raise_for_status()
            items = response.json()

            articles = []
            skipped = 0
            for item in items:
                url = item.get("url", "")
                title = item.get("title", "")
                if not url or not title:
                    skipped += 1
                    continue
                articles.append(Article(
                    title=title,
                    url=url,
                    source=self.source_type,
                    summary=item.get("description", ""),
                    tags=item.get("tag_list", []),
                    published_at=item.get("published_at", ""),
                    score=item.get("positive_reactions_count", 0),
                ))

            if not articles:
                self._status = f"degraded:empty_response:skipped={skipped}"
            elif skipped:
                self._status = f"degraded:partial:fetched={len(articles)},skipped={skipped}"
            else:
                self._status = f"ok:api:{len(articles)}_articles"

            return articles

        except Exception as e:
            self._status = f"failed:{type(e).__name__}"
            print(f"[Dev.to] fetch failed: {e}")
            return []