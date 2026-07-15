import hashlib
import json
import os
import re
from datetime import date

import httpx

from stacktwin.learning.schema import Checkpoint, Exercise, LearningModule, WeeklyTrack
from stacktwin.llm import model_for
from stacktwin.llm.structured import (
    chat_template_kwargs,
    json_response_format,
    parse_json_value,
    response_content,
)
from stacktwin.profile.schema import DeveloperProfile, DigestItem, WeeklyDigest

MODEL = model_for("reduce")
TRACK_BATCH_SIZE = int(os.getenv("TRACK_BATCH_SIZE", "2"))

TRACK_MODULE_PROMPT = """
You are StackTwin's lesson architect. Expand a small batch of ranked, summarized
sources into self-contained micro-lessons for one learner. Each lesson must
teach the source's actual idea, connect it to the learner's stated direction,
and end with a bounded action. Use the weekly track context to avoid repeating
the same objective or exercise across modules.

Return only this JSON object:
{"items": [{
  "id": "a1",
  "difficulty": "Focused | Intermediate | Advanced",
  "estimated_minutes": 15,
  "personalization_reason": "one specific learner connection",
  "context_brief": "3-5 sentences that teach the core idea and its tradeoff",
  "objectives": ["observable objective 1", "objective 2", "objective 3"],
  "key_concepts": ["concept: concise explanation", "...", "..."],
  "exercise": {"title": "...", "instructions": "a concrete 15-30 minute task with an output"},
  "checkpoint": {
    "question": "applied multiple-choice question",
    "options": ["...", "...", "...", "..."],
    "answer_index": 0,
    "explanation": "why this option follows from the source"
  },
  "takeaway": "one memorable, actionable sentence"
}]}

Quality rules:
- Preserve every input id and return one lesson per input
- Ground every claim in the supplied source summary and ranking evidence
- Teach before asking the learner to act; do not use generic productivity advice
- Objectives must use verbs such as explain, compare, implement, evaluate, or test
- Key concepts must contain substance, not labels such as "Topic: AI"
- The exercise must name a deliverable and a success check relevant to the learner's stack
- The checkpoint must test a tradeoff or application, with exactly one correct answer
- estimated_minutes must fit the learner's weekly budget and the requested lesson scope
- Avoid duplicate objectives and exercises listed in the track context
- No Markdown, preamble, comments, or additional keys
"""


def build_weekly_track(
    digest: WeeklyDigest,
    profile: DeveloperProfile,
    max_modules: int = 7,
) -> WeeklyTrack:
    """Build reusable classroom modules from already-generated digest content."""
    budget_minutes = max(30, round(profile.weekly_time_budget_hours * 60))
    selected_items: list[DigestItem] = []
    planned_minutes = 0

    for item in digest.items:
        estimated_minutes = max(15, min(60, item.estimated_reading_minutes + 12))
        if selected_items and planned_minutes + estimated_minutes > budget_minutes:
            continue
        selected_items.append(item)
        planned_minutes += estimated_minutes
        if len(selected_items) >= max_modules:
            break

    modules = _build_modules(selected_items, profile, budget_minutes)

    return WeeklyTrack(
        id=_track_id(digest),
        week_start=digest.week_start,
        week_label=_week_label(digest.week_start),
        generated_at=digest.generated_at,
        learner_focus=_learner_focus(profile),
        weekly_time_budget_minutes=budget_minutes,
        modules=modules,
    )


