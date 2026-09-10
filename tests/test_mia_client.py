from types import SimpleNamespace

import pytest

import app.connectors.mia_client as mia_client


def test_create_mia_client_requires_api_key(monkeypatch):
    monkeypatch.setenv("MIA_API_KEY", "")

    with pytest.raises(mia_client.MiaConfigurationError, match="MIA_API_KEY"):
        mia_client.create_mia_client()


def test_ask_mia_rejects_empty_prompt():
    with pytest.raises(ValueError, match="boş olamaz"):
        mia_client.ask_mia("   ")


def test_ask_mia_returns_clean_text(monkeypatch):
    received_request = {}

    class FakeCompletions:
        def create(self, **kwargs):
            received_request.update(kwargs)

            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="  MIA bağlantısı başarılı  "
                        )
                    )
                ]
            )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeCompletions()
        )
    )

    monkeypatch.setenv("MIA_CHAT_MODEL", "test-model")
    monkeypatch.setattr(
        mia_client,
        "create_mia_client",
        lambda: fake_client,
    )

    result = mia_client.ask_mia("  Test mesajı  ")

    assert result == "MIA bağlantısı başarılı"
    assert received_request["model"] == "test-model"
    assert received_request["messages"][0]["content"] == "Test mesajı"