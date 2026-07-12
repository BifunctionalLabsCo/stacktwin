import pytest
from stacktwin.llm.config import model_for, model_mode


def test_test_mode_forces_one_model_for_all_stages(monkeypatch):
    monkeypatch.setenv("NEBIUS_MODEL_MODE", "test")
    monkeypatch.setenv("NEBIUS_MODEL_TEST", "Qwen/test")
    monkeypatch.setenv("NEBIUS_MODEL_MAP", "NousResearch/map")
    monkeypatch.setenv("NEBIUS_MODEL_RED", "Qwen/reduce")

    assert model_for("map") == "Qwen/test"
    assert model_for("reduce") == "Qwen/test"


def test_prod_mode_routes_map_and_reduce_models(monkeypatch):
    monkeypatch.setenv("NEBIUS_MODEL_MODE", "prod")
    monkeypatch.setenv("NEBIUS_MODEL_MAP", "NousResearch/map")
    monkeypatch.setenv("NEBIUS_MODEL_RED", "Qwen/reduce")

    assert model_for("map") == "NousResearch/map"
    assert model_for("reduce") == "Qwen/reduce"


def test_invalid_model_mode_fails_fast(monkeypatch):
    monkeypatch.setenv("NEBIUS_MODEL_MODE", "staging")

    with pytest.raises(ValueError, match="NEBIUS_MODEL_MODE"):
        model_mode()