def _build_modules(
    items: list[DigestItem], profile: DeveloperProfile, budget_minutes: int
) -> list[LearningModule]:
    if not _llm_enabled():
        return [_build_module(item) for item in items]

    modules: list[LearningModule] = []
    track_context = {
        "learner_focus": _learner_focus(profile),
        "weekly_budget_minutes": budget_minutes,
        "ordered_source_titles": [item.title for item in items],
    }
    total_batches = -(-len(items) // TRACK_BATCH_SIZE)
    for offset in range(0, len(items), TRACK_BATCH_SIZE):
        batch = items[offset : offset + TRACK_BATCH_SIZE]
        print(f"[track] authoring lesson batch {offset // TRACK_BATCH_SIZE + 1}/{total_batches}")
        generated = _generate_module_batch(batch, profile, track_context, modules)
        modules.extend(generated)
    return modules


def _llm_enabled() -> bool:
    return os.getenv("STACKTWIN_PIPELINE_LLM_ACTIVE", "false").lower() == "true" and bool(
        os.getenv("NEBIUS_TOKEN") or os.getenv("NEBIUS_API_KEY")
    )


def _generate_module_batch(
    batch: list[DigestItem],
    profile: DeveloperProfile,
    track_context: dict,
    existing_modules: list[LearningModule],
) -> list[LearningModule]:
    records = [
        {
            "id": f"a{index + 1}",
            "title": item.title,
            "source": item.source,
            "summary": item.summary,
            "tags": item.tags,
            "ranking": item.score.model_dump(mode="json"),
            "quiz_evidence": item.quiz[:1],
        }
        for index, item in enumerate(batch)
    ]
    context = {
        **track_context,
        "already_authored": [
            {
                "title": module.title,
                "objectives": module.objectives,
                "exercise": module.exercise.title,
            }
            for module in existing_modules
        ],
    }
    learner = {
        "role": profile.current_role,
        "seniority": str(profile.seniority or "mid"),
        "current_stack": profile.current_stack,
        "learning": profile.learning,
        "domains": profile.domains,
        "career_direction": profile.career_direction,
        "learning_goals": profile.learning_goals,
        "topics_to_avoid": profile.topics_to_avoid,
    }
    payload = {
        "model": MODEL,
        "max_tokens": 2200,
        "temperature": 0.15,
        "response_format": json_response_format(),
        "chat_template_kwargs": chat_template_kwargs(),
        "messages": [
            {"role": "system", "content": TRACK_MODULE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"LEARNER\n{json.dumps(learner, ensure_ascii=False)}\n\n"
                    f"TRACK CONTEXT\n{json.dumps(context, ensure_ascii=False)}\n\n"
                    f"LESSON BATCH\n{json.dumps(records, ensure_ascii=False)}"
                ),
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {os.getenv('NEBIUS_TOKEN') or os.getenv('NEBIUS_API_KEY')}",
        "Content-Type": "application/json",
    }
    try:
        base_url = os.getenv("NEBIUS_API_URL", "https://api.studio.nebius.ai/v1")
        response = httpx.post(
            f"{base_url}/chat/completions", json=payload, headers=headers, timeout=60.0
        )
        response.raise_for_status()
        result = parse_json_value(response_content(response.json()))
        entries = result.get("items", []) if isinstance(result, dict) else []
        by_id = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)}
    except Exception as error:
        print(f"[track] lesson batch failed: {error}")
        by_id = {}

    modules = []
    for index, item in enumerate(batch):
        generated = by_id.get(f"a{index + 1}")
        module = _module_from_generated(item, generated) if generated else _build_module(item)
        modules.append(module)
    return modules


def _module_from_generated(item: DigestItem, generated: dict) -> LearningModule:
    try:
        checkpoint_data = generated["checkpoint"]
        options = [str(option) for option in checkpoint_data["options"]]
        answer_index = int(checkpoint_data["answer_index"])
        if len(options) != 4 or not 0 <= answer_index < len(options):
            raise ValueError("invalid checkpoint options")
        return LearningModule(
            id=_module_id(item),
            title=item.title,
            difficulty=generated["difficulty"],
            estimated_minutes=max(10, min(60, int(generated["estimated_minutes"]))),
            personalization_reason=str(generated["personalization_reason"]),
            source_hints=[{"title": item.title, "source": item.source, "url": item.url}],
            context_brief=str(generated["context_brief"]),
            objectives=[str(value) for value in generated["objectives"]][:3],
            key_concepts=[str(value) for value in generated["key_concepts"]][:5],
            exercise=Exercise(**generated["exercise"]),
            checkpoint=Checkpoint(
                question=str(checkpoint_data["question"]),
                options=options,
                answer=options[answer_index],
                explanation=str(checkpoint_data["explanation"]),
            ),
            takeaway=str(generated["takeaway"]),
        )
    except Exception as error:
        print(f"[track] invalid generated lesson for '{item.title[:50]}': {error}")
        return _build_module(item)


def _build_module(item: DigestItem) -> LearningModule:
    topic = item.tags[0] if item.tags else "the core engineering idea"
    context = item.summary.strip() or item.title
    why = item.score.why_this_matters.strip() or "This supports your current learning goals."

    return LearningModule(
        id=_module_id(item),
        title=item.title,
        difficulty=_difficulty(item),
        estimated_minutes=max(15, min(60, item.estimated_reading_minutes + 12)),
        personalization_reason=why,
        source_hints=[
            {
                "title": item.title,
                "source": item.source,
                "url": item.url,
            }
        ],
        context_brief=context,
        objectives=[
            f"Explain the main engineering idea behind {item.title}.",
            f"Connect {topic} to your current stack or learning goals.",
            "Choose one small experiment that can validate the idea in practice.",
        ],
        key_concepts=_key_concepts(item, context, why),
        exercise=Exercise(
            title=f"Apply {topic}",
            instructions=(
                "Write a short implementation note with the problem, the proposed change, "
                "one measurable outcome, and the smallest experiment you can run this week."
            ),
        ),
        checkpoint=_checkpoint(item),
        takeaway=why,
    )


def _module_id(item: DigestItem) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", item.title.lower()).strip("-")[:48]
    fingerprint = hashlib.sha256(item.url.encode("utf-8")).hexdigest()[:8]
    return f"{slug or 'module'}-{fingerprint}"


def _track_id(digest: WeeklyDigest) -> str:
    source_identity = "\n".join(item.url for item in digest.items)
    fingerprint = hashlib.sha256(source_identity.encode("utf-8")).hexdigest()[:10]
    return f"track-{digest.week_start}-{fingerprint}"


def _difficulty(item: DigestItem) -> str:
    if item.score.difficulty < 0.35:
        return "Focused"
    if item.score.difficulty < 0.7:
        return "Intermediate"
    return "Advanced"


def _key_concepts(item: DigestItem, context: str, why: str) -> list[str]:
    concepts = [f"Topic: {tag}" for tag in item.tags[:3]]
    concepts.append(f"Core idea: {_first_sentence(context)}")
    concepts.append(f"Profile connection: {_first_sentence(why)}")
    return concepts[:5]


def _checkpoint(item: DigestItem) -> Checkpoint:
    if item.quiz:
        quiz = item.quiz[0]
        options = [str(option) for option in quiz.get("options", [])]
        answer = _resolve_quiz_answer(options, str(quiz.get("correct", "")))
        if quiz.get("question") and len(options) >= 2 and answer:
            return Checkpoint(
                question=str(quiz["question"]),
                options=options,
                answer=answer,
                explanation=str(
                    quiz.get("explanation", "Review the source evidence before applying the idea.")
                ),
            )

    options = [
        "Run a small experiment with a measurable outcome",
        "Save the source without changing current practice",
        "Adopt the idea everywhere before evaluating it",
    ]
    return Checkpoint(
        question="What is the strongest next step after this lesson?",
        options=options,
        answer=options[0],
        explanation=(
            "A bounded experiment turns the source into evidence without committing "
            "to a broad change."
        ),
    )


def _resolve_quiz_answer(options: list[str], correct: str) -> str | None:
    normalized = correct.strip()
    if normalized in options:
        return normalized
    if len(normalized) == 1 and normalized.upper() in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        index = ord(normalized.upper()) - ord("A")
        if 0 <= index < len(options):
            return options[index]
    return None


def _learner_focus(profile: DeveloperProfile) -> str:
    signals = profile.learning_goals or profile.learning or profile.topics_to_track
    if signals:
        return ", ".join(signals[:3])
    if profile.current_stack:
        return f"Deepen practical skill with {', '.join(profile.current_stack[:3])}"
    return "Build one practical engineering skill from current technical signals"


def _first_sentence(value: str) -> str:
    # A period inside a technology name, such as Next.js, is not a sentence
    # boundary. Only split when punctuation ends a sentence before whitespace
    # or the end of the value.
    return re.split(r"[.!?](?=\s|$)", value.strip(), maxsplit=1)[0].strip()


def _week_label(week_start: str) -> str:
    start = date.fromisoformat(week_start)
    return f"Week of {start.strftime('%B')} {start.day}"
