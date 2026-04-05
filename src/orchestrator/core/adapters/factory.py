"""AdapterFactory — creates CLI adapters from presets."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.adapters.claude import ClaudeAdapter
from orchestrator.core.adapters.codex import CodexAdapter
from orchestrator.core.adapters.gemini import GeminiAdapter

if TYPE_CHECKING:
    from orchestrator.core.auth.provider import AuthProvider

logger = structlog.get_logger()

_ADAPTER_MAP: dict[str, type[CLIAdapter]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "gemini": GeminiAdapter,
}


class AdapterFactory:
    """CLI 어댑터 팩토리.

    프리셋 설정과 AuthProvider를 기반으로 CLIAdapter 인스턴스를 생성한다.
    """

    def __init__(self, auth_provider: AuthProvider | None = None) -> None:
        """
        Args:
            auth_provider: API 키 프로바이더.
        """
        self._auth_provider = auth_provider

    def create(self, cli_name: str) -> CLIAdapter:
        """CLI 이름으로 어댑터를 생성한다.

        Args:
            cli_name: CLI 이름 ("claude", "codex", "gemini").

        Returns:
            CLIAdapter 인스턴스.

        Raises:
            ValueError: 지원하지 않는 CLI 이름.
        """
        adapter_cls = _ADAPTER_MAP.get(cli_name)
        if adapter_cls is None:
            msg = f"Unsupported CLI: {cli_name}. Supported: {list(_ADAPTER_MAP)}"
            raise ValueError(msg)
        return adapter_cls()

    def list_available(self) -> list[str]:
        """사용 가능한 CLI 어댑터 이름 목록을 반환한다.

        Returns:
            CLI 이름 목록.
        """
        return list(_ADAPTER_MAP.keys())
