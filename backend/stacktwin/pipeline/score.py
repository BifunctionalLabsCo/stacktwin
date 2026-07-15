import json
import os
from collections.abc import Callable

import httpx

from stacktwin.llm import model_for
from stacktwin.llm.structured import (
    chat_template_kwargs,
    json_response_format,
    parse_json_value,
    response_content,
)
from stacktwin.pipeline.sources.base import Article
from stacktwin.profile.schema import ArticleScore, DeveloperProfile

NEBIUS_API_URL = os.getenv("NEBIUS_API_URL", "https://api.studio.nebius.ai/v1")
NEBIUS_API_KEY = os.getenv("NEBIUS_TOKEN") or os.getenv("NEBIUS_API_KEY", "")
MODEL = model_for("map")


SCORING_BATCH_SIZE = int(os.getenv("SCORING_BATCH_SIZE", "4"))

SCORING_PROMPT = """
You are StackTwin's ranking editor. Rank a small batch of current learning
sources for one specific learner. Judge the supplied evidence, not the fame of
the topic. Compare items within the batch so generic or clickbait content does
not tie with material that directly advances the learner's stated goals.

Return one JSON object with exactly this shape:
{"items": [{
  "id": "a1",
  "relevance": float between 0 and 1,
  "novelty": float between 0 and 1,
  "practicality": float between 0 and 1,
  "difficulty": float between 0 and 1,
  "urgency": float between 0 and 1,
  "stack_match": float between 0 and 1,
  "learning_value": float between 0 and 1,
  "time_cost_minutes": integer estimated reading or watching time,
  "overall": float between 0 and 1,
  "why_this_matters": one sentence explaining why this matters for this specific developer,
  "recommended_action": one of ["read_now", "save_for_later", "skim", "skip"]
}]}

Scoring rules:
- relevance: direct match to explicit stack, domains, or learning goals
- novelty: likely new knowledge; use 0.5 when evidence is insufficient
- practicality: can the learner apply or test it during the coming week
- difficulty: 0 = very easy, 1 = very advanced relative to their level
- urgency: high only for genuinely time-sensitive releases, risks, or changes
- stack_match: exact technologies score higher than adjacent generic domains
- learning_value: durable skill or understanding gained from consuming the source
- overall: 30% relevance, 20% stack_match, 20% learning_value,
  15% practicality, 10% novelty, 5% urgency
- penalize vague motivation, sensational claims, duplicate themes, and sources
  whose title is stronger than the supplied summary
- if the source matches a topic to avoid, set overall <= 0.1 and action "skip"
- why_this_matters must name a learner goal, technology, role, or career direction
- time_cost_minutes must be realistic for the source type
- preserve every input id exactly and return one result per input
- JSON only: no prose, Markdown, comments, or additional keys
"""


def _build_profile_summary(profile: DeveloperProfile) -> str:
    return f"""
Name: {profile.name or "Developer"}
Role: {profile.current_role or "Software Engineer"}
Experience: {profile.experience_years or "?"} years ({profile.seniority or "mid"} level)
Current stack: {", ".join(profile.current_stack) or "not specified"}
Learning: {", ".join(profile.learning) or "not specified"}
Domains: {", ".join(profile.domains) or "not specified"}
Career direction: {profile.career_direction or "not specified"}
Learning goals: {", ".join(profile.learning_goals) or "not specified"}
Weekly time budget: {profile.weekly_time_budget_hours} hours
Topics to avoid: {", ".join(profile.topics_to_avoid) or "none"}
""".strip()


def _build_article_summary(article: Article) -> str:
    return f"""
Title: {article.title}
Source: {article.source}
URL: {article.url}
Summary: {article.summary or "no summary available"}
Tags: {", ".join(article.tags) or "none"}
Score/reactions: {article.score}
""".strip()


def _article_record(article: Article, index: int) -> dict:
    return {
        "id": f"a{index + 1}",
        "title": article.title,
        "source": article.source,
        "summary": (article.summary or "no summary available")[:900],
        "tags": article.tags[:8],
        "reactions": article.score,
    }


def _stub_score(article: Article) -> ArticleScore:
    """
    Fallback when API key is not set.
    Returns a neutral score so the pipeline does not break.
    Remove this once Nebius key is configured.
    """
    return ArticleScore(
        relevance=0.5,
        novelty=0.5,
        practicality=0.5,
        difficulty=0.3,
        urgency=0.0,
        stack_match=0.5,
        learning_value=0.5,
        time_cost_minutes=5,
        overall=0.5,
        why_this_matters="Scoring fallback used because the model response was unavailable.",
        recommended_action="save_for_later",
    )


def score_article(article: Article, profile: DeveloperProfile) -> ArticleScore:
    """
    Score a single article against a developer profile.
    Calls Nebius Endpoint and returns a structured ArticleScore.
    Falls back to stub score if API key is not configured.
    """
    if not NEBIUS_API_KEY:
        return _stub_score(article)

    return _score_batch([article], profile)[0]


