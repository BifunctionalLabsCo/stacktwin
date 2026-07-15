import json
import os
from datetime import UTC, datetime

import httpx

from stacktwin.llm import model_for
from stacktwin.llm.structured import (
    chat_template_kwargs,
    json_response_format,
    parse_json_value,
    response_content,
)
from stacktwin.pipeline.sources.base import Article
from stacktwin.profile.schema import (
    ArticleScore,
    DeveloperProfile,
    DigestItem,
    WeeklyDigest,
)

NEBIUS_API_URL = os.getenv("NEBIUS_API_URL", "https://api.studio.nebius.ai/v1")
NEBIUS_API_KEY = os.getenv("NEBIUS_TOKEN") or os.getenv("NEBIUS_API_KEY", "")
MODEL = model_for("reduce")

DIGEST_SIZE = int(os.getenv("DIGEST_SIZE", "10"))  # articles in weekly digest
QUIZ_COUNT = int(os.getenv("QUIZ_COUNT", "3"))  # articles to generate quizzes for


SUMMARY_PROMPT = """
You are a developer learning assistant writing a weekly digest.
Given an article and a developer profile, write a tight 2-3 sentence
plain-English summary and a one-line "why this matters for you" specific
to this developer's stack and goals.

Return ONLY a valid JSON object:
{
  "summary": "2-3 sentence plain-English summary of the article",
  "why_this_matters": "one sentence specific to this developer's stack and goals",
  "estimated_reading_minutes": integer
}

Rules:
- Write for a working developer, not an academic
- Be specific about technologies when relevant
- No markdown, no code fences, JSON only
"""

QUIZ_PROMPT = """
You are a developer learning assistant.
Given an article summary, generate 3 multiple-choice quiz questions
to help a developer retain the key concepts.

Return ONLY a valid JSON object:
{"items": [
  {
    "question": "question text",
    "options": ["A) option", "B) option", "C) option", "D) option"],
    "correct": "A",
    "explanation": "one sentence explanation of why this is correct"
  }
]}

Rules:
- Questions should test practical understanding, not trivia
- One clearly correct answer per question
- No markdown, no code fences, JSON array only
"""


def _call_nebius(system_prompt: str, user_content: str) -> str | None:
    """
    Make a single call to the Nebius Endpoint.
    Returns raw response text or None on failure.
    """
    if not NEBIUS_API_KEY:
        return None

    payload = {
        "model": MODEL,
        "max_tokens": 800,
        "temperature": 0.2,
        "response_format": json_response_format(),
        "chat_template_kwargs": chat_template_kwargs(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }

    headers = {"Authorization": f"Bearer {NEBIUS_API_KEY}", "Content-Type": "application/json"}

    try:
        response = httpx.post(
            f"{NEBIUS_API_URL}/chat/completions", json=payload, headers=headers, timeout=30.0
        )
        response.raise_for_status()
        return response_content(response.json())
    except Exception as e:
        print(f"[digest] Nebius call failed: {e}")
        return None


def _parse_json(raw: str | None, fallback):
    """
    Parse JSON from LLM response.
    Strips markdown fences if present.
    Returns fallback on failure.
    """
    if not raw:
        return fallback
    return parse_json_value(raw) or fallback


def _generate_summary(article: Article, profile: DeveloperProfile) -> dict:
    """
    Generate a plain-English summary and why-it-matters for one article.
    Falls back to article's existing summary if no API key.
    """
    user_content = f"""
Developer stack: {", ".join(profile.current_stack)}
Developer learning: {", ".join(profile.learning)}
Career direction: {profile.career_direction or "not specified"}

Article title: {article.title}
Article summary: {article.summary or "no summary available"}
Article tags: {", ".join(article.tags)}
Article source: {article.source}
""".strip()

    raw = _call_nebius(SUMMARY_PROMPT, user_content)
    result = _parse_json(raw, fallback=None)

    if result:
        return result

    # Stub fallback
    return {
        "summary": article.summary or article.title,
        "why_this_matters": "Relevant to your current learning path",
        "estimated_reading_minutes": 5,
    }


def _generate_quiz(article: Article, summary: str) -> list[dict]:
    """
    Generate 3 quiz questions for one article.
    Returns empty list if no API key or on failure.
    """
    user_content = f"""
Article title: {article.title}
Article summary: {summary}
""".strip()

    raw = _call_nebius(QUIZ_PROMPT, user_content)
    result = _parse_json(raw, fallback={})
    return result.get("items", []) if isinstance(result, dict) else []


def build_digest(
    scored_articles: list[tuple[Article, ArticleScore]],
    profile: DeveloperProfile,
    top_n: int = DIGEST_SIZE,
    quiz_top_n: int = QUIZ_COUNT,
    week_start: str | None = None,
) -> WeeklyDigest:
    """
    Build the weekly digest from scored articles.

    Takes the top_n highest scored articles, generates summaries
    and why-it-matters for each, generates quizzes for the top
    quiz_top_n, and returns a WeeklyDigest.
    """
    # Take top N articles — already sorted by score descending
    top_articles = scored_articles[:top_n]
    total_processed = len(scored_articles)

    print(f"[digest] building digest from top {len(top_articles)} of {total_processed} articles")

    digest_items = []

    for i, (article, score) in enumerate(top_articles):
        print(f"[digest] {i + 1}/{len(top_articles)} — {article.title[:50]}")

        # Generate summary
        summary_data = _generate_summary(article, profile)

        # Generate quiz for top articles only
        quiz = []
        if i < quiz_top_n:
            print(f"[digest] generating quiz for: {article.title[:50]}")
            quiz = _generate_quiz(article, summary_data["summary"])

        digest_items.append(
            DigestItem(
                title=article.title,
                url=article.url,
                source=article.source,
                summary=summary_data["summary"],
                score=score,
                estimated_reading_minutes=summary_data.get("estimated_reading_minutes", 5),
                tags=article.tags,
                quiz=quiz if quiz else [],
            )
        )

    digest = WeeklyDigest(
        week_start=week_start or datetime.now(UTC).strftime("%Y-%m-%d"),
        profile_name=profile.name,
        items=digest_items,
        total_items_processed=total_processed,
        generated_at=datetime.now(UTC).isoformat(),
    )

    quiz_count = sum(1 for item in digest_items if item.quiz)
    print(f"[digest] done: {len(digest_items)} items, {quiz_count} with quizzes")
    return digest


def save_digest(digest: WeeklyDigest, output_dir: str = "outputs") -> str:
    """
    Save the weekly digest to a JSON file.
    Returns the file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"digest_{digest.week_start}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(digest.model_dump(), f, indent=2, ensure_ascii=False)

    print(f"[digest] saved to {filepath}")
    return filepath
