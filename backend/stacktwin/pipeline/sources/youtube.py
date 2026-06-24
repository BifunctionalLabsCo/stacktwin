import os
import ssl
import urllib.request
import feedparser
from stacktwin.pipeline.sources.base import BaseSource, Article
import re
import requests


# Curated developer YouTube channels
# Format: (channel_name, channel_id)
DEFAULT_CHANNELS = [
      ("Fireship", "UCsBjURrPoezykLs9EqgamOA"),
    ("Google for Developers", "UC_x5XG1OV2P6uZZ5FSM9Ttw"),
    ("Nick Chapsas", "UCrkPsvLGln62OMZRO6K-llg"),
    ("Traversy Media", "UC29ju8bIPH5as8OGnQzwJyA"),
    ("TechWorld with Nana", "UCdngmbVKX1Tgre699-XLlUA"),
    ("Theo - t3.gg", "UCbRP3c757lWg9M-U7TyEkXA"),
]

YOUTUBE_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/search"



def _fetch_channel_rss(channel_id: str, timeout: int = 10) -> list:
    try:
        url = YOUTUBE_RSS_URL.format(channel_id=channel_id)
        if os.getenv("YOUTUBE_SSL_VERIFY", "true").lower() != "true":
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        else:
            opener = urllib.request.build_opener()
        response = opener.open(url, timeout=timeout)
        raw = response.read()
        feed = feedparser.parse(raw)
        return feed.entries
    except Exception as e:
        print(f"[YouTube] RSS failed for channel {channel_id}: {e}")
        return []


class YouTubeSource(BaseSource):
    """
    YouTube source adapter.

    Fetch strategy:
    - If YOUTUBE_API_KEY is set in environment, uses YouTube Data API v3.
    - Otherwise falls back to RSS feeds per channel (no key required).
    - Missing credentials produce a skipped-source status, not a crash.

    Configuration via environment variables:
    - YOUTUBE_API_KEY: optional, enables API-based fetching
    - YOUTUBE_MAX_RESULTS: optional, results per query (default 10)
    """

    def __init__(self, channels: list[tuple[str, str]] | None = None):
        self.channels = channels or DEFAULT_CHANNELS
        self.api_key = os.getenv("YOUTUBE_API_KEY", "")
        self.max_results = int(os.getenv("YOUTUBE_MAX_RESULTS", "10"))
        self._status = "ready"

    @property
    def name(self) -> str:
        return "YouTube"

    @property
    def source_type(self) -> str:
        return "youtube"

    @property
    def status(self) -> str:
        """
        Returns source readiness status.
        Used by ingestion pipeline for status reporting.
        """
        return self._status

    def fetch(self, limit: int = 50) -> list[Article]:
        if self.api_key:
            return self._fetch_via_api(limit)
        return self._fetch_via_rss(limit)

    def _fetch_via_rss(self, limit: int) -> list[Article]:
        """Fetch using RSS — no API key required."""
        articles = []
        seen_urls = set()
        per_channel = max(1, limit // len(self.channels))
        channel_errors = 0

        for channel_name, channel_id in self.channels:
            entries = _fetch_channel_rss(channel_id)
            if not entries:
                channel_errors += 1

            count = 0
            for entry in entries:
                if count >= per_channel:
                    break
                video_url = entry.get("link", "")
                if not video_url or video_url in seen_urls:
                    continue
                seen_urls.add(video_url)
                summary = self._clean_description(entry.get("summary", ""))
                if not summary:
                    summary = f"Video by {channel_name}"
                articles.append(Article(
                    title=entry.get("title", ""),
                    url=video_url,
                    source=self.source_type,
                    summary=summary,
                    tags=[channel_name, "video"],
                    published_at=entry.get("published", ""),
                    score=0,
                ))
                count += 1

        if not articles:
            self._status = f"failed:rss:all_{len(self.channels)}_channels_failed"
        elif channel_errors:
            self._status = f"degraded:rss:{len(articles)}_articles,{channel_errors}_channels_failed"
        else:
            self._status = f"ok:rss:{len(articles)}_articles"
        return articles[:limit]

    def _fetch_via_api(self, limit: int) -> list[Article]:
        """
        Fetch using YouTube Data API v3.
        Requires YOUTUBE_API_KEY environment variable.
        """
        import requests

        articles = []
        seen_urls = set()
        channel_errors = 0

        for channel_name, channel_id in self.channels:
            try:
                response = requests.get(
                    YOUTUBE_API_URL,
                    params={
                        "part": "snippet",
                        "q": channel_name,
                        "type": "video",
                        "maxResults": self.max_results,
                        "order": "date",
                        "key": self.api_key,
                    },
                    timeout=10,
                )
                response.raise_for_status()
                items = response.json().get("items", [])

                for item in items:
                    video_id = item.get("id", {}).get("videoId", "")
                    if not video_id:
                        continue
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    if video_url in seen_urls:
                        continue
                    seen_urls.add(video_url)
                    snippet = item.get("snippet", {})
                    articles.append(Article(
                        title=snippet.get("title", ""),
                        url=video_url,
                        source=self.source_type,
                        summary=snippet.get("description", "")[:300],
                        tags=[snippet.get("channelTitle", ""), "video"],
                        published_at=snippet.get("publishedAt", ""),
                        score=0,
                    ))

            except Exception as e:
                print(f"[YouTube] API failed for channel '{channel_name}': {e}")
                channel_errors += 1
                continue

        if not articles and channel_errors:
            self._status = "failed:api:all_channels_failed"
        elif channel_errors:
            self._status = f"degraded:api:{len(articles)}_articles,{channel_errors}_channels_failed"
        else:
            self._status = f"ok:api:{len(articles)}_articles"
        return articles[:limit]

    def _clean_description(self, text: str) -> str:
        """
        Clean YouTube video description.
        Strip sponsor links, affiliate codes, URLs, and promotional text.
        Keep only the first meaningful sentence that describes the content.
        """
        if not text:
            return ""

        # Remove URLs
        text = re.sub(r'http\S+', '', text)

        # Remove lines that look like promotional content
        promo_patterns = [
            r'(?i)use code.*',
            r'(?i)promo.*',
            r'(?i)coupon.*',
            r'(?i)discount.*',
            r'(?i)affiliate.*',
            r'(?i)sponsor.*',
            r'(?i)check out.*',
            r'(?i)subscribe.*',
            r'(?i)follow.*on.*',
            r'(?i)get \$\d+.*',
            r'(?i)\d+% off.*',
        ]

        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(re.search(p, line) for p in promo_patterns):
                continue
            clean_lines.append(line)

        # Take first 2 clean lines — that's usually the actual description
        result = ' '.join(clean_lines[:2])
        return result[:300].strip()