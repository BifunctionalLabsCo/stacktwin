import json
import os
from datetime import UTC, datetime, timedelta

import httpx

from stacktwin.llm import model_for
from stacktwin.llm.structured import (
    chat_template_kwargs,
    json_response_format,
    parse_json_value,
    response_content,
)
from stacktwin.pipeline.sources.arxiv import ArxivSource
from stacktwin.pipeline.sources.base import Article
from stacktwin.pipeline.sources.devto import DevToSource
from stacktwin.pipeline.sources.hackernews import HackerNewsSource
from stacktwin.pipeline.sources.youtube import YouTubeSource

SOURCE_LIMIT = int(os.getenv("SOURCE_LIMIT", "50"))
NEBIUS_API_URL = os.getenv("NEBIUS_API_URL", "https://api.studio.nebius.ai/v1")
NEBIUS_API_KEY = os.getenv("NEBIUS_TOKEN") or os.getenv("NEBIUS_API_KEY", "")
MODEL = model_for("map")

TAG_INDEX_PROMPT = """
You are StackTwin's content-normalization editor. Convert a compact batch of
fresh source metadata into a stable topic index used later for personalized
ranking. Use title, source, excerpt, and existing tags together; never infer a
technology from hype language alone.

Tags must be lowercase technology or domain names. Examples:
"python", "javascript", "rust", "machine-learning", "llm", "kubernetes", "devops",
"backend", "frontend", "security", "databases", "cloud", "distributed-systems",
"web-development", "infrastructure", "open-source", "career", "algorithms"

Return ONLY a valid JSON object:
{"items": [{"id": "a1", "tags": ["tag1", "tag2", "tag3"]}, ...]}

Rules:
- Preserve every input id exactly and return one result per input
- Prefer specific tech names ("fastapi", "pytorch") over generic ("framework", "library")
- Include one useful domain tag such as "frontend", "ai-research", or "devops"
- Use 3-5 unique tags, lowercase kebab-case, ordered specific to broad
- Treat existing tags as hints, not guaranteed truth
- For non-technical articles use domain tags ("career", "open-source", "tools")
- Do not invent version numbers, products, or claims absent from the input
- No markdown, no code fences, JSON object only
"""

