"""Authentication provider for CLI adapters."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import ClassVar

from orchestrator.errors.exceptions import AuthError


class AuthProvider(ABC):
    """Abstract authentication provider."""

    @abstractmethod
    def get_key(self, provider: str) -> str:
        """Get API key for the given provider."""
        ...

    @abstractmethod
    def available_providers(self) -> list[str]:
        """List providers with valid keys."""
        ...


class EnvAuthProvider(AuthProvider):
    """Environment variable-based auth provider (PoC implementation)."""

    KEY_MAP: ClassVar[dict[str, str]] = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "CODEX_API_KEY",
        "google": "GEMINI_API_KEY",
    }

    def get_key(self, provider: str) -> str:
        env_var = self.KEY_MAP.get(provider)
        if not env_var:
            raise AuthError(f"Unknown provider: {provider}")
        key = os.environ.get(env_var, "")
        if not key:
            raise AuthError(f"Missing environment variable: {env_var}")
        return key

    def available_providers(self) -> list[str]:
        return [
            provider
            for provider, env_var in self.KEY_MAP.items()
            if os.environ.get(env_var)
        ]
