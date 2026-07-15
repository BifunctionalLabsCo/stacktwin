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
    """Return the legacy job tier marker retained for configuration compatibility."""
    mode = os.getenv("STACKTWIN_MODEL_MODE", app_mode()).lower()
    if mode not in ("local", "cloud"):
        raise ValueError("STACKTWIN_MODEL_MODE must be either 'local' or 'cloud'")
    return mode


def model_for(stage: ModelStage) -> str:
    """Use the economical Qwen worker for every finite pipeline phase.

    App mode controls artifact placement only. Stage-specific prompts provide
    specialization without allocating a second, larger model tier.
    """
    del stage
    return os.getenv("STACKTWIN_JOB_MODEL", os.getenv("NEBIUS_MODEL_TEST", "Qwen/Qwen3-0.6B"))
