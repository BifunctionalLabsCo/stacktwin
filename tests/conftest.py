import pytest


@pytest.fixture(autouse=True)
def disable_password_gate_for_tests(monkeypatch):
    """Keep API contract tests independent of a developer's local .env file."""
    monkeypatch.delenv("STACKTWIN_APP_PASSWORD", raising=False)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_TOKEN", raising=False)
