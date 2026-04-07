"""Common schemas shared across the orchestrator."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, SecretStr

from orchestrator.core.presets.models import MCPServerDef


class AgentResult(BaseModel):
    """에이전트 실행 결과.

    CLI subprocess 또는 MCP tool call의 결과를 통합된 형태로 표현한다.
    output은 에이전트가 생성한 텍스트 결과, raw는 파싱 전 원시 데이터를 보존한다.
    """

    output: str = Field(
        ...,
        description="에이전트가 생성한 최종 텍스트 출력",
        examples=["JWT 미들웨어 구현이 완료되었습니다."],
    )
    exit_code: int = Field(
        default=0,
        ge=-1,
        le=255,
        description="프로세스 종료 코드. 0=성공, 비0=실패, -1=timeout",
    )
    duration_ms: int = Field(
        default=0,
        ge=0,
        description="실행 소요 시간 (밀리초)",
    )
    tokens_used: int = Field(
        default=0,
        ge=0,
        description="소비된 토큰 수 (추적 가능한 경우)",
    )
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="CLI JSON 출력 등 파싱 전 원시 데이터",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "output": "JWT 미들웨어를 Express.js에 구현했습니다.",
                    "exit_code": 0,
                    "duration_ms": 45200,
                    "tokens_used": 3420,
                    "raw": {
                        "model": "claude-sonnet-4-20250514",
                        "stop_reason": "end_turn",
                    },
                }
            ]
        }
    }


class AdapterConfig(BaseModel):
    """CLI 어댑터 공통 설정.

    CLI subprocess 실행에 필요한 인증 정보와 타임아웃을 정의한다.
    api_key는 SecretStr로 감싸서 로그에 노출되지 않도록 한다.
    """

    api_key: SecretStr | None = Field(
        default=None,
        description="API 키. None이면 AuthProvider에서 자동 조회",
    )
    timeout: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="CLI subprocess 타임아웃 (초)",
    )
    model: str | None = Field(
        default=None,
        description="사용할 모델 이름. None이면 CLI 기본값 사용",
        examples=["claude-sonnet-4-20250514", "o3-mini", "gemini-2.5-pro"],
    )
    extra_args: list[str] = Field(
        default_factory=list,
        description="CLI에 전달할 추가 인자 목록",
        examples=[["--no-cache", "--verbose"]],
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="CLI subprocess에 전달할 추가 환경 변수",
    )
    working_dir: str | None = Field(
        default=None,
        description="CLI 실행 작업 디렉토리 경로. None이면 worktree 경로 사용",
    )
    mcp_servers: dict[str, MCPServerDef] = Field(
        default_factory=dict,
        description="에이전트에 노출할 MCP 서버 목록. "
        "비어있으면 MCP 도구 없음 (격리).",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "api_key": "sk-ant-***",
                    "timeout": 300,
                    "model": "claude-sonnet-4-20250514",
                    "extra_args": [],
                    "env": {},
                    "working_dir": None,
                }
            ]
        }
    }
