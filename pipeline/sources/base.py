from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    """
    Standard article shape across all sources.
    Every source returns a list of these — nothing else.
    """
    title: str
    url: str
    source: str                          # "hackernews", "arxiv", "devto"
    summary: str = ""                    # short description or abstract
    tags: list[str] = field(default_factory=list)
    published_at: str = ""               # ISO string when available
    score: int = 0                       # source-native score e.g. HN points
    fetched_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "summary": self.summary,
            "tags": self.tags,
            "published_at": self.published_at,
            "score": self.score,
            "fetched_at": self.fetched_at
        }


class BaseSource(ABC):
    """
    Every source must implement this contract.
    To add a new source: create a class, inherit BaseSource,
    implement name, source_type, and fetch().
    That's it — the pipeline picks it up automatically.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human readable name e.g. 'Hacker News'"""
        pass

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Short identifier e.g. 'hackernews'"""
        pass

    @abstractmethod
    def fetch(self, limit: int = 50) -> list[Article]:
        """
        Fetch articles from this source.
        Always returns a list of Article objects.
        Never raises — return empty list on failure.
        """
        pass

    def __repr__(self):
        return f"<Source: {self.name}>"