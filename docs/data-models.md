# 데이터 구조 + 인터페이스 명세서

> v1.0 | 2026-04-05
> 기반: `docs/SPEC.md` v2.0

---

## 목차

1. [core/models/schemas.py — 공통 스키마](#1-coremodelsschemaspy--공통-스키마)
2. [core/executor/base.py — 에이전트 실행](#2-coreexecutorbasepy--에이전트-실행)
3. [core/presets/models.py — 프리셋 모델](#3-corepresetmodelspy--프리셋-모델)
4. [core/queue/models.py — 칸반 큐 모델](#4-corequeuemodelspy--칸반-큐-모델)
5. [core/models/pipeline.py — 파이프라인 모델](#5-coremodelspipelinepy--파이프라인-모델)
6. [core/events/types.py — 이벤트 타입](#6-coreeventstypespy--이벤트-타입)
7. [core/auth/provider.py — 인증 프로바이더](#7-coreauthproviderpy--인증-프로바이더)
8. [core/config/schema.py — 설정](#8-coreconfigschemapy--설정)
9. [모델 관계 다이어그램](#9-모델-관계-다이어그램)

---

## 1. `core/models/schemas.py` — 공통 스키마

### 1.1 `AgentResult`

에이전트 실행 결과를 담는 불변 데이터 모델. 모든 CLI subprocess 실행 결과를 동일한 형태로 반환한다.

```python
from pydantic import BaseModel, Field
from typing import Any


class AgentResult(BaseModel):
    """에이전트 실행 결과.

    CLI subprocess 실행 결과를 통합된 형태로 표현한다.
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
                    "output": "JWT 미들웨어를 Express.js에 구현했습니다.\n- src/middleware/auth.ts 생성\n- 토큰 검증 로직 포함",
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
```

**JSON 직렬화 예시:**

```json
{
  "output": "JWT 미들웨어를 Express.js에 구현했습니다.\n- src/middleware/auth.ts 생성\n- 토큰 검증 로직 포함",
  "exit_code": 0,
  "duration_ms": 45200,
  "tokens_used": 3420,
  "raw": {
    "model": "claude-sonnet-4-20250514",
    "stop_reason": "end_turn"
  }
}
```

**관계:**
- `WorkerResult.output` 필드는 `AgentResult.output`에서 복사됨
- `Synthesizer.synthesize()`의 입력으로 사용됨
- `TaskItem.result`에 문자열로 저장됨

---

### 1.2 `AdapterConfig`

CLI 어댑터 공통 설정. 각 CLI 어댑터(`ClaudeAdapter`, `CodexAdapter`, `GeminiAdapter`)가 실행 시 참조하는 공통 설정 값이다.

```python
from pydantic import BaseModel, Field, SecretStr
from typing import Any


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
```

**JSON 직렬화 예시:**

```json
{
  "api_key": "**********",
  "timeout": 300,
  "model": "claude-sonnet-4-20250514",
  "extra_args": [],
  "env": {},
  "working_dir": null
}
```

> **주의:** `api_key`는 `SecretStr`이므로 직렬화 시 `**********`로 마스킹된다.
> 실제 값 접근: `config.api_key.get_secret_value()`

**관계:**
- `CLIAgentExecutor` 생성 시 주입됨
- `AdapterFactory.create()`에서 `AgentPreset` + `AuthProvider`로부터 구성됨
- `OrchestratorConfig.default_timeout`이 기본값 소스

---

## 2. `core/executor/base.py` — 에이전트 실행

### 2.1 `AgentExecutor` (ABC)

모든 에이전트 실행기의 추상 기반 클래스. CLI subprocess든 MCP tool call이든 동일한 인터페이스를 따른다.

```python
from abc import ABC, abstractmethod
from typing import Any


class AgentExecutor(ABC):
    """도메인 무관 에이전트 실행 인터페이스.

    모든 에이전트 실행기(CLI, Mock)는 이 ABC를 상속한다.
    run()으로 프롬프트를 실행하고, health_check()로 가용성을 확인한다.

    MCP 서버와 Skills는 별도 실행기가 아니라 CLI 플래그로 전달된다.
    예: claude -p "..." --system-prompt "persona" --mcp-config '{"mcpServers":{...}}'

    Attributes:
        executor_type: 실행기 유형 식별자. "cli" | "mock"
    """

    executor_type: str  # 서브클래스에서 클래스 변수로 정의

    @abstractmethod
    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """프롬프트를 에이전트에 전달하고 결과를 반환한다.

        Args:
            prompt: 에이전트에 전달할 프롬프트 문자열.
            timeout: 최대 실행 시간 (초). 초과 시 TimeoutError.
            context: 추가 컨텍스트 (이전 결과, 파일 목록 등).

        Returns:
            AgentResult: 실행 결과.

        Raises:
            CLIExecutionError: 프로세스 실행 실패.
            CLITimeoutError: 타임아웃 초과.
            CLIParseError: 출력 파싱 실패.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """에이전트 가용성을 확인한다.

        Returns:
            bool: 가용하면 True, 아니면 False.
        """
        ...
```

### 2.2 `CLIAgentExecutor`

CLI subprocess 기반 에이전트 실행기. Claude Code, Codex CLI, Gemini CLI를 subprocess로 실행한다.

```python
from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.models.schemas import AdapterConfig


class CLIAgentExecutor(AgentExecutor):
    """CLI subprocess 기반 에이전트 실행기.

    내부적으로 CLIAdapter를 사용하여 CLI 프로세스를 실행한다.
    persona 프롬프트, MCP 서버, Skills를 CLI 플래그로 주입하고,
    결과를 파싱하여 AgentResult를 반환한다.

    모든 에이전트(코딩, ELK 분석, Grafana 모니터링 등)는 이 실행기를 사용한다.
    MCP 서버와 Skills는 CLI 옵션으로 전달된다:
    - claude: --system-prompt, --mcp-config
    - codex: CODEX_HOME 기반 MCP 설정
    - gemini: --mcp-config (또는 설정 파일)

    Attributes:
        executor_type: "cli" (고정)
        adapter: CLIAdapter 인스턴스 (Claude/Codex/Gemini)
        config: AdapterConfig 실행 설정
        persona_prompt: 시스템 프롬프트에 주입할 페르소나 텍스트
        mcp_config: MCP 서버 설정 (CLI --mcp-config 플래그로 전달)
        skills: Skill 목록 (CLI에 전달)
    """

    executor_type: str = "cli"

    def __init__(
        self,
        adapter: CLIAdapter,
        config: AdapterConfig,
        persona_prompt: str = "",
        mcp_config: dict[str, Any] | None = None,
        skills: list[str] | None = None,
    ) -> None:
        """
        Args:
            adapter: CLIAdapter 구현체 (ClaudeAdapter, CodexAdapter, GeminiAdapter).
            config: 어댑터 실행 설정.
            persona_prompt: 에이전트 페르소나 프롬프트. --system-prompt로 주입.
            mcp_config: MCP 서버 설정. --mcp-config로 전달.
                예: {"mcpServers": {"elasticsearch": {"command": "npx", ...}}}
            skills: Skill 이름 목록. CLI에 전달.
        """
        self.adapter = adapter
        self.config = config
        self.persona_prompt = persona_prompt
        self.mcp_config = mcp_config or {}
        self.skills = skills or []

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """CLI subprocess를 실행하여 결과를 반환한다.

        1. persona_prompt → --system-prompt 플래그로 전달
        2. mcp_config → --mcp-config 플래그로 전달
        3. skills → CLI 옵션으로 전달
        4. context가 있으면 프롬프트에 추가 정보 삽입
        5. adapter.run()으로 CLI 실행
        6. 결과를 AgentResult로 파싱하여 반환
        """
        ...

    async def health_check(self) -> bool:
        """CLI 바이너리 존재 여부 및 인증 상태를 확인한다."""
        ...
```

---

## 3. `core/presets/models.py` — 프리셋 모델

### 3.1 `PersonaDef`

에이전트의 역할, 목표, 배경, 제약 조건을 정의하는 페르소나 모델.

```python
from pydantic import BaseModel, Field


class PersonaDef(BaseModel):
    """에이전트 페르소나 정의.

    CrewAI의 Agent(role, goal, backstory) 패턴을 차용.
    이 정보는 시스템 프롬프트로 변환되어 에이전트에 주입된다.
    """

    role: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="에이전트 역할 (예: '시니어 백엔드 개발자')",
        examples=["시니어 백엔드 개발자", "보안 감사 전문가"],
    )
    goal: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="에이전트가 달성해야 할 목표",
        examples=["주어진 요구사항을 분석하고 최적의 아키텍처를 설계한다"],
    )
    backstory: str = Field(
        default="",
        max_length=2000,
        description="에이전트 배경 설명 (선택). 프롬프트에 맥락 제공",
        examples=["10년간 대규모 시스템 설계 경험이 있으며, DDD와 클린 아키텍처에 능통하다"],
    )
    constraints: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="에이전트 행동 제약 목록",
        examples=[["테스트 코드를 반드시 포함할 것", "기존 API 호환성을 유지할 것"]],
    )

    def to_system_prompt(self) -> str:
        """페르소나를 시스템 프롬프트 문자열로 변환한다.

        Returns:
            str: 시스템 프롬프트 형식의 문자열.
        """
        parts = [
            f"당신의 역할: {self.role}",
            f"목표: {self.goal}",
        ]
        if self.backstory:
            parts.append(f"배경: {self.backstory}")
        if self.constraints:
            constraints_text = "\n".join(f"- {c}" for c in self.constraints)
            parts.append(f"제약 조건:\n{constraints_text}")
        return "\n\n".join(parts)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "role": "시니어 백엔드 개발자",
                    "goal": "견고하고 테스트 가능한 백엔드 코드를 구현한다",
                    "backstory": "10년간 대규모 시스템 개발 경험",
                    "constraints": [
                        "테스트 코드를 반드시 포함할 것",
                        "기존 API 호환성을 유지할 것",
                    ],
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "role": "시니어 백엔드 개발자",
  "goal": "견고하고 테스트 가능한 백엔드 코드를 구현한다",
  "backstory": "10년간 대규모 시스템 개발 경험",
  "constraints": [
    "테스트 코드를 반드시 포함할 것",
    "기존 API 호환성을 유지할 것"
  ]
}
```

---

### 3.2 `ToolAccess`

에이전트가 사용할 수 있는/없는 도구 목록을 정의한다.

```python
class ToolAccess(BaseModel):
    """에이전트 도구 접근 제어.

    allowed가 비어있으면 모든 도구 허용 (disallowed 제외).
    allowed에 값이 있으면 해당 도구만 허용.
    """

    allowed: list[str] = Field(
        default_factory=list,
        description="허용된 도구 이름 목록. 비어있으면 전체 허용",
        examples=[["Read", "Write", "Bash"]],
    )
    disallowed: list[str] = Field(
        default_factory=list,
        description="차단된 도구 이름 목록. allowed보다 우선",
        examples=[["WebSearch", "WebFetch"]],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "allowed": ["Read", "Write", "Bash", "Grep"],
                    "disallowed": ["WebSearch"],
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "allowed": ["Read", "Write", "Bash", "Grep"],
  "disallowed": ["WebSearch"]
}
```

---

### 3.3 `AgentLimits`

에이전트의 실행 제한을 정의한다. 비용/시간/반복 폭주를 방지한다.

```python
class AgentLimits(BaseModel):
    """에이전트 실행 제한.

    에이전트가 무한 루프에 빠지거나 과도한 리소스를 사용하는 것을 방지한다.
    """

    timeout: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="최대 실행 시간 (초)",
    )
    max_turns: int = Field(
        default=50,
        ge=1,
        le=500,
        description="최대 대화 턴 수 (LLM 호출 횟수)",
    )
    max_iterations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="최대 반복 수 (tool_use 루프). MCP executor에서 사용",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timeout": 300,
                    "max_turns": 50,
                    "max_iterations": 10,
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "timeout": 300,
  "max_turns": 50,
  "max_iterations": 10
}
```

---

### 3.4 `MCPServerDef`

MCP 서버 하나의 실행 정의. CLI agent에 --mcp-config로 전달되는 도구 서버의 시작 명령과 환경을 명세한다.

```python
class MCPServerDef(BaseModel):
    """MCP 서버 실행 정의.

    stdio transport 기반 MCP 서버의 실행 명령, 인자, 환경 변수를 정의한다.
    CLIAgentExecutor가 이 정보를 --mcp-config 플래그로 CLI에 전달한다.
    """

    command: str = Field(
        ...,
        min_length=1,
        description="MCP 서버 실행 명령어",
        examples=["npx", "python", "uvx"],
    )
    args: list[str] = Field(
        default_factory=list,
        description="명령어에 전달할 인자 목록",
        examples=[["-y", "@anthropic/mcp-server-elasticsearch"]],
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="MCP 서버 프로세스에 전달할 환경 변수",
        examples=[{"ES_URL": "http://localhost:9200", "ES_API_KEY": "${ES_API_KEY}"}],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "command": "npx",
                    "args": ["-y", "@anthropic/mcp-server-elasticsearch"],
                    "env": {
                        "ES_URL": "http://localhost:9200",
                        "ES_API_KEY": "${ES_API_KEY}",
                    },
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "command": "npx",
  "args": ["-y", "@anthropic/mcp-server-elasticsearch"],
  "env": {
    "ES_URL": "http://localhost:9200",
    "ES_API_KEY": "${ES_API_KEY}"
  }
}
```

> **환경 변수 참조:** `env` 값에 `${VAR_NAME}` 형식을 사용하면, `PresetRegistry`가 로딩 시 실제 환경 변수로 치환한다.

---

### 3.5 `AgentPreset`

단일 에이전트의 전체 설정을 정의하는 프리셋. YAML 파일로 저장/로딩되며, `PresetRegistry`가 관리한다.

```python
from typing import Literal


class AgentPreset(BaseModel):
    """에이전트 프리셋.

    에이전트의 페르소나, CLI 우선순위, 모델, 도구 접근, MCP 서버, Skills,
    실행 제한을 하나의 재사용 가능한 단위로 묶는다.
    모든 에이전트는 CLI(claude/codex/gemini)로 실행되며, MCP 서버와
    Skills는 CLI 플래그로 전달되는 도구 옵션이다.
    YAML 파일(presets/agents/*.yaml)로 저장·로딩된다.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9\-]*$",
        description="프리셋 고유 이름 (kebab-case)",
        examples=["architect", "implementer", "elk-analyst"],
    )
    description: str = Field(
        default="",
        max_length=500,
        description="프리셋 설명",
        examples=["시스템 아키텍처 설계 전문가"],
    )
    tags: list[str] = Field(
        default_factory=list,
        description="프리셋 분류 태그",
        examples=[["coding", "backend", "senior"]],
    )
    persona: PersonaDef = Field(
        ...,
        description="에이전트 페르소나 정의",
    )
    preferred_cli: Literal["claude", "codex", "gemini"] | None = Field(
        default="claude",
        description="우선 사용 CLI. None이면 자동 선택",
    )
    fallback_cli: list[Literal["claude", "codex", "gemini"]] = Field(
        default_factory=list,
        description="폴백 CLI 우선순위 목록. preferred_cli 실패 시 순서대로 시도",
        examples=[["codex", "gemini"]],
    )
    model: str | None = Field(
        default=None,
        description="사용할 LLM 모델. None이면 CLI/provider 기본값",
        examples=["claude-sonnet-4-20250514", "o3-mini", "gemini-2.5-pro"],
    )
    tools: ToolAccess = Field(
        default_factory=ToolAccess,
        description="도구 접근 제어",
    )
    mcp_servers: dict[str, MCPServerDef] = Field(
        default_factory=dict,
        description="MCP 서버 이름 → 실행 정의 매핑. CLI --mcp-config 플래그로 전달",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="에이전트에 부여할 Skill 목록. CLI 옵션으로 전달",
        examples=[["code-review", "test-generation"]],
    )
    limits: AgentLimits = Field(
        default_factory=AgentLimits,
        description="실행 제한",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "implementer",
                    "description": "기능 구현 전문 개발자",
                    "tags": ["coding", "backend"],
                    "persona": {
                        "role": "시니어 백엔드 개발자",
                        "goal": "견고하고 테스트 가능한 코드를 구현한다",
                        "backstory": "10년간 대규모 시스템 개발 경험",
                        "constraints": ["테스트 코드 필수", "타입 힌트 필수"],
                    },
                    "preferred_cli": "claude",
                    "fallback_cli": ["codex", "gemini"],
                    "model": "claude-sonnet-4-20250514",
                    "tools": {
                        "allowed": [],
                        "disallowed": [],
                    },
                    "mcp_servers": {},
                    "skills": [],
                    "limits": {
                        "timeout": 300,
                        "max_turns": 50,
                        "max_iterations": 10,
                    },
                }
            ]
        }
    }
```

**YAML 프리셋 예시 (`presets/agents/implementer.yaml`):**

```yaml
name: implementer
description: 기능 구현 전문 개발자
tags: [coding, backend]
persona:
  role: 시니어 백엔드 개발자
  goal: 견고하고 테스트 가능한 코드를 구현한다
  backstory: 10년간 대규모 시스템 개발 경험
  constraints:
    - 테스트 코드를 반드시 포함할 것
    - 타입 힌트를 반드시 사용할 것
preferred_cli: claude
fallback_cli: [codex, gemini]
model: claude-sonnet-4-20250514
tools:
  allowed: []
  disallowed: []
mcp_servers: {}
skills: []
limits:
  timeout: 300
  max_turns: 50
```

**JSON 직렬화 예시:**

```json
{
  "name": "implementer",
  "description": "기능 구현 전문 개발자",
  "tags": ["coding", "backend"],
  "persona": {
    "role": "시니어 백엔드 개발자",
    "goal": "견고하고 테스트 가능한 코드를 구현한다",
    "backstory": "10년간 대규모 시스템 개발 경험",
    "constraints": ["테스트 코드를 반드시 포함할 것", "타입 힌트를 반드시 사용할 것"]
  },
  "preferred_cli": "claude",
  "fallback_cli": ["codex", "gemini"],
  "model": "claude-sonnet-4-20250514",
  "tools": { "allowed": [], "disallowed": [] },
  "mcp_servers": {},
  "skills": [],
  "limits": { "timeout": 300, "max_turns": 50, "max_iterations": 10 }
}
```

**관계:**
- `TeamAgentDef.preset`에서 이름으로 참조됨
- `PresetRegistry.load_agent_preset()`으로 로딩
- `AdapterFactory.create()`에서 `AgentExecutor` 생성 시 사용됨
- `persona.to_system_prompt()`가 `CLIAgentExecutor.persona_prompt`로 주입됨

---

### 3.6 `TeamAgentDef`

팀 프리셋 내에서 에이전트를 참조하는 정의. 프리셋 이름 + 오버라이드로 구성된다.

```python
class TeamAgentDef(BaseModel):
    """팀 내 에이전트 정의.

    기존 AgentPreset을 이름으로 참조하고, 필요시 필드를 오버라이드한다.
    오버라이드는 deep merge로 적용된다.
    """

    preset: str = Field(
        ...,
        min_length=1,
        description="참조할 AgentPreset 이름",
        examples=["implementer", "architect"],
    )
    overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="AgentPreset 필드 오버라이드. deep merge로 적용됨",
        examples=[
            {
                "model": "o3-mini",
                "limits": {"timeout": 600},
                "persona": {"constraints": ["Python만 사용할 것"]},
            }
        ],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "preset": "implementer",
                    "overrides": {
                        "model": "o3-mini",
                        "limits": {"timeout": 600},
                    },
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "preset": "implementer",
  "overrides": {
    "model": "o3-mini",
    "limits": { "timeout": 600 }
  }
}
```

**관계:**
- `TeamPreset.agents`의 값 타입
- `PresetRegistry.merge_preset_with_overrides()`로 최종 `AgentPreset` 생성

---

### 3.7 `TeamTaskDef`

팀 프리셋 내에서 태스크를 정의한다. 어떤 에이전트가 어떤 작업을 수행하는지, 의존성은 무엇인지 명세한다.

```python
class TeamTaskDef(BaseModel):
    """팀 내 태스크 정의.

    팀 프리셋에서 작업 흐름을 정의할 때 사용한다.
    depends_on으로 DAG 의존성을 표현한다.
    """

    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="태스크 설명. 에이전트에 프롬프트로 전달됨",
        examples=["JWT 미들웨어 아키텍처를 설계하고 인터페이스를 정의하라"],
    )
    agent: str = Field(
        ...,
        min_length=1,
        description="이 태스크를 수행할 에이전트 이름 (TeamPreset.agents의 키)",
        examples=["architect", "implementer"],
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="선행 태스크 이름 목록 (TeamPreset.tasks의 키). DAG 의존성",
        examples=[["design"]],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "JWT 미들웨어 아키텍처를 설계하고 인터페이스를 정의하라",
                    "agent": "architect",
                    "depends_on": [],
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "description": "JWT 미들웨어 아키텍처를 설계하고 인터페이스를 정의하라",
  "agent": "architect",
  "depends_on": []
}
```

---

### 3.8 `TeamPreset`

팀 전체를 정의하는 프리셋. 에이전트 구성, 태스크 흐름, 워크플로우 방식, 결과 종합 전략을 하나의 단위로 묶는다.

```python
from pydantic import model_validator
from typing import Literal, Any


class TeamPreset(BaseModel):
    """팀 프리셋.

    에이전트 팀의 구성, 작업 흐름, 종합 전략을 정의한다.
    YAML 파일(presets/teams/*.yaml)로 저장·로딩된다.

    workflow 종류:
    - "parallel": 모든 태스크 병렬 실행 (depends_on 무시)
    - "sequential": 정의 순서대로 순차 실행
    - "dag": depends_on에 따라 DAG 순서로 실행

    synthesis_strategy 종류:
    - "narrative": 자연어 종합 보고서
    - "structured": 구조화된 JSON/마크다운 보고서
    - "checklist": 체크리스트 형태 보고서
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9\-]*$",
        description="팀 프리셋 고유 이름 (kebab-case)",
        examples=["feature-team", "incident-analysis"],
    )
    description: str = Field(
        default="",
        max_length=500,
        description="팀 프리셋 설명",
        examples=["기능 구현 팀: 설계→구현→리뷰→테스트"],
    )
    agents: dict[str, TeamAgentDef] = Field(
        ...,
        min_length=1,
        description="에이전트 이름 → 에이전트 정의 매핑",
    )
    tasks: dict[str, TeamTaskDef] = Field(
        ...,
        min_length=1,
        description="태스크 이름 → 태스크 정의 매핑",
    )
    workflow: Literal["parallel", "sequential", "dag"] = Field(
        default="parallel",
        description="작업 흐름 방식",
    )
    synthesis_strategy: Literal["narrative", "structured", "checklist"] = Field(
        default="narrative",
        description="결과 종합 전략",
    )

    @model_validator(mode="after")
    def validate_task_agent_references(self) -> "TeamPreset":
        """태스크의 agent 참조가 agents에 존재하는지 검증한다."""
        agent_names = set(self.agents.keys())
        for task_name, task_def in self.tasks.items():
            if task_def.agent not in agent_names:
                raise ValueError(
                    f"태스크 '{task_name}'의 agent '{task_def.agent}'가 "
                    f"agents에 정의되지 않음. 사용 가능: {agent_names}"
                )
        return self

    @model_validator(mode="after")
    def validate_depends_on_references(self) -> "TeamPreset":
        """태스크의 depends_on 참조가 tasks에 존재하는지 검증한다."""
        task_names = set(self.tasks.keys())
        for task_name, task_def in self.tasks.items():
            for dep in task_def.depends_on:
                if dep not in task_names:
                    raise ValueError(
                        f"태스크 '{task_name}'의 depends_on '{dep}'가 "
                        f"tasks에 정의되지 않음. 사용 가능: {task_names}"
                    )
                if dep == task_name:
                    raise ValueError(
                        f"태스크 '{task_name}'이 자기 자신에 의존할 수 없음"
                    )
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "feature-team",
                    "description": "기능 구현 팀: 설계→구현→리뷰",
                    "agents": {
                        "architect": {"preset": "architect", "overrides": {}},
                        "implementer": {"preset": "implementer", "overrides": {}},
                        "reviewer": {"preset": "reviewer", "overrides": {}},
                    },
                    "tasks": {
                        "design": {
                            "description": "아키텍처 설계 및 인터페이스 정의",
                            "agent": "architect",
                            "depends_on": [],
                        },
                        "implement": {
                            "description": "설계에 따른 구현",
                            "agent": "implementer",
                            "depends_on": ["design"],
                        },
                        "review": {
                            "description": "코드 리뷰",
                            "agent": "reviewer",
                            "depends_on": ["implement"],
                        },
                    },
                    "workflow": "dag",
                    "synthesis_strategy": "narrative",
                }
            ]
        }
    }
```

**YAML 프리셋 예시 (`presets/teams/feature-team.yaml`):**

```yaml
name: feature-team
description: "기능 구현 팀: 설계→구현→리뷰"
workflow: dag
synthesis_strategy: narrative

agents:
  architect:
    preset: architect
  implementer:
    preset: implementer
    overrides:
      model: claude-sonnet-4-20250514
  reviewer:
    preset: reviewer

tasks:
  design:
    description: "아키텍처 설계 및 인터페이스 정의"
    agent: architect
  implement:
    description: "설계에 따른 구현"
    agent: implementer
    depends_on: [design]
  review:
    description: "코드 리뷰"
    agent: reviewer
    depends_on: [implement]
```

**YAML 프리셋 예시 (`presets/teams/incident-analysis.yaml`):**

```yaml
name: incident-analysis
description: "인시던트 분석 팀: ELK+Grafana+K8s 병렬 분석 → 종합 보고서"
workflow: parallel
synthesis_strategy: structured

agents:
  elk-analyst:
    preset: elk-analyst
  grafana-analyst:
    preset: grafana-analyst
  k8s-analyst:
    preset: k8s-analyst

tasks:
  analyze-logs:
    description: "ELK 로그에서 에러 패턴 분석"
    agent: elk-analyst
  analyze-metrics:
    description: "Grafana 메트릭 이상치 분석"
    agent: grafana-analyst
  analyze-cluster:
    description: "K8s 클러스터 상태 점검"
    agent: k8s-analyst
```

**JSON 직렬화 예시:**

```json
{
  "name": "feature-team",
  "description": "기능 구현 팀: 설계→구현→리뷰",
  "agents": {
    "architect": { "preset": "architect", "overrides": {} },
    "implementer": { "preset": "implementer", "overrides": {} },
    "reviewer": { "preset": "reviewer", "overrides": {} }
  },
  "tasks": {
    "design": {
      "description": "아키텍처 설계 및 인터페이스 정의",
      "agent": "architect",
      "depends_on": []
    },
    "implement": {
      "description": "설계에 따른 구현",
      "agent": "implementer",
      "depends_on": ["design"]
    },
    "review": {
      "description": "코드 리뷰",
      "agent": "reviewer",
      "depends_on": ["implement"]
    }
  },
  "workflow": "dag",
  "synthesis_strategy": "narrative"
}
```

**관계:**
- `PresetRegistry.load_team_preset()`으로 로딩
- `OrchestratorEngine.submit_task(team_preset=)`에서 참조됨
- `TeamPlanner`가 자동 팀 구성 시 동적으로 생성할 수 있음
- `agents` 값의 `preset`은 `AgentPreset.name`을 참조
- `Pipeline.team_preset`에 이름이 저장됨

---

## 4. `core/queue/models.py` — 칸반 큐 모델

### 4.1 `TaskState`

칸반 보드의 태스크 상태를 나타내는 열거형.

```python
from enum import StrEnum


class TaskState(StrEnum):
    """칸반 보드 태스크 상태.

    상태 전이 규칙:
    - BACKLOG → TODO: 의존성 충족 시 자동 전이
    - TODO → IN_PROGRESS: AgentWorker가 claim 시
    - IN_PROGRESS → DONE: 성공 완료 시
    - IN_PROGRESS → FAILED: 실패 시 (max_retries 초과)
    - IN_PROGRESS → TODO: 실패 시 재시도 (retry_count < max_retries)
    """

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
```

---

### 4.2 `TaskItem`

칸반 보드의 개별 태스크. 상태, 의존성, 할당, 결과를 추적한다.

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Any


class TaskItem(BaseModel):
    """칸반 보드 태스크 아이템.

    TaskBoard에서 관리하는 개별 작업 단위.
    에이전트별 레인에 배치되고, AgentWorker가 소비한다.
    """

    id: str = Field(
        ...,
        min_length=1,
        description="태스크 고유 ID. UUID4 형식",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="태스크 제목 (사람이 읽을 수 있는 짧은 설명)",
        examples=["JWT 미들웨어 구현"],
    )
    description: str = Field(
        default="",
        max_length=5000,
        description="태스크 상세 설명. 에이전트에 프롬프트로 전달됨",
    )
    lane: str = Field(
        ...,
        min_length=1,
        description="칸반 레인 이름. 보통 에이전트 프리셋 이름과 동일",
        examples=["implementer", "architect"],
    )
    state: TaskState = Field(
        default=TaskState.BACKLOG,
        description="현재 태스크 상태",
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="우선순위 (0=기본, 높을수록 우선)",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="선행 태스크 ID 목록. 모두 DONE이어야 TODO로 전이",
    )
    assigned_to: str | None = Field(
        default=None,
        description="현재 할당된 AgentWorker ID. None이면 미할당",
    )
    result: str = Field(
        default="",
        description="실행 결과 텍스트. DONE 시 AgentResult.output 저장",
    )
    error: str = Field(
        default="",
        description="마지막 에러 메시지. FAILED 시 저장",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="현재까지 재시도 횟수",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="최대 재시도 횟수. 초과 시 FAILED",
    )
    pipeline_id: str = Field(
        default="",
        description="이 태스크가 속한 Pipeline ID",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="태스크 생성 시각 (UTC)",
    )
    started_at: datetime | None = Field(
        default=None,
        description="IN_PROGRESS 전이 시각",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="DONE 또는 FAILED 전이 시각",
    )

    @field_validator("depends_on")
    @classmethod
    def validate_no_self_dependency(cls, v: list[str], info) -> list[str]:
        """자기 자신에 대한 의존성을 검증한다."""
        task_id = info.data.get("id")
        if task_id and task_id in v:
            raise ValueError(f"태스크가 자기 자신에 의존할 수 없음: {task_id}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "title": "JWT 미들웨어 구현",
                    "description": "Express.js JWT 인증 미들웨어를 구현하라",
                    "lane": "implementer",
                    "state": "todo",
                    "priority": 5,
                    "depends_on": ["550e8400-e29b-41d4-a716-446655440001"],
                    "assigned_to": None,
                    "result": "",
                    "error": "",
                    "retry_count": 0,
                    "max_retries": 3,
                    "pipeline_id": "pipeline-001",
                    "created_at": "2026-04-05T10:00:00",
                    "started_at": None,
                    "completed_at": None,
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "JWT 미들웨어 구현",
  "description": "Express.js JWT 인증 미들웨어를 구현하라",
  "lane": "implementer",
  "state": "todo",
  "priority": 5,
  "depends_on": ["550e8400-e29b-41d4-a716-446655440001"],
  "assigned_to": null,
  "result": "",
  "error": "",
  "retry_count": 0,
  "max_retries": 3,
  "pipeline_id": "pipeline-001",
  "created_at": "2026-04-05T10:00:00",
  "started_at": null,
  "completed_at": null
}
```

**관계:**
- `TaskBoard`가 관리하는 핵심 엔티티
- `AgentWorker`가 `claim()` → `complete()`/`fail()` 생명주기를 실행
- `Pipeline.subtasks`의 `SubTask`와 1:1 대응 (SubTask.task_id = TaskItem.id)
- `OrchestratorEvent.data`에 상태 변화 정보로 포함됨

---

## 5. `core/models/pipeline.py` — 파이프라인 모델

### 5.1 `PipelineStatus`

파이프라인(전체 태스크) 상태를 나타내는 열거형.

```python
from enum import StrEnum


class PipelineStatus(StrEnum):
    """파이프라인 상태.

    상태 전이 규칙:
    - PENDING → PLANNING: 태스크 분해 시작
    - PLANNING → RUNNING: 서브태스크를 TaskBoard에 투입
    - RUNNING → SYNTHESIZING: 모든 서브태스크 완료
    - SYNTHESIZING → COMPLETED: 종합 보고서 생성 완료
    - RUNNING → PARTIAL_FAILURE: 일부 서브태스크 실패 (나머지 성공)
    - PARTIAL_FAILURE → SYNTHESIZING: 부분 결과로 종합 진행
    - RUNNING → FAILED: 모든 서브태스크 실패 또는 치명적 오류
    - * → CANCELLED: 사용자 취소
    """

    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

### 5.2 `SubTask`

파이프라인 내 서브태스크. `TeamPlanner`가 분해한 개별 작업 단위이며, `TaskItem`과 1:1 대응된다.

```python
from pydantic import BaseModel, Field
from typing import Literal


class SubTask(BaseModel):
    """파이프라인 서브태스크.

    TeamPlanner가 분해한 개별 작업 단위.
    TaskBoard의 TaskItem과 1:1 대응되며, task_id로 연결된다.
    """

    id: str = Field(
        ...,
        description="서브태스크 고유 ID. UUID4 형식",
        examples=["sub-001"],
    )
    task_id: str = Field(
        default="",
        description="대응되는 TaskItem ID. TaskBoard에 투입 후 설정됨",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="서브태스크 설명. TaskItem.description으로 복사됨",
    )
    assigned_cli: Literal["claude", "codex", "gemini"] | None = Field(
        default=None,
        description="할당된 CLI. None이면 AgentPreset.preferred_cli 사용",
    )
    assigned_preset: str = Field(
        default="",
        description="할당된 AgentPreset 이름",
        examples=["implementer", "architect"],
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="우선순위 (0=기본, 높을수록 우선)",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="선행 서브태스크 ID 목록",
    )
    status: PipelineStatus = Field(
        default=PipelineStatus.PENDING,
        description="서브태스크 현재 상태",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "sub-001",
                    "task_id": "550e8400-e29b-41d4-a716-446655440000",
                    "description": "JWT 토큰 검증 미들웨어 구현",
                    "assigned_cli": "claude",
                    "assigned_preset": "implementer",
                    "priority": 5,
                    "depends_on": [],
                    "status": "pending",
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "id": "sub-001",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "description": "JWT 토큰 검증 미들웨어 구현",
  "assigned_cli": "claude",
  "assigned_preset": "implementer",
  "priority": 5,
  "depends_on": [],
  "status": "pending"
}
```

---

### 5.3 `FileChange`

에이전트가 변경한 파일 하나의 정보.

```python
from typing import Literal


class FileChange(BaseModel):
    """파일 변경 정보.

    FileDiffCollector가 에이전트 실행 전후 스냅샷을 비교하여 생성한다.
    """

    path: str = Field(
        ...,
        min_length=1,
        description="변경된 파일의 상대 경로 (worktree 기준)",
        examples=["src/middleware/auth.ts"],
    )
    change_type: Literal["added", "modified", "deleted"] = Field(
        ...,
        description="변경 유형",
    )
    content: str = Field(
        default="",
        description="변경 후 파일 전체 내용. deleted인 경우 빈 문자열",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "src/middleware/auth.ts",
                    "change_type": "added",
                    "content": "import jwt from 'jsonwebtoken';\n\nexport function authMiddleware(req, res, next) {\n  // ...\n}",
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "path": "src/middleware/auth.ts",
  "change_type": "added",
  "content": "import jwt from 'jsonwebtoken';\n\nexport function authMiddleware(req, res, next) {\n  // ...\n}"
}
```

---

### 5.4 `WorkerResult`

개별 서브태스크의 실행 결과. `AgentResult`를 포함하되, 서브태스크 메타데이터와 파일 변경 정보를 추가한다.

```python
from typing import Literal


class WorkerResult(BaseModel):
    """서브태스크 실행 결과.

    AgentWorker가 서브태스크를 완료한 후 생성한다.
    AgentResult의 주요 필드를 포함하고, 파일 변경 정보를 추가한다.
    """

    subtask_id: str = Field(
        ...,
        description="대응되는 SubTask ID",
        examples=["sub-001"],
    )
    executor_type: Literal["cli", "mcp", "mock"] = Field(
        ...,
        description="사용된 실행기 유형",
    )
    cli: str | None = Field(
        default=None,
        description="사용된 CLI 이름. executor_type='cli'일 때만 유효",
        examples=["claude", "codex", "gemini"],
    )
    output: str = Field(
        default="",
        description="에이전트 출력 텍스트 (AgentResult.output에서 복사)",
    )
    files_changed: list[FileChange] = Field(
        default_factory=list,
        description="변경된 파일 목록. FileDiffCollector가 수집",
    )
    tokens_used: int = Field(
        default=0,
        ge=0,
        description="소비된 토큰 수",
    )
    duration_ms: int = Field(
        default=0,
        ge=0,
        description="실행 소요 시간 (밀리초)",
    )
    error: str = Field(
        default="",
        description="에러 메시지. 실패 시 저장",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "subtask_id": "sub-001",
                    "executor_type": "cli",
                    "cli": "claude",
                    "output": "JWT 미들웨어를 구현했습니다.",
                    "files_changed": [
                        {
                            "path": "src/middleware/auth.ts",
                            "change_type": "added",
                            "content": "// JWT middleware code...",
                        }
                    ],
                    "tokens_used": 3420,
                    "duration_ms": 45200,
                    "error": "",
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "subtask_id": "sub-001",
  "executor_type": "cli",
  "cli": "claude",
  "output": "JWT 미들웨어를 구현했습니다.",
  "files_changed": [
    {
      "path": "src/middleware/auth.ts",
      "change_type": "added",
      "content": "// JWT middleware code..."
    }
  ],
  "tokens_used": 3420,
  "duration_ms": 45200,
  "error": ""
}
```

**관계:**
- `Pipeline.results`에 수집됨
- `Synthesizer.synthesize()`의 입력으로 사용됨
- `subtask_id`로 `SubTask`와 연결됨

---

### 5.5 `Pipeline`

하나의 사용자 태스크 전체 파이프라인. 분해, 실행, 종합의 생명주기를 추적한다.

```python
from datetime import datetime


class Pipeline(BaseModel):
    """태스크 파이프라인.

    사용자가 제출한 하나의 태스크에 대한 전체 생명주기를 추적한다.
    분해(planning) → 실행(running) → 종합(synthesizing) → 완료(completed)

    API 응답의 핵심 엔티티이며, GET /api/tasks/{id}로 조회된다.
    """

    task_id: str = Field(
        ...,
        description="파이프라인 고유 ID. UUID4 형식",
        examples=["pipeline-550e8400"],
    )
    task: str = Field(
        ...,
        min_length=1,
        description="사용자가 제출한 원본 태스크 설명",
        examples=["JWT 인증 미들웨어 구현"],
    )
    status: PipelineStatus = Field(
        default=PipelineStatus.PENDING,
        description="파이프라인 현재 상태",
    )
    team_preset: str = Field(
        default="",
        description="사용된 TeamPreset 이름. 빈 문자열이면 자동 구성",
    )
    target_repo: str = Field(
        default="",
        description="대상 리포지토리 경로. 코딩 태스크에서 사용",
        examples=["./my-project", "/home/user/project"],
    )
    subtasks: list[SubTask] = Field(
        default_factory=list,
        description="분해된 서브태스크 목록",
    )
    results: list[WorkerResult] = Field(
        default_factory=list,
        description="서브태스크 실행 결과 목록",
    )
    synthesis: str = Field(
        default="",
        description="Synthesizer가 생성한 종합 보고서",
    )
    merged: bool = Field(
        default=False,
        description="worktree 변경사항이 target branch에 merge되었는지 여부",
    )
    error: str = Field(
        default="",
        description="파이프라인 레벨 에러 메시지",
    )
    started_at: datetime | None = Field(
        default=None,
        description="파이프라인 시작 시각 (PLANNING 전이 시)",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="파이프라인 완료 시각 (COMPLETED/FAILED/CANCELLED 전이 시)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "pipeline-550e8400",
                    "task": "JWT 인증 미들웨어 구현",
                    "status": "completed",
                    "team_preset": "feature-team",
                    "target_repo": "./my-project",
                    "subtasks": [
                        {
                            "id": "sub-001",
                            "task_id": "task-001",
                            "description": "아키텍처 설계",
                            "assigned_cli": "claude",
                            "assigned_preset": "architect",
                            "priority": 5,
                            "depends_on": [],
                            "status": "completed",
                        }
                    ],
                    "results": [
                        {
                            "subtask_id": "sub-001",
                            "executor_type": "cli",
                            "cli": "claude",
                            "output": "설계 완료",
                            "files_changed": [],
                            "tokens_used": 2100,
                            "duration_ms": 30000,
                            "error": "",
                        }
                    ],
                    "synthesis": "# JWT 미들웨어 구현 보고서\n\n...",
                    "merged": True,
                    "error": "",
                    "started_at": "2026-04-05T10:00:00",
                    "completed_at": "2026-04-05T10:05:30",
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "task_id": "pipeline-550e8400",
  "task": "JWT 인증 미들웨어 구현",
  "status": "completed",
  "team_preset": "feature-team",
  "target_repo": "./my-project",
  "subtasks": [
    {
      "id": "sub-001",
      "task_id": "task-001",
      "description": "아키텍처 설계",
      "assigned_cli": "claude",
      "assigned_preset": "architect",
      "priority": 5,
      "depends_on": [],
      "status": "completed"
    }
  ],
  "results": [
    {
      "subtask_id": "sub-001",
      "executor_type": "cli",
      "cli": "claude",
      "output": "설계 완료",
      "files_changed": [],
      "tokens_used": 2100,
      "duration_ms": 30000,
      "error": ""
    }
  ],
  "synthesis": "# JWT 미들웨어 구현 보고서\n\n...",
  "merged": true,
  "error": "",
  "started_at": "2026-04-05T10:00:00",
  "completed_at": "2026-04-05T10:05:30"
}
```

**관계:**
- `OrchestratorEngine.submit_task()`의 반환 타입
- `GET /api/tasks/{id}` 응답 본문
- `subtasks`의 각 `SubTask`는 `TaskBoard`의 `TaskItem`과 1:1 대응
- `results`의 각 `WorkerResult`는 `subtask_id`로 `SubTask`와 연결
- `team_preset`은 `TeamPreset.name`을 참조

---

## 6. `core/events/types.py` — 이벤트 타입

### 6.1 `EventType`

시스템에서 발생하는 모든 이벤트 유형.

```python
from enum import StrEnum


class EventType(StrEnum):
    """시스템 이벤트 유형.

    EventBus를 통해 발행되며, WebSocket으로 실시간 전달된다.
    각 이벤트는 OrchestratorEvent 인스턴스로 래핑된다.
    """

    # 파이프라인 생명주기
    PIPELINE_CREATED = "pipeline.created"
    PIPELINE_PLANNING = "pipeline.planning"
    PIPELINE_RUNNING = "pipeline.running"
    PIPELINE_SYNTHESIZING = "pipeline.synthesizing"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"
    PIPELINE_CANCELLED = "pipeline.cancelled"

    # 태스크 보드
    TASK_SUBMITTED = "task.submitted"
    TASK_READY = "task.ready"              # BACKLOG → TODO (의존성 충족)
    TASK_CLAIMED = "task.claimed"           # TODO → IN_PROGRESS (워커 할당)
    TASK_COMPLETED = "task.completed"       # IN_PROGRESS → DONE
    TASK_FAILED = "task.failed"             # IN_PROGRESS → FAILED
    TASK_RETRYING = "task.retrying"         # IN_PROGRESS → TODO (재시도)

    # 에이전트 워커
    WORKER_STARTED = "worker.started"
    WORKER_STOPPED = "worker.stopped"
    WORKER_HEARTBEAT = "worker.heartbeat"

    # 에이전트 실행
    AGENT_EXECUTING = "agent.executing"     # CLI/MCP 실행 시작
    AGENT_OUTPUT = "agent.output"           # 중간 출력 (스트리밍)
    AGENT_COMPLETED = "agent.completed"     # 실행 완료
    AGENT_ERROR = "agent.error"             # 실행 에러

    # 폴백
    FALLBACK_TRIGGERED = "fallback.triggered"
    FALLBACK_SUCCEEDED = "fallback.succeeded"
    FALLBACK_EXHAUSTED = "fallback.exhausted"

    # Git worktree
    WORKTREE_CREATED = "worktree.created"
    WORKTREE_MERGED = "worktree.merged"
    WORKTREE_CLEANUP = "worktree.cleanup"
    WORKTREE_CONFLICT = "worktree.conflict"

    # 종합
    SYNTHESIS_STARTED = "synthesis.started"
    SYNTHESIS_COMPLETED = "synthesis.completed"

    # 시스템
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH = "system.health"
```

---

### 6.2 `OrchestratorEvent`

시스템 이벤트 데이터 모델. EventBus를 통해 발행되고, WebSocket으로 전달된다.

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any


class OrchestratorEvent(BaseModel):
    """시스템 이벤트.

    EventBus에서 발행하고, 구독자(WebSocket, 로그, 대시보드)에 전달한다.
    모든 이벤트는 task_id로 파이프라인에 연결된다.
    """

    type: EventType = Field(
        ...,
        description="이벤트 유형",
    )
    task_id: str = Field(
        default="",
        description="관련 파이프라인 ID. 시스템 이벤트는 빈 문자열",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="이벤트 발생 시각 (UTC)",
    )
    node: str = Field(
        default="",
        description="이벤트 발생 노드/컴포넌트 이름",
        examples=["orchestrator", "worker-1", "claude-adapter"],
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="이벤트 페이로드. 이벤트 유형별로 구조가 다름",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "task.completed",
                    "task_id": "pipeline-550e8400",
                    "timestamp": "2026-04-05T10:05:30",
                    "node": "worker-1",
                    "data": {
                        "subtask_id": "sub-001",
                        "duration_ms": 45200,
                        "tokens_used": 3420,
                    },
                }
            ]
        }
    }
```

**JSON 직렬화 예시:**

```json
{
  "type": "task.completed",
  "task_id": "pipeline-550e8400",
  "timestamp": "2026-04-05T10:05:30",
  "node": "worker-1",
  "data": {
    "subtask_id": "sub-001",
    "duration_ms": 45200,
    "tokens_used": 3420
  }
}
```

**이벤트 유형별 `data` 필드 구조:**

| EventType | data 필드 |
|-----------|-----------|
| `pipeline.created` | `{"task": str, "team_preset": str}` |
| `pipeline.planning` | `{"subtask_count": int}` |
| `pipeline.completed` | `{"synthesis_length": int, "total_duration_ms": int}` |
| `task.submitted` | `{"task_id": str, "lane": str, "title": str}` |
| `task.claimed` | `{"task_id": str, "worker_id": str}` |
| `task.completed` | `{"subtask_id": str, "duration_ms": int, "tokens_used": int}` |
| `task.failed` | `{"subtask_id": str, "error": str, "retry_count": int}` |
| `task.retrying` | `{"subtask_id": str, "retry_count": int, "max_retries": int}` |
| `agent.executing` | `{"cli": str, "preset": str, "prompt_length": int}` |
| `agent.output` | `{"cli": str, "chunk": str}` |
| `agent.error` | `{"cli": str, "error_type": str, "message": str}` |
| `fallback.triggered` | `{"from_cli": str, "to_cli": str, "reason": str}` |
| `worktree.created` | `{"branch": str, "path": str}` |
| `worktree.merged` | `{"branch": str, "files_changed": int}` |
| `worktree.conflict` | `{"branch": str, "conflicting_files": list[str]}` |
| `worker.heartbeat` | `{"worker_id": str, "lane": str, "tasks_completed": int}` |
| `system.error` | `{"error_type": str, "message": str, "traceback": str}` |

**관계:**
- `EventBus.emit()`으로 발행
- `OrchestratorEngine.subscribe()`로 구독
- `GET /api/events` 응답의 리스트 항목
- `WS /ws/events`로 실시간 스트리밍

---

## 7. `core/auth/provider.py` — 인증 프로바이더

### 7.1 `AuthProvider` (ABC)

API 키 조회 추상 인터페이스. 다양한 키 저장소(환경 변수, Vault 등)를 통합한다.

```python
from abc import ABC, abstractmethod


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
            str | None: API 키 문자열. 없으면 None.
        """
        ...

    @abstractmethod
    def validate(self, provider: str) -> bool:
        """지정된 프로바이더의 API 키가 유효한지 확인한다.

        Args:
            provider: 프로바이더 이름.

        Returns:
            bool: 유효하면 True.
        """
        ...

    @abstractmethod
    def list_providers(self) -> list[str]:
        """사용 가능한 프로바이더 목록을 반환한다.

        Returns:
            list[str]: API 키가 설정된 프로바이더 이름 목록.
        """
        ...
```

---

### 7.2 `EnvAuthProvider`

환경 변수 기반 API 키 프로바이더. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` 등을 조회한다.

```python
import os


class EnvAuthProvider(AuthProvider):
    """환경 변수 기반 API 키 프로바이더.

    프로바이더 이름을 환경 변수 이름으로 매핑하여 키를 조회한다.

    매핑 규칙:
    - "anthropic" → ANTHROPIC_API_KEY
    - "openai" → OPENAI_API_KEY
    - "google" → GOOGLE_API_KEY (또는 GEMINI_API_KEY)

    Attributes:
        _provider_env_map: 프로바이더 → 환경 변수 이름 매핑
    """

    _provider_env_map: dict[str, list[str]] = {
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
            extra_mappings: 추가 프로바이더 → 환경 변수 매핑.
                예: {"custom": ["CUSTOM_API_KEY"]}
        """
        if extra_mappings:
            self._provider_env_map = {**self._provider_env_map, **extra_mappings}

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
```

**관계:**
- `OrchestratorConfig.auth_provider`에서 생성됨
- `AdapterFactory.create()`에서 `AdapterConfig.api_key` 설정에 사용됨
- CLI 어댑터별 프로바이더 매핑:
  - Claude Code → `anthropic`
  - Codex CLI → `openai`
  - Gemini CLI → `google`

---

## 8. `core/config/schema.py` — 설정

### 8.1 `OrchestratorConfig`

시스템 전체 설정. `pydantic-settings`를 사용하여 환경 변수, `.env` 파일, YAML에서 로딩한다.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal


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
```

**환경 변수 매핑 예시:**

| 환경 변수 | 필드 | 기본값 |
|-----------|------|--------|
| `ORCHESTRATOR_DEBUG` | `debug` | `False` |
| `ORCHESTRATOR_LOG_LEVEL` | `log_level` | `"INFO"` |
| `ORCHESTRATOR_DEFAULT_TIMEOUT` | `default_timeout` | `300` |
| `ORCHESTRATOR_MAX_CONCURRENT_AGENTS` | `max_concurrent_agents` | `5` |
| `ORCHESTRATOR_CLI_PRIORITY` | `cli_priority` | `["claude","codex","gemini"]` |
| `ORCHESTRATOR_PRESET_DIRS` | `preset_dirs` | `["./presets"]` |
| `ORCHESTRATOR_API_HOST` | `api_host` | `"0.0.0.0"` |
| `ORCHESTRATOR_API_PORT` | `api_port` | `8000` |
| `ORCHESTRATOR_PLANNER_MODEL` | `planner_model` | `"claude-sonnet-4-20250514"` |
| `ORCHESTRATOR_WORKTREE_BASE_DIR` | `worktree_base_dir` | `"/tmp/orchestrator-worktrees"` |
| `ORCHESTRATOR_AUTO_MERGE` | `auto_merge` | `True` |
| `ORCHESTRATOR_CHECKPOINT_ENABLED` | `checkpoint_enabled` | `True` |

**`.env` 파일 예시:**

```env
ORCHESTRATOR_DEBUG=true
ORCHESTRATOR_LOG_LEVEL=DEBUG
ORCHESTRATOR_DEFAULT_TIMEOUT=600
ORCHESTRATOR_MAX_CONCURRENT_AGENTS=3
ORCHESTRATOR_CLI_PRIORITY=["claude","codex","gemini"]
ORCHESTRATOR_API_PORT=9000
ORCHESTRATOR_PLANNER_MODEL=claude-sonnet-4-20250514
ORCHESTRATOR_WORKTREE_BASE_DIR=/tmp/my-worktrees
```

**JSON 직렬화 예시:**

```json
{
  "app_name": "agent-team-orchestrator",
  "debug": false,
  "log_level": "INFO",
  "default_timeout": 300,
  "max_concurrent_agents": 5,
  "default_max_retries": 3,
  "cli_priority": ["claude", "codex", "gemini"],
  "preset_dirs": ["./presets"],
  "api_host": "0.0.0.0",
  "api_port": 8000,
  "planner_model": "claude-sonnet-4-20250514",
  "synthesizer_model": "claude-sonnet-4-20250514",
  "worktree_base_dir": "/tmp/orchestrator-worktrees",
  "auto_merge": true,
  "checkpoint_enabled": true,
  "checkpoint_db_path": "./data/checkpoints.sqlite"
}
```

**관계:**
- `OrchestratorEngine.__init__()`에서 주입됨
- `AdapterFactory`가 `default_timeout`, `cli_priority` 사용
- `PresetRegistry`가 `preset_dirs` 사용
- `WorktreeManager`가 `worktree_base_dir` 사용
- `TaskBoard`가 `max_concurrent_agents`, `default_max_retries` 사용
- API 서버가 `api_host`, `api_port` 사용

---

## 9. 모델 관계 다이어그램

```
OrchestratorConfig
    │
    ├──→ OrchestratorEngine
    │       ├──→ PresetRegistry
    │       │       ├── AgentPreset ←── TeamAgentDef.preset (이름 참조)
    │       │       │   ├── PersonaDef
    │       │       │   ├── ToolAccess
    │       │       │   ├── AgentLimits
    │       │       │   └── MCPServerDef
    │       │       └── TeamPreset
    │       │           ├── TeamAgentDef (dict value)
    │       │           └── TeamTaskDef (dict value)
    │       │
    │       ├──→ TaskBoard
    │       │       └── TaskItem ←── SubTask.task_id (1:1 대응)
    │       │           └── TaskState (enum)
    │       │
    │       ├──→ AgentWorker
    │       │       └── AgentExecutor (ABC)
    │       │           └── CLIAgentExecutor
    │       │               ├── CLIAdapter
    │       │               ├── AdapterConfig
    │       │               └── mcp_config / skills (CLI 플래그)
    │       │
    │       ├──→ TeamPlanner → Pipeline
    │       │                   ├── SubTask
    │       │                   ├── WorkerResult
    │       │                   │   └── FileChange
    │       │                   └── PipelineStatus (enum)
    │       │
    │       ├──→ Synthesizer
    │       │       └── AgentResult (입력)
    │       │
    │       ├──→ EventBus
    │       │       └── OrchestratorEvent
    │       │           └── EventType (enum)
    │       │
    │       ├──→ WorktreeManager
    │       │
    │       ├──→ AdapterFactory
    │       │
    │       └──→ AuthProvider (ABC)
    │               └── EnvAuthProvider
    │
    └──→ API (FastAPI)
            └── Pipeline (응답)
```

**핵심 데이터 흐름:**

```
사용자 태스크 (str)
    ↓ OrchestratorEngine.submit_task()
Pipeline (PENDING)
    ↓ TeamPlanner.plan_team()
Pipeline (PLANNING) + SubTask[]
    ↓ TaskBoard.submit()
TaskItem[] (BACKLOG → TODO)
    ↓ AgentWorker.claim()
TaskItem (IN_PROGRESS)
    ↓ AgentExecutor.run()
AgentResult
    ↓ FileDiffCollector.collect_changes()
WorkerResult + FileChange[]
    ↓ TaskBoard.complete()
TaskItem (DONE)
    ↓ (모든 서브태스크 완료)
Pipeline (SYNTHESIZING)
    ↓ Synthesizer.synthesize()
Pipeline (COMPLETED) + synthesis (str)
    ↓ WorktreeManager.merge_to_target()
Pipeline (merged=True)
```
