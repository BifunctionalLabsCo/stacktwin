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
        """
        Returns source health status after fetch.
        Example: 'ok:10_articles' or 'failed:error_detail'
        """
        return self._status

    def fetch(self, limit: int = 50) -> list[Article]:
        try:
            response = requests.get(
                DEVTO_API_URL,
                params={
                    "per_page": limit,
                    "top": 7
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

            if len(articles) < limit * 0.5:
                self._status = f"degraded:{len(articles)}_articles:undershoot"
            else:
                self._status = f"ok:{len(articles)}_articles"

            return articles

        except Exception as e:
            print(f"[Dev.to] fetch failed: {e}")
            self._status = f"failed:{str(e)[:80]}"
            return []