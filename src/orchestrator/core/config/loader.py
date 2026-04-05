"""Configuration loader."""

from __future__ import annotations

from orchestrator.core.config.schema import OrchestratorConfig


def load_config(env_file: str | None = None) -> OrchestratorConfig:
    """설정을 로딩한다.

    Args:
        env_file: .env 파일 경로. None이면 기본 경로 사용.

    Returns:
        OrchestratorConfig 인스턴스.
    """
    if env_file:
        return OrchestratorConfig(_env_file=env_file)
    return OrchestratorConfig()
