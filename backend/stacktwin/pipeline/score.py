import os
import json
import httpx
from stacktwin.pipeline.sources.base import Article
from stacktwin.profile.schema import DeveloperProfile, ArticleScore

NEBIUS_API_URL = os.getenv("NEBIUS_API_URL", "https://api.studio.nebius.com/v1")
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")
MODEL = os.getenv("NEBIUS_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct")


SCORING_PROMPT = """
You are a developer learning assistant.
Given a developer profile and an article, score how relevant and valuable
the article is for that specific developer.

Return ONLY a valid JSON object with these exact fields:
{
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
}

Scoring rules:
- relevance: how closely the article matches current stack or learning goals
- novelty: is this new information the developer likely has not seen
- practicality: can they apply this to their work this week
- difficulty: 0 = very easy, 1 = very advanced relative to their level
- urgency: does this need to be read soon (new release, breaking change)
- stack_match: how directly does this match their exact technologies
- learning_value: how much will this advance their stated learning goals
- overall: weighted summary — prioritise relevance, stack_match, learning_value
- why_this_matters: be specific, mention their actual stack
- Return JSON only. No explanation, no markdown, no code fences.
"""


def _build_profile_summary(profile: DeveloperProfile) -> str:
    return f"""
Name: {profile.name or 'Developer'}
Role: {profile.current_role or 'Software Engineer'}
Experience: {profile.experience_years or '?'} years ({profile.seniority or 'mid'} level)
Current stack: {', '.join(profile.current_stack) or 'not specified'}
Learning: {', '.join(profile.learning) or 'not specified'}
Domains: {', '.join(profile.domains) or 'not specified'}
Career direction: {profile.career_direction or 'not specified'}
Learning goals: {', '.join(profile.learning_goals) or 'not specified'}
Weekly time budget: {profile.weekly_time_budget_hours} hours
Topics to avoid: {', '.join(profile.topics_to_avoid) or 'none'}
""".strip()


def _build_article_summary(article: Article) -> str:
    # Hacker News provides no description — only title and upvote score.
    # Give the LLM explicit context so it scores based on title + community signal,
    # rather than penalizing the article for a missing summary.
    if article.source == "hackernews" and not article.summary:
        return f"""
Title: {article.title}
Source: Hacker News (community-curated tech discussion)
URL: {article.url}
Note: No article summary available from this source — score based on title
relevance and community signal. This article reached {article.score} upvotes,
indicating it was widely read and discussed by developers.
""".strip()

    return f"""
Title: {article.title}
Source: {article.source}
URL: {article.url}
Summary: {article.summary or 'no summary available'}
Tags: {', '.join(article.tags) or 'none'}
Score/reactions: {article.score}
""".strip()


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
        why_this_matters="Stub score — Nebius API key not set yet",
        recommended_action="save_for_later"
    )


def score_article(article: Article, profile: DeveloperProfile, user_id: str = "default") -> ArticleScore:
    """
    Score a single article against a developer profile.
    Calls Nebius Endpoint and returns a structured ArticleScore.
    Falls back to stub score if API key is not configured.

    Note: no per-article caching here — the digest idempotency check
    (storage.load_digest_by_week) already prevents redundant scoring
    for the same user and week. A per-article cache added complexity
    without real production value once the pipeline runs on a true
    weekly cadence — see NOTES.md.
    """
    if not NEBIUS_API_KEY:
        return _stub_score(article)

    payload = {
        "model": MODEL,
        "max_tokens": 500,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SCORING_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Developer profile:\n{_build_profile_summary(profile)}"
                    f"\n\nArticle:\n{_build_article_summary(article)}"
                )
            }
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
            timeout=30.0
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if model returns them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        return ArticleScore(**data)

    except json.JSONDecodeError as e:
        print(f"[score] JSON parse failed for '{article.title[:50]}': {e}")
        return _stub_score(article)
    except httpx.HTTPStatusError as e:
        print(f"[score] API error {e.response.status_code} for '{article.title[:50]}'")
        return _stub_score(article)
    except Exception as e:
        print(f"[score] failed for '{article.title[:50]}': {e}")
        return _stub_score(article)


def score_articles(
    articles: list[Article],
    profile: DeveloperProfile,
    min_overall: float = 0.3,
    user_id: str = "default"
) -> list[tuple[Article, ArticleScore]]:
    """
    Score all articles against a profile.
    Returns list of (article, score) tuples sorted by overall score descending.
    Filters out anything below min_overall threshold.
    """
    results = []
    total = len(articles)

    for i, article in enumerate(articles):
        print(f"[score] {i + 1}/{total} — {article.title[:50]}")
        score = score_article(article, profile, user_id=user_id)
        if score.overall >= min_overall:
            results.append((article, score))


    # Sort best first
    results.sort(key=lambda x: x[1].overall, reverse=True)
    print(f"[score] {len(results)}/{total} articles passed threshold {min_overall}")
    return results