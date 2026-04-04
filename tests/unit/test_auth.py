"""Unit tests for auth provider."""


import pytest

from orchestrator.auth.provider import EnvAuthProvider
from orchestrator.errors.exceptions import AuthError


class TestEnvAuthProvider:
    def test_get_key_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")
        provider = EnvAuthProvider()
        assert provider.get_key("anthropic") == "sk-ant-test123"

    def test_get_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = EnvAuthProvider()
        with pytest.raises(AuthError, match="Missing environment variable"):
            provider.get_key("anthropic")

    def test_get_key_unknown_provider(self) -> None:
        provider = EnvAuthProvider()
        with pytest.raises(AuthError, match="Unknown provider"):
            provider.get_key("unknown_provider")

    def test_available_providers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("CODEX_API_KEY", "sk-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        provider = EnvAuthProvider()
        available = provider.available_providers()
        assert "anthropic" in available
        assert "openai" in available
        assert "google" not in available

    def test_no_providers_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ["ANTHROPIC_API_KEY", "CODEX_API_KEY", "GEMINI_API_KEY"]:
            monkeypatch.delenv(var, raising=False)
        provider = EnvAuthProvider()
        assert provider.available_providers() == []
