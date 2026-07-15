"""Portable structured-output helpers for Nebius endpoints and local vLLM."""

import json
from typing import Any


def json_response_format() -> dict[str, str]:
    """Use the OpenAI-compatible JSON mode supported by every Job model tier."""
    return {"type": "json_object"}


def chat_template_kwargs() -> dict[str, bool]:
    """Keep Qwen's reasoning trace out of the JSON response; other models ignore it."""
    return {"enable_thinking": False}


def response_content(payload: dict[str, Any]) -> str:
    """Extract the assistant content from an OpenAI-compatible completion payload."""
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()


def parse_json_value(raw: str | None) -> Any | None:
    """Parse JSON even if a model adds prose or Markdown around the value."""
    if not raw:
        return None
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("```", 2)[1]
        if clean.lstrip().startswith("json"):
            clean = clean.lstrip()[4:]
    decoder = json.JSONDecoder()
    for marker in ("{", "["):
        start = clean.find(marker)
        if start < 0:
            continue
        try:
            value, _ = decoder.raw_decode(clean[start:])
            return value
        except json.JSONDecodeError:
            continue
    return None
