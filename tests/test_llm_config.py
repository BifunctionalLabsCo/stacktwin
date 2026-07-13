import pytest
from stacktwin.llm.config import app_mode, model_for


def test_local_mode_forces_one_model_for_all_stages(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_MODE", "local")
    monkeypatch.setenv("NEBIUS_MODEL_TEST", "Qwen/test")
    monkeypatch.setenv("NEBIUS_MODEL_MAP", "NousResearch/map")
    monkeypatch.setenv("NEBIUS_MODEL_RED", "Qwen/reduce")

    assert model_for("map") == "Qwen/test"
    assert model_for("reduce") == "Qwen/test"


def test_cloud_mode_routes_map_and_reduce_models(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_MODE", "cloud")
    monkeypatch.setenv("NEBIUS_MODEL_MAP", "NousResearch/map")
    monkeypatch.setenv("NEBIUS_MODEL_RED", "Qwen/reduce")

    assert model_for("map") == "NousResearch/map"
    assert model_for("reduce") == "Qwen/reduce"


def test_invalid_app_mode_fails_fast(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_MODE", "staging")

    with pytest.raises(ValueError, match="STACKTWIN_APP_MODE"):
        app_mode()
