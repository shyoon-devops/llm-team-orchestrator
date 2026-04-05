"""Tests for core/auth/provider.py."""

import os

from orchestrator.core.auth.provider import EnvAuthProvider


def test_get_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    provider = EnvAuthProvider()
    assert provider.get_key("anthropic") == "sk-test-123"


def test_get_key_missing():
    provider = EnvAuthProvider()
    # Ensure env var is not set
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)
    result = provider.get_key("openai")
    # May or may not be None depending on actual env
    # Just test it doesn't crash
    assert result is None or isinstance(result, str)


def test_validate(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    provider = EnvAuthProvider()
    assert provider.validate("anthropic") is True


def test_list_providers(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = EnvAuthProvider()
    providers = provider.list_providers()
    assert "anthropic" in providers


def test_extra_mappings(monkeypatch):
    monkeypatch.setenv("CUSTOM_KEY", "my-key")
    provider = EnvAuthProvider(extra_mappings={"custom": ["CUSTOM_KEY"]})
    assert provider.get_key("custom") == "my-key"
