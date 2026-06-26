import json
import os
import httpx
from datetime import datetime, timedelta, UTC
from stacktwin.pipeline.sources.base import Article
from stacktwin.pipeline.sources.hackernews import HackerNewsSource
from stacktwin.pipeline.sources.arxiv import ArxivSource
from stacktwin.pipeline.sources.devto import DevToSource
from stacktwin.pipeline.sources.github_trending import GitHubTrendingSource
from stacktwin.pipeline.sources.youtube import YouTubeSource


SOURCE_LIMIT = int(os.getenv("SOURCE_LIMIT", "50"))
NEBIUS_API_URL = os.getenv("NEBIUS_API_URL", "https://api.studio.nebius.ai/v1")
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")
MODEL = os.getenv("NEBIUS_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct")

TAG_INDEX_PROMPT = """
You are a content tagger for a developer learning platform.
Given a list of technical articles, assign 2-5 normalized topic tags to each.

Tags must be lowercase technology or domain names. Examples:
"python", "javascript", "rust", "machine-learning", "llm", "kubernetes", "devops",
"backend", "frontend", "security", "databases", "cloud", "distributed-systems",
"web-development", "infrastructure", "open-source", "career", "algorithms"

Return ONLY a valid JSON array:
[{"url": "...", "tags": ["tag1", "tag2", "tag3"]}, ...]

Rules:
- Use the exact article URL provided
- Prefer specific tech names ("fastapi", "pytorch") over generic ("framework", "library")
- For non-technical articles use domain tags ("career", "open-source", "tools")
- No markdown, no code fences, JSON array only
"""
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


def _call_nebius_for_tags(articles_batch: list[Article]) -> list[dict]:
    """Call Nebius LLM to tag a batch of articles. Returns list of {url, tags} dicts."""
    if not NEBIUS_API_KEY:
        return []

    article_list = "\n".join([
        f"{i+1}. URL: {a.url}\n   Title: {a.title}\n   Existing tags: {', '.join(a.tags) or 'none'}"
        for i, a in enumerate(articles_batch)
    ])

    payload = {
        "model": MODEL,
        "max_tokens": 2000,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": TAG_INDEX_PROMPT},
            {"role": "user", "content": f"Tag these articles:\n\n{article_list}"}
        ]
    }

    headers = {
        "Authorization": f"Bearer {NEBIUS_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = httpx.post(
            f"{NEBIUS_API_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        return result if isinstance(result, list) else []
    except Exception as e:
        print(f"[ingest] tag LLM call failed: {e}")
        return []


def build_tag_index(articles: list[Article]) -> dict[str, list[str]]:
    """
    Build a tag→URLs index for all articles using LLM-normalized tags.
    Falls back to existing article tags if no API key is set.

    Returns: {"python": ["url1", "url2"], "devops": ["url3"], ...}
    """
    if not NEBIUS_API_KEY:
        tag_index: dict[str, list[str]] = {}
        for article in articles:
            for tag in article.tags:
                normalized = tag.lower().strip()
                if normalized:
                    tag_index.setdefault(normalized, []).append(article.url)
        print(f"[ingest] tag index built from existing tags (no API key): {len(tag_index)} tags")
        return tag_index

    batch_size = 30
    all_tagged: list[dict] = []
    total_batches = -(-len(articles) // batch_size)  # ceiling division

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        print(f"[ingest] tagging batch {i // batch_size + 1}/{total_batches}...")
        tagged = _call_nebius_for_tags(batch)
        all_tagged.extend(tagged)

    url_to_tags = {item["url"]: item.get("tags", []) for item in all_tagged if "url" in item}

    # Fall back to existing tags for any article the LLM missed
    for article in articles:
        if article.url not in url_to_tags:
            url_to_tags[article.url] = [t.lower().strip() for t in article.tags if t.strip()]

    tag_index = {}
    for url, tags in url_to_tags.items():
        for tag in tags:
            if tag:
                tag_index.setdefault(tag, []).append(url)

    print(f"[ingest] tag index built: {len(tag_index)} unique tags across {len(articles)} articles")
    return tag_index


def load_or_build_tag_index(
    articles: list[Article], cache_dir: str = "outputs"
) -> dict[str, list[str]]:
    """
    Load this week's tag index if it exists, otherwise build it from articles.

    Cache file pattern: outputs/articles_YYYYMMDD_tags.json
    """
    today = datetime.now(UTC)
    week_monday = (today - timedelta(days=today.weekday())).strftime("%Y%m%d")
    tag_index_path = os.path.join(cache_dir, f"articles_{week_monday}_tags.json")

    if os.path.exists(tag_index_path):
        print(f"[ingest] tag index cache hit — loading {tag_index_path}")
        with open(tag_index_path, encoding="utf-8") as f:
            return json.load(f)

    print(f"[ingest] building tag index for week of {week_monday}...")
    tag_index = build_tag_index(articles)

    os.makedirs(cache_dir, exist_ok=True)
    with open(tag_index_path, "w", encoding="utf-8") as f:
        json.dump(tag_index, f, indent=2, ensure_ascii=False)
    print(f"[ingest] tag index saved to {tag_index_path}")
    return tag_index


if __name__ == "__main__":
    articles = fetch_all(limit_per_source=30)
    path = save_articles(articles)
    print(f"\nDone. {len(articles)} articles saved to {path}")


def load_or_fetch(limit_per_source: int = 50, cache_dir: str = "outputs") -> list[Article]:
    """
    Load this week's article cache if it exists, otherwise fetch fresh.

    Cache is keyed by Monday of the current week.
    This means:
    - First run on or after Monday with no existing cache: fetches fresh
    - All subsequent runs that week: loads the Monday cache
    - Following Monday: no cache exists yet, fetches fresh again

    Cache file pattern: outputs/articles_YYYYMMDD_*.json
    """
    today = datetime.now(UTC)
    week_monday = (today - timedelta(days=today.weekday())).strftime("%Y%m%d")

    if os.path.exists(cache_dir):
        week_files = sorted([
            f for f in os.listdir(cache_dir)
            if f.startswith(f"articles_{week_monday}") and f.endswith(".json")
        ], reverse=True)

        if week_files:
            cache_path = os.path.join(cache_dir, week_files[0])
            print(f"[ingest] cache hit — loading {cache_path}")
            with open(cache_path, encoding="utf-8") as f:
                raw = json.load(f)
            articles = [Article(**item) for item in raw]
            print(f"[ingest] loaded {len(articles)} articles from cache")
            return articles

    print(f"[ingest] no cache for week of {week_monday} — fetching fresh")
    articles = fetch_all(limit_per_source=limit_per_source)

    os.makedirs(cache_dir, exist_ok=True)
    filename = f"articles_{week_monday}_{datetime.now(UTC).strftime('%H%M%S')}.json"
    filepath = os.path.join(cache_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([a.to_dict() for a in articles], f, indent=2, ensure_ascii=False)
    print(f"[ingest] saved to {filepath}")
    return articles