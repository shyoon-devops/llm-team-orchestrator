"""OrchestratorConfig — pydantic-settings based configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorConfig(BaseSettings):
    """시스템 전체 설정.

    pydantic-settings 기반. 환경 변수, .env 파일에서 자동 로딩한다.
    환경 변수 prefix: ORCHESTRATOR_

    예: ORCHESTRATOR_DEFAULT_TIMEOUT=600
    """

    # === 일반 ===
    app_name: str = Field(
        default="agent-team-orchestrator",
        description="애플리케이션 이름",
    )
    debug: bool = Field(
        default=False,
        description="디버그 모드. True면 상세 로깅 활성화",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="로그 레벨",
    )

    # === 실행 ===
    default_timeout: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="기본 에이전트 실행 타임아웃 (초)",
    )
    max_concurrent_agents: int = Field(
        default=5,
        ge=1,
        le=20,
        description="동시 실행 가능한 최대 에이전트 수",
    )
    default_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="기본 최대 재시도 횟수",
    )

    # === CLI 우선순위 ===
    cli_priority: list[str] = Field(
        default=["claude", "codex", "gemini"],
        description="CLI 우선순위 목록. 폴백 시 이 순서로 시도",
    )

    # === 프리셋 ===
    preset_dirs: list[str] = Field(
        default=["./presets"],
        description="프리셋 YAML 검색 디렉토리 목록",
    )

    # === API 서버 ===
    api_host: str = Field(
        default="0.0.0.0",
        description="API 서버 바인드 호스트",
    )
    api_port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="API 서버 포트",
    )

    # === LangGraph ===
    planner_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="TeamPlanner/Decomposer에서 사용하는 LLM 모델",
    )
    synthesizer_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Synthesizer에서 사용하는 LLM 모델",
    )

    # === Git Worktree ===
    worktree_base_dir: str = Field(
        default="/tmp/orchestrator-worktrees",
        description="Git worktree 생성 기본 디렉토리",
    )
    auto_merge: bool = Field(
        default=True,
        description="파이프라인 완료 시 worktree를 자동으로 target branch에 merge",
    )

    # === 체크포인팅 ===
    checkpoint_enabled: bool = Field(
        default=True,
        description="LangGraph SQLite 체크포인터 활성화",
    )
    checkpoint_db_path: str = Field(
        default="./data/checkpoints.sqlite",
        description="체크포인트 SQLite 파일 경로",
    )

    model_config = SettingsConfigDict(
        env_prefix="ORCHESTRATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