# Registry: add new sources here, nothing else changes.
SOURCES = [
    HackerNewsSource(),
    ArxivSource(),
    DevToSource(),
    # GitHubTrendingSource(),
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
        json.dump([a.to_dict() for a in articles], f, indent=2, ensure_ascii=False)

    print(f"[ingest] saved to {filepath}")
    return filepath


def _call_nebius_for_tags(articles_batch: list[Article]) -> list[dict]:
    """Call Nebius LLM to tag a batch of articles. Returns list of {url, tags} dicts."""
    if not NEBIUS_API_KEY:
        return []

    records = [
        {
            "id": f"a{index + 1}",
            "title": article.title,
            "source": article.source,
            "excerpt": (article.summary or "")[:500],
            "existing_tags": article.tags[:8],
        }
        for index, article in enumerate(articles_batch)
    ]

    payload = {
        "model": MODEL,
        "max_tokens": 900,
        "temperature": 0.1,
        "response_format": json_response_format(),
        "chat_template_kwargs": chat_template_kwargs(),
        "messages": [
            {"role": "system", "content": TAG_INDEX_PROMPT},
            {
                "role": "user",
                "content": f"NORMALIZE THIS BATCH\n{json.dumps(records, ensure_ascii=False)}",
            },
        ],
    }

    headers = {"Authorization": f"Bearer {NEBIUS_API_KEY}", "Content-Type": "application/json"}

    try:
        response = httpx.post(
            f"{NEBIUS_API_URL}/chat/completions", json=payload, headers=headers, timeout=60.0
        )
        response.raise_for_status()
        result = parse_json_value(response_content(response.json()))
        items = result.get("items", []) if isinstance(result, dict) else []
        by_id = {item.get("id"): item for item in items if isinstance(item, dict)}
        return [
            {"url": article.url, "tags": by_id.get(f"a{index + 1}", {}).get("tags", [])}
            for index, article in enumerate(articles_batch)
        ]
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

    batch_size = int(os.getenv("TAGGING_BATCH_SIZE", "8"))
    all_tagged: list[dict] = []
    total_batches = -(-len(articles) // batch_size)  # ceiling division

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        print(f"[ingest] tagging batch {i // batch_size + 1}/{total_batches}...")
        tagged = _call_nebius_for_tags(batch)
        all_tagged.extend(tagged)

    url_to_tags = {
        item["url"]: item.get("tags", [])
        for item in all_tagged
        if item.get("url") and item.get("tags")
    }

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
    articles: list[Article],
    cache_dir: str = "outputs",
    storage=None,
    week_start: str | None = None,
    fallback_storage=None,
) -> dict[str, list[str]]:
    """
    Load this week's tag index if it exists, otherwise build it from articles.

    Cache file pattern: outputs/articles_YYYYMMDD_tags.json
    """
    if storage is not None:
        week = week_start or _week_start()
        snapshot = storage.load_content_snapshot(week)
        if snapshot and snapshot.get("tag_index") is not None:
            print(f"[ingest] shared tag index cache hit for week of {week}")
            return snapshot["tag_index"]
        if fallback_storage is not None:
            fallback = fallback_storage.load_content_snapshot(week)
            if fallback and fallback.get("tag_index") is not None:
                storage.save_content_snapshot(week, fallback["articles"], fallback["tag_index"])
                print(f"[ingest] restored shared tag index from cloud for week of {week}")
                return fallback["tag_index"]
        tag_index = build_tag_index(articles)
        storage.save_content_snapshot(week, [article.to_dict() for article in articles], tag_index)
        print(f"[ingest] shared tag index saved for week of {week}")
        return tag_index

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


def load_or_fetch(
    limit_per_source: int = 50,
    cache_dir: str = "outputs",
    storage=None,
    week_start: str | None = None,
    fallback_storage=None,
) -> list[Article]:
    """
    Load this week's article cache if it exists, otherwise fetch fresh.

    Cache is keyed by Monday of the current week.
    This means:
    - First run on or after Monday with no existing cache: fetches fresh
    - All subsequent runs that week: loads the Monday cache
    - Following Monday: no cache exists yet, fetches fresh again

    Cache file pattern: outputs/articles_YYYYMMDD_*.json
    """
    if storage is not None:
        week = week_start or _week_start()
        snapshot = storage.load_content_snapshot(week)
        if snapshot:
            print(f"[ingest] shared content cache hit for week of {week}")
            return [Article(**item) for item in snapshot["articles"]]
        if fallback_storage is not None:
            fallback = fallback_storage.load_content_snapshot(week)
            if fallback:
                storage.save_content_snapshot(
                    week, fallback["articles"], fallback.get("tag_index")
                )
                print(f"[ingest] restored shared content from cloud for week of {week}")
                return [Article(**item) for item in fallback["articles"]]
        articles = fetch_all(limit_per_source=limit_per_source)
        storage.save_content_snapshot(week, [article.to_dict() for article in articles], None)
        print(f"[ingest] shared content cache saved for week of {week}")
        return articles

    today = datetime.now(UTC)
    week_monday = (today - timedelta(days=today.weekday())).strftime("%Y%m%d")

    if os.path.exists(cache_dir):
        week_files = sorted(
            [
                f
                for f in os.listdir(cache_dir)
                if f.startswith(f"articles_{week_monday}")
                and f.endswith(".json")
                and "_tags" not in f
            ],
            reverse=True,
        )

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


def prefetch_weekly_content(
    storage,
    limit_per_source: int = SOURCE_LIMIT,
    owner_id: str | None = None,
    fallback_storage=None,
    week_start: str | None = None,
) -> dict[str, int | str]:
    """Fetch and tag the shared weekly source pool without scoring any learner profile."""
    week_start = week_start or _week_start()
    try:
        articles = load_or_fetch(
            limit_per_source=limit_per_source,
            storage=storage,
            week_start=week_start,
            fallback_storage=fallback_storage,
        )
        tag_index = load_or_build_tag_index(
            articles,
            storage=storage,
            week_start=week_start,
            fallback_storage=fallback_storage,
        )
        if owner_id:
            storage.complete_content_prefetch_lease(week_start, owner_id)
        return {"week_start": week_start, "articles": len(articles), "tags": len(tag_index)}
    except Exception as error:
        if owner_id:
            storage.fail_content_prefetch_lease(week_start, owner_id, str(error))
        raise


def _week_start() -> str:
    today = datetime.now(UTC).date()
    return (today - timedelta(days=today.weekday())).isoformat()
