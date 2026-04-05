"""AuthProvider ABC and EnvAuthProvider implementation."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import ClassVar


class AuthProvider(ABC):
    """API 키 조회 추상 인터페이스.

    CLI 어댑터가 에이전트 실행 시 필요한 API 키를 조회하는 계약.
    구현체가 키 저장소를 캡슐화한다.
    """

    @abstractmethod
    def get_key(self, provider: str) -> str | None:
        """지정된 프로바이더의 API 키를 반환한다.

        Args:
            provider: 프로바이더 이름 ("anthropic", "openai", "google").

        Returns:
            API 키 문자열. 없으면 None.
        """
        ...

    @abstractmethod
    def validate(self, provider: str) -> bool:
        """지정된 프로바이더의 API 키가 유효한지 확인한다.

        Args:
            provider: 프로바이더 이름.

        Returns:
            유효하면 True.
        """
        ...

    @abstractmethod
    def list_providers(self) -> list[str]:
        """사용 가능한 프로바이더 목록을 반환한다.

        Returns:
            API 키가 설정된 프로바이더 이름 목록.
        """
        ...


class EnvAuthProvider(AuthProvider):
    """환경 변수 기반 API 키 프로바이더.

    프로바이더 이름을 환경 변수 이름으로 매핑하여 키를 조회한다.

    매핑 규칙:
    - "anthropic" -> ANTHROPIC_API_KEY
    - "openai" -> OPENAI_API_KEY
    - "google" -> GOOGLE_API_KEY (또는 GEMINI_API_KEY)
    """

    _DEFAULT_MAP: ClassVar[dict[str, list[str]]] = {
        "anthropic": ["ANTHROPIC_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
    }

    def __init__(
        self,
        extra_mappings: dict[str, list[str]] | None = None,
    ) -> None:
        """
        Args:
            extra_mappings: 추가 프로바이더 -> 환경 변수 매핑.
        """
        self._provider_env_map = {**self._DEFAULT_MAP}
        if extra_mappings:
            self._provider_env_map.update(extra_mappings)

    def get_key(self, provider: str) -> str | None:
        """환경 변수에서 API 키를 조회한다."""
        env_names = self._provider_env_map.get(provider, [])
        for env_name in env_names:
            key = os.environ.get(env_name)
            if key:
                return key
        return None

    def validate(self, provider: str) -> bool:
        """API 키가 설정되어 있는지 확인한다 (형식 검증은 하지 않음)."""
        return self.get_key(provider) is not None

    def list_providers(self) -> list[str]:
        """API 키가 설정된 프로바이더 목록을 반환한다."""
        return [p for p in self._provider_env_map if self.validate(p)]
