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
DIGEST_BATCH_SIZE = int(os.getenv("DIGEST_BATCH_SIZE", "2"))


SUMMARY_PROMPT = """
You are StackTwin's digest editor. Turn a small batch of already-ranked source
records into concise, evidence-grounded learning briefs for one learner. The
ranking score tells you why each source was selected; the supplied source
excerpt is the boundary of what you may claim.

Return ONLY a valid JSON object:
{"items": [{
  "id": "a1",
  "summary": "2-3 sentences: core idea, useful detail, practical implication",
  "why_this_matters": "one learner-specific sentence",
  "estimated_reading_minutes": integer,
  "quiz": [{
    "question": "one applied comprehension question",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct": "A",
    "explanation": "one evidence-based sentence"
  }]
}]}

Rules:
- Preserve every input id and return exactly one item per input
- Explain the source, do not merely restate its title
- Connect why_this_matters to an explicit learner technology, goal, domain, or role
- Use the ranking rationale, but replace vague fallback language with a concrete connection
- Keep claims within the supplied title, excerpt, tags, and score rationale
- For video, estimate watch time from supplied ranking metadata; otherwise estimate reading time
- Return one quiz only when needs_quiz is true; otherwise return an empty quiz list
- Quiz questions must test application or tradeoffs, never title recall
- Use four plausible options and exactly one correct letter
- No markdown, code fences, preamble, or additional keys
"""


def _call_nebius(
    system_prompt: str, user_content: str, *, max_tokens: int = 2200
) -> str | None:
    """
    Make a single call to the Nebius Endpoint.
    Returns raw response text or None on failure.
    """
    if not NEBIUS_API_KEY:
        return None

    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.15,
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


def _profile_context(profile: DeveloperProfile) -> dict:
    return {
        "role": profile.current_role or "Software Engineer",
        "seniority": str(profile.seniority or "mid"),
        "current_stack": profile.current_stack,
        "learning": profile.learning,
        "domains": profile.domains,
        "career_direction": profile.career_direction,
        "learning_goals": profile.learning_goals,
        "topics_to_avoid": profile.topics_to_avoid,
        "weekly_time_budget_hours": profile.weekly_time_budget_hours,
    }


def _fallback_brief(article: Article, score: ArticleScore) -> dict:
    return {
        "summary": article.summary or article.title,
        "why_this_matters": score.why_this_matters,
        "estimated_reading_minutes": max(3, score.time_cost_minutes),
        "quiz": [],
    }


def _prepare_digest_batch(
    batch: list[tuple[Article, ArticleScore]],
    profile: DeveloperProfile,
    quiz_ids: set[str],
) -> list[dict]:
    records = []
    for index, (article, score) in enumerate(batch):
        record_id = f"a{index + 1}"
        records.append(
            {
                "id": record_id,
                "title": article.title,
                "source": article.source,
                "excerpt": (article.summary or "")[:1200],
                "tags": article.tags[:8],
                "ranking": score.model_dump(mode="json"),
                "needs_quiz": record_id in quiz_ids,
            }
        )

    raw = _call_nebius(
        SUMMARY_PROMPT,
        "LEARNER PROFILE\n"
        f"{json.dumps(_profile_context(profile), ensure_ascii=False)}\n\n"
        "RANKED SOURCE BATCH\n"
        f"{json.dumps(records, ensure_ascii=False)}",
    )
    result = _parse_json(raw, fallback={})
    items = result.get("items", []) if isinstance(result, dict) else []
    by_id = {item.get("id"): item for item in items if isinstance(item, dict)}

    prepared = []
    for index, (article, score) in enumerate(batch):
        item = by_id.get(f"a{index + 1}")
        if not item:
            prepared.append(_fallback_brief(article, score))
            continue
        try:
            prepared.append(
                {
                    "summary": str(item.get("summary") or article.summary or article.title),
                    "why_this_matters": str(
                        item.get("why_this_matters") or score.why_this_matters
                    ),
                    "estimated_reading_minutes": max(
                        3,
                        min(
                            120,
                            int(
                                item.get("estimated_reading_minutes")
                                or score.time_cost_minutes
                                or 5
                            ),
                        ),
                    ),
                    "quiz": (
                        item.get("quiz", []) if isinstance(item.get("quiz", []), list) else []
                    ),
                }
            )
        except (TypeError, ValueError) as error:
            print(f"[digest] invalid brief for '{article.title[:50]}': {error}")
            prepared.append(_fallback_brief(article, score))
    return prepared


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
    total_batches = -(-len(top_articles) // DIGEST_BATCH_SIZE)
    for offset in range(0, len(top_articles), DIGEST_BATCH_SIZE):
        batch = top_articles[offset : offset + DIGEST_BATCH_SIZE]
        quiz_ids = {
            f"a{index + 1}"
            for index in range(len(batch))
            if offset + index < quiz_top_n
        }
        print(f"[digest] preparing batch {offset // DIGEST_BATCH_SIZE + 1}/{total_batches}")
        briefs = _prepare_digest_batch(batch, profile, quiz_ids)
        for (article, score), brief in zip(batch, briefs, strict=True):
            personalized_score = score.model_copy(
                update={"why_this_matters": brief["why_this_matters"]}
            )
            digest_items.append(
                DigestItem(
                    title=article.title,
                    url=article.url,
                    source=article.source,
                    summary=brief["summary"],
                    score=personalized_score,
                    estimated_reading_minutes=brief["estimated_reading_minutes"],
                    tags=article.tags,
                    quiz=brief["quiz"],
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
