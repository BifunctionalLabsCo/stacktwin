import os
from typing import Literal

ModelStage = Literal["map", "reduce"]
AppMode = Literal["local", "cloud"]


def app_mode() -> AppMode:
    mode = os.getenv("STACKTWIN_APP_MODE", "local").lower()
    if mode not in ("local", "cloud"):
        raise ValueError("STACKTWIN_APP_MODE must be either 'local' or 'cloud'")
    return mode


def model_mode() -> AppMode:
    """Return the model tier, independently from the storage mode used by a Job."""
    mode = os.getenv("STACKTWIN_MODEL_MODE", app_mode()).lower()
    if mode not in ("local", "cloud"):
        raise ValueError("STACKTWIN_MODEL_MODE must be either 'local' or 'cloud'")
    return mode


def model_for(stage: ModelStage) -> str:
    """Use one small model locally and stage-specific production models in cloud mode."""
    if model_mode() == "local":
        return os.getenv("NEBIUS_MODEL_TEST", "Qwen/Qwen3-0.6B")
    if stage == "map":
        return os.getenv("NEBIUS_MODEL_MAP", "NousResearch/Hermes-4-70B")
    return os.getenv("NEBIUS_MODEL_RED", "Qwen/Qwen3-235B-A22B-Thinking-2507")
