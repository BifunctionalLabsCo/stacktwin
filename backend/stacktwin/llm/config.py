import os
from typing import Literal

ModelStage = Literal["map", "reduce"]
ModelMode = Literal["test", "prod"]


def model_mode() -> ModelMode:
    mode = os.getenv("NEBIUS_MODEL_MODE", "test").lower()
    if mode not in ("test", "prod"):
        raise ValueError("NEBIUS_MODEL_MODE must be either 'test' or 'prod'")
    return mode


def model_for(stage: ModelStage) -> str:
    """Resolve the configured model, forcing one small model in test mode."""
    if model_mode() == "test":
        return os.getenv("NEBIUS_MODEL_TEST", "Qwen/Qwen3-0.6B")
    if stage == "map":
        return os.getenv("NEBIUS_MODEL_MAP", "NousResearch/Hermes-4-70B")
    return os.getenv("NEBIUS_MODEL_RED", "Qwen/Qwen3-235B-A22B-Thinking-2507")
