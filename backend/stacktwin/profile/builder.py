import json
import os

import httpx

from stacktwin.llm import model_for
from stacktwin.profile.schema import DeveloperProfile

NEBIUS_API_URL = os.getenv("NEBIUS_API_URL", "https://api.studio.nebius.com/v1")
NEBIUS_API_KEY = os.getenv("NEBIUS_TOKEN") or os.getenv("NEBIUS_API_KEY", "")
MODEL = model_for("map")


SYSTEM_PROMPT = """
You are a developer profile extractor.
Given raw text from a CV, resume, or LinkedIn export, extract a structured developer profile.

Return ONLY a valid JSON object with these exact fields:
{
  "name": string or null,
  "current_role": string or null,
  "experience_years": integer or null,
  "seniority": one of ["junior", "mid", "senior", "staff"] or null,
  "current_stack": list of strings,
  "learning": list of strings,
  "domains": list of strings,
  "certifications": list of strings,
  "career_direction": string or null,
  "learning_goals": list of strings,
  "topics_to_track": list of strings,
  "topics_to_avoid": list of strings,
  "weekly_time_budget_hours": float
}

Rules:
- Extract only what is clearly stated. Do not invent or assume
- current_stack = technologies they actively use today
- learning = technologies they are currently learning or transitioning to
- domains = areas like microservices, cloud, backend, ML, DevOps
- career_direction = one sentence summary of where they are heading
- If weekly_time_budget_hours is not mentioned default to 2.0
- Return JSON only. No explanation, no markdown, no code fences
"""


def build_profile_from_text(raw_text: str, source: str = "cv") -> DeveloperProfile:
    """
    Send raw extracted text to Nebius Endpoint.
    Returns a structured DeveloperProfile.
    """
    if not NEBIUS_API_KEY:
        raise OSError("NEBIUS_API_KEY is not set in environment variables")

    if not raw_text or len(raw_text.strip()) < 50:
        raise ValueError("Text too short to build a meaningful profile")

    # Truncate to avoid token limits. 3000 chars is enough for a CV.
    truncated = raw_text[:3000]

    payload = {
        "model": MODEL,
        "max_tokens": 1000,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract the developer profile from this text:\n\n{truncated}",
            },
        ],
    }

    headers = {"Authorization": f"Bearer {NEBIUS_API_KEY}", "Content-Type": "application/json"}

    try:
        response = httpx.post(
            f"{NEBIUS_API_URL}/chat/completions", json=payload, headers=headers, timeout=30.0
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        message = f"Nebius API error {e.response.status_code}: {e.response.text}"
        raise ConnectionError(message) from e
    except httpx.TimeoutException as e:
        raise ConnectionError("Nebius API timed out after 30 seconds") from e

    raw_json = response.json()["choices"][0]["message"]["content"].strip()

    try:
        clean = raw_json
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()
        data = json.loads(clean)
        list_fields = [
            "current_stack",
            "learning",
            "domains",
            "certifications",
            "learning_goals",
            "topics_to_track",
            "topics_to_avoid",
        ]
        for field in list_fields:
            if data.get(field) is None:
                data[field] = []
    except json.JSONDecodeError as e:
        raise ValueError(f"Nebius returned invalid JSON:\n{raw_json}") from e

    data["profile_source"] = source
    data["raw_text"] = raw_text[:500]

    return DeveloperProfile(**data)


def build_profile_from_file(file_path: str) -> DeveloperProfile:
    """
    Convenience wrapper that extracts text from file, then builds a profile.
    """
    from stacktwin.profile.extractor import extract_text_from_file

    raw_text = extract_text_from_file(file_path)
    return build_profile_from_text(raw_text, source="cv")
