import pytest


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("TOOL_BACKEND", "local")
    monkeypatch.setenv("TICKETS_FILE", str(tmp_path / "tickets.json"))
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("ALLOWED_TOOLS", "search_customer,get_order,create_ticket")
