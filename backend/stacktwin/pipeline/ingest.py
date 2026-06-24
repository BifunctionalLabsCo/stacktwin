import json
import os
from datetime import datetime, UTC
from stacktwin.pipeline.sources.base import Article
from stacktwin.pipeline.sources.hackernews import HackerNewsSource
from stacktwin.pipeline.sources.arxiv import ArxivSource
from stacktwin.pipeline.sources.devto import DevToSource
from stacktwin.pipeline.sources.github_trending import GitHubTrendingSource
from stacktwin.pipeline.sources.youtube import YouTubeSource

# Registry: add new sources here, nothing else changes.
SOURCES = [
    HackerNewsSource(),
    ArxivSource(),
    DevToSource(),
    #GitHubTrendingSource(),
    YouTubeSource(),
]


def fetch_all(limit_per_source: int = 50) -> list[Article]:
    """
    Run all registered sources and return combined deduplicated list.
    """
    all_articles = []
    seen_urls = set()

    for source in SOURCES:
        print(f"[ingest] fetching from {source.name}...")
        try:
            articles = source.fetch(limit=limit_per_source)
            added = 0
            for article in articles:
                # Deduplicate by URL
                if article.url and article.url not in seen_urls:
                    seen_urls.add(article.url)
                    all_articles.append(article)
                    added += 1
            print(f"[ingest] {source.name}: {added} articles added")
        except Exception as e:
            print(f"[ingest] {source.name} failed: {e}")
            continue

    print(f"[ingest] total: {len(all_articles)} unique articles")
    return all_articles


def save_articles(articles: list[Article], output_dir: str = "outputs") -> str:
    """
    Save fetched articles to a JSON file.
    Returns the file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"articles_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            [a.to_dict() for a in articles],
            f,
            indent=2,
            ensure_ascii=False
        )

    print(f"[ingest] saved to {filepath}")
    return filepath


if __name__ == "__main__":
    articles = fetch_all(limit_per_source=30)
    path = save_articles(articles)
    print(f"\nDone. {len(articles)} articles saved to {path}")

def load_or_fetch(limit_per_source: int = 50, cache_dir: str = "outputs") -> list[Article]:
    """
    Load today's article cache if it exists, otherwise fetch fresh.
    
    This means:
    - First run of the day: fetches all sources, saves cache
    - Subsequent runs same day: loads cache, skips network calls
    - Next day: fetches fresh again
    
    Cache file pattern: outputs/articles_YYYYMMDD_*.json
    """
    today = datetime.now(UTC).strftime("%Y%m%d")
    
    # Check if today's cache exists
    if os.path.exists(cache_dir):
        today_files = sorted([
            f for f in os.listdir(cache_dir)
            if f.startswith(f"articles_{today}") and f.endswith(".json")
        ], reverse=True)
        
        if today_files:
            cache_path = os.path.join(cache_dir, today_files[0])
            print(f"[ingest] cache hit — loading {cache_path}")
            with open(cache_path, encoding="utf-8") as f:
                raw = json.load(f)
            # Convert dicts back to Article objects
            articles = [Article(**item) for item in raw]
            print(f"[ingest] loaded {len(articles)} articles from cache")
            return articles
    
    # No cache for today — fetch fresh
    print("[ingest] no cache for today — fetching fresh")
    articles = fetch_all(limit_per_source=limit_per_source)
    save_articles(articles, output_dir=cache_dir)
    return articles