import hashlib
import re
from datetime import date

from stacktwin.learning.schema import Checkpoint, Exercise, LearningModule, WeeklyTrack
from stacktwin.profile.schema import DeveloperProfile, DigestItem, WeeklyDigest


def build_weekly_track(
    digest: WeeklyDigest,
    profile: DeveloperProfile,
    max_modules: int = 7,
) -> WeeklyTrack:
    """Build reusable classroom modules from already-generated digest content."""
    budget_minutes = max(30, round(profile.weekly_time_budget_hours * 60))
    modules: list[LearningModule] = []
    planned_minutes = 0

    for item in digest.items:
        module = _build_module(item)
        if modules and planned_minutes + module.estimated_minutes > budget_minutes:
            continue
        modules.append(module)
        planned_minutes += module.estimated_minutes
        if len(modules) >= max_modules:
            break

    return WeeklyTrack(
        id=_track_id(digest),
        week_start=digest.week_start,
        week_label=_week_label(digest.week_start),
        generated_at=digest.generated_at,
        learner_focus=_learner_focus(profile),
        weekly_time_budget_minutes=budget_minutes,
        modules=modules,
    )


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
