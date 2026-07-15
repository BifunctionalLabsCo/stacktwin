import pytest
from stacktwin.llm.config import app_mode, model_for, model_mode


def test_local_mode_forces_one_model_for_all_stages(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_MODE", "local")
    monkeypatch.setenv("STACKTWIN_JOB_MODEL", "Qwen/test")
    monkeypatch.setenv("NEBIUS_MODEL_MAP", "NousResearch/map")
    monkeypatch.setenv("NEBIUS_MODEL_RED", "Qwen/reduce")

    assert model_for("map") == "Qwen/test"
    assert model_for("reduce") == "Qwen/test"


def test_cloud_mode_still_uses_economical_qwen_for_every_stage(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_MODE", "cloud")
    monkeypatch.setenv("STACKTWIN_JOB_MODEL", "Qwen/economical")
    monkeypatch.setenv("NEBIUS_MODEL_MAP", "NousResearch/map")
    monkeypatch.setenv("NEBIUS_MODEL_RED", "Qwen/reduce")

    assert model_for("map") == "Qwen/economical"
    assert model_for("reduce") == "Qwen/economical"


def test_job_can_use_local_model_tier_with_cloud_storage_mode(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_MODE", "cloud")
    monkeypatch.setenv("STACKTWIN_MODEL_MODE", "local")
    monkeypatch.setenv("STACKTWIN_JOB_MODEL", "Qwen/test")

    assert app_mode() == "cloud"
    assert model_mode() == "local"
    assert model_for("map") == "Qwen/test"
    assert model_for("reduce") == "Qwen/test"


def test_invalid_app_mode_fails_fast(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_MODE", "staging")

    with pytest.raises(ValueError, match="STACKTWIN_APP_MODE"):
        app_mode()