def _score_batch(articles: list[Article], profile: DeveloperProfile) -> list[ArticleScore]:
    if not NEBIUS_API_KEY:
        return [_stub_score(article) for article in articles]

    records = [_article_record(article, index) for index, article in enumerate(articles)]
    payload = {
        "model": MODEL,
        "max_tokens": 1800,
        "temperature": 0.1,
        "response_format": json_response_format(),
        "chat_template_kwargs": chat_template_kwargs(),
        "messages": [
            {"role": "system", "content": SCORING_PROMPT},
            {
                "role": "user",
                "content": (
                    f"LEARNER PROFILE\n{_build_profile_summary(profile)}"
                    f"\n\nCANDIDATE BATCH\n{json.dumps(records, ensure_ascii=False)}"
                ),
            },
        ],
    }

    headers = {"Authorization": f"Bearer {NEBIUS_API_KEY}", "Content-Type": "application/json"}

    try:
        response = httpx.post(
            f"{NEBIUS_API_URL}/chat/completions", json=payload, headers=headers, timeout=30.0
        )
        response.raise_for_status()
        data = parse_json_value(response_content(response.json()))
        items = data.get("items", []) if isinstance(data, dict) else []
        by_id = {item.get("id"): item for item in items if isinstance(item, dict)}
        scores = []
        for index, article in enumerate(articles):
            item = by_id.get(f"a{index + 1}")
            if not item:
                scores.append(_stub_score(article))
                continue
            score_data = {key: value for key, value in item.items() if key != "id"}
            try:
                scores.append(ArticleScore(**score_data))
            except Exception as error:
                print(f"[score] invalid result for '{article.title[:50]}': {error}")
                scores.append(_stub_score(article))
        return scores

    except json.JSONDecodeError as e:
        print(f"[score] batch JSON parse failed: {e}")
    except httpx.HTTPStatusError as e:
        print(f"[score] batch API error {e.response.status_code}")
    except Exception as e:
        print(f"[score] batch failed: {e}")
    return [_stub_score(article) for article in articles]


def filter_by_tags(
    articles: list[Article],
    profile: DeveloperProfile,
    tag_index: dict[str, list[str]],
) -> list[Article]:
    """
    Filter articles to those matching the user's profile tags using the pre-built tag index.
    Falls back to all articles if profile has no tags or nothing matches.
    """
    user_tags: set[str] = set()
    for field in [
        profile.current_stack,
        profile.learning,
        profile.domains,
        profile.topics_to_track,
        profile.learning_goals,
    ]:
        for term in field:
            normalized = term.lower().strip().replace(" ", "-")
            user_tags.add(normalized)
            for word in term.lower().split():
                if len(word) > 2:
                    user_tags.add(word)

    if not user_tags or not tag_index:
        return articles

    matching_urls: set[str] = set()
    for user_tag in user_tags:
        if user_tag in tag_index:
            matching_urls.update(tag_index[user_tag])
        for index_tag, urls in tag_index.items():
            if user_tag in index_tag or index_tag in user_tag:
                matching_urls.update(urls)

    filtered = [a for a in articles if a.url in matching_urls]
    print(f"[score] tag filter: {len(filtered)}/{len(articles)} articles match profile tags")
    return filtered if filtered else articles


def score_articles(
    articles: list[Article],
    profile: DeveloperProfile,
    min_overall: float = 0.3,
    already_scored: list[tuple[Article, ArticleScore]] | None = None,
    on_scored: Callable[[Article, ArticleScore], None] | None = None,
) -> list[tuple[Article, ArticleScore]]:
    """
    Score all articles against a profile.
    Returns list of (article, score) tuples sorted by overall score descending.
    Filters out anything below min_overall threshold.

    already_scored: pre-loaded checkpoint from a prior attempt — these articles
        are included in the result without re-calling the LLM.
    on_scored: called after each newly scored article so the caller can persist
        a per-article checkpoint for resumability.
    """
    pre_scored: list[tuple[Article, ArticleScore]] = list(already_scored) if already_scored else []
    already_scored_urls: set[str] = {a.url for a, _ in pre_scored}

    articles_to_score = [a for a in articles if a.url not in already_scored_urls]
    if already_scored_urls:
        print(
            f"[score] resuming: {len(already_scored_urls)} already scored, "
            f"{len(articles_to_score)} remaining"
        )

    total = len(articles_to_score)
    newly_scored: list[tuple[Article, ArticleScore]] = []
    total_batches = -(-total // SCORING_BATCH_SIZE)
    for offset in range(0, total, SCORING_BATCH_SIZE):
        batch = articles_to_score[offset : offset + SCORING_BATCH_SIZE]
        print(f"[score] ranking batch {offset // SCORING_BATCH_SIZE + 1}/{total_batches}")
        batch_scores = _score_batch(batch, profile)
        for article, score in zip(batch, batch_scores, strict=True):
            newly_scored.append((article, score))
            if on_scored:
                on_scored(article, score)

    all_scored = pre_scored + newly_scored
    results = [(a, s) for a, s in all_scored if s.overall >= min_overall]
    results.sort(key=lambda x: x[1].overall, reverse=True)
    print(f"[score] {len(results)}/{len(all_scored)} articles passed threshold {min_overall}")
    return results
