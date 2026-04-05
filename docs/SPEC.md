# Agent Team Orchestrator — 프로젝트 기획서

> v2.0 | 2026-04-05
> 이전 버전 이력은 git log 참조

---

## 1. 비전

### 한 줄 정의

> **인간 팀과 동일한 방식으로 일하는 범용 AI 에이전트 팀 플랫폼.**

### 왜 만드는가

각 AI 에이전트(Claude, Codex, Gemini 등)는 개별적으로 강력하지만, 복잡한 작업은 **여러 전문가가 협업**해야 한다. 코딩, 인프라 운영, 장애 분석, 업무 대행 — 어떤 도메인이든 **팀 단위 협업**이 필요하다.

이 플랫폼은:
- **에이전트를 자유롭게 정의** (페르소나 + MCP 도구 + 제약)
- **팀을 자유롭게 구성** (프리셋 조합 또는 오케스트레이터 자동 구성)
- **칸반 보드 방식으로 작업 분배** (에이전트가 독립적으로 소비)
- **결과를 종합하여 보고** (Synthesizer)

### 사용 시나리오

```bash
# 코딩 팀: 설계→구현→리뷰
orchestrator run "JWT 인증 미들웨어 구현" --repo ./my-project --team feature-team

# 장애 분석 팀: ELK+Grafana+K8s 병렬 분석 → 종합 보고서
orchestrator run "프로덕션 API 500 에러 원인 분석" --team incident-analysis

# 인프라 운영: 모니터링→배포→검증
orchestrator run "v2.3.0 카나리 배포 진행" --team deploy-team

# 오케스트레이터 자동 구성: 팀 지정 없이
orchestrator run "사용자 인증 시스템 보안 감사"

# 웹 대시보드 (프론트엔드 dev 서버, API는 localhost:9000)
open http://localhost:3000
```

---

## 2. 기대 결과물

| 산출물 | 형태 | 설명 |
|--------|------|------|
| **orchestrator CLI** | Python 패키지 | `pip install agent-team-orchestrator` |
| **API 서버** | FastAPI | REST + WebSocket, 칸반 보드 API 포함 |
| **웹 대시보드** | React SPA | 칸반 보드 뷰, 에이전트 상태, 결과 뷰어 |
| **프리셋 시스템** | YAML | 에이전트/팀 프리셋 정의·저장·재사용 |
| **어댑터 SDK** | Python ABC | AgentExecutor로 새 에이전트 유형 추가 |

---

## 3. 아키텍처

### 3-Layer 분리

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  CLI (typer)  │  │  Web (React) │  │  MCP / SDK   │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       └────────┬────────┴─────────┬────────┘
                │    Interface     │
         ┌──────┴──────┐   ┌──────┴──────┐
         │  REST API   │   │  WebSocket  │
         └──────┬──────┘   └──────┬──────┘
                │      API       │
         ┌──────┴────────────────┴──────┐
         │      OrchestratorEngine       │
         └──────┬────────────────────────┘
                │      Core
         ┌──────┴────────────────────────┐
         │  TaskBoard │ AgentExecutor    │
         │  Presets   │ Synthesizer      │
         │  Worktree  │ Events           │
         └───────────────────────────────┘
```

### Hybrid 오케스트레이션 모델

```
사용자 태스크
    ↓
[Orchestrator LLM] ← 태스크 분해 + 팀 구성 (LangGraph)
    ↓
[TaskBoard] ← 칸반 보드에 서브태스크 투입
    ↓
[AgentWorker] ← 각 레인에서 독립 소비 (느슨한 결합)
    ↓
[Synthesizer] ← 결과 종합 보고
```

**경계 규칙:**
- LangGraph: LLM이 필요한 의사결정만 (태스크 분해, 품질 평가)
- TaskBoard: 기계적 분배만 (큐 관리, DAG 의존성, retry)
- 순서 관리: `depends_on` (데이터) — LangGraph edges 아님

---

## 4. 도메인 모델

### 에이전트 실행

```python
class AgentExecutor(ABC):
    """도메인 무관 에이전트 실행 인터페이스."""
    async def run(self, prompt, *, timeout=300, context=None) -> AgentResult
    async def health_check(self) -> bool
    executor_type: str  # "cli" | "mcp" | "mock"

# 구현체
CLIAgentExecutor    # Claude Code, Codex CLI, Gemini CLI (subprocess)
MCPAgentExecutor    # ELK 분석가, Grafana 모니터링, K8s 운영 (LLM + MCP tools)
```

### 프리셋

```python
class PersonaDef(BaseModel):
    role: str                        # "시니어 보안 감사자"
    goal: str
    backstory: str = ""
    constraints: list[str] = []

class AgentPreset(BaseModel):
    name: str
    persona: PersonaDef
    execution_mode: str = "cli"      # "cli" | "mcp"
    preferred_cli: str = "claude"
    mcp_servers: dict = {}
    tools: ToolAccess = ToolAccess()
    limits: AgentLimits = AgentLimits()

class TeamPreset(BaseModel):
    name: str
    agents: dict[str, TeamAgentDef]
    tasks: dict[str, TeamTaskDef]
    workflow: str = "parallel"
    synthesis_strategy: str = "narrative"
```

### 칸반 작업 큐

```python
class TaskState(StrEnum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"

class TaskItem(BaseModel):
    id: str
    title: str
    lane: str
    state: TaskState
    depends_on: list[str] = []
    assigned_to: str | None = None
    result: str = ""
    retry_count: int = 0
    max_retries: int = 3
    pipeline_id: str = ""
```

### 결과 종합

```python
class Synthesizer:
    strategy: str  # "narrative" | "structured" | "checklist"
    async def synthesize(self, results: list[AgentResult], task: str) -> str
```

---

## 5. API 스펙

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/tasks` | 태스크 제출 (team_preset, target_repo 옵션) |
| GET | `/api/tasks` | 파이프라인 목록 |
| GET | `/api/tasks/{id}` | 파이프라인 상세 |
| POST | `/api/tasks/{id}/resume` | 중단 태스크 재개 |
| DELETE | `/api/tasks/{id}` | 태스크 취소 |
| GET | `/api/board` | 칸반 보드 상태 |
| GET | `/api/board/lanes` | 레인 목록 |
| GET | `/api/board/tasks/{id}` | 보드 태스크 상세 |
| GET | `/api/agents` | 에이전트 상태 |
| GET | `/api/presets/agents` | 에이전트 프리셋 목록 |
| GET | `/api/presets/teams` | 팀 프리셋 목록 |
| POST | `/api/presets/agents` | 에이전트 프리셋 생성 |
| POST | `/api/presets/teams` | 팀 프리셋 생성 |
| GET | `/api/artifacts/{task_id}` | 아티팩트 목록 |
| GET | `/api/events` | 이벤트 히스토리 |
| GET | `/api/health` | 헬스 체크 |
| WS | `/ws/events` | 실시간 이벤트 스트림 |

---

## 6. Core Engine

```python
class OrchestratorEngine:
    """Core 계층 단일 진입점. API 계층은 이것만 의존."""

    # 태스크
    async def submit_task(self, task, *, team_preset=None, target_repo=None) -> Pipeline
    async def get_pipeline(self, task_id) -> Pipeline | None
    async def list_pipelines(self) -> list[Pipeline]
    async def cancel_task(self, task_id) -> bool
    async def resume_task(self, task_id) -> Pipeline

    # 프리셋
    def list_agent_presets(self) -> list[AgentPreset]
    def list_team_presets(self) -> list[TeamPreset]
    def save_agent_preset(self, preset) -> None
    def save_team_preset(self, preset) -> None

    # 보드
    def get_board_state(self) -> dict
    def list_agents(self) -> list[Agent]

    # 이벤트
    def subscribe(self, callback) -> None
    def get_events(self, task_id=None) -> list[Event]
```

---

## 7. 에러 체계

```
OrchestratorError
├── CLIError (Execution, Timeout, Parse, NotFound)
├── AuthError
├── WorktreeError
├── MergeConflictError
├── DecompositionError
└── AllProvidersFailedError
```

---

## 8. 디렉토리 구조

```
src/orchestrator/
├── core/
│   ├── executor/           # AgentExecutor ABC + CLI/MCP 구현
│   ├── queue/              # TaskBoard + AgentWorker (칸반)
│   ├── presets/            # PresetRegistry + 모델
│   ├── planner/            # TeamPlanner (LLM 기반 팀 구성)
│   ├── adapters/           # CLIAdapter (Claude/Codex/Gemini)
│   ├── worktree/           # Git worktree 격리
│   ├── context/            # ArtifactStore
│   ├── auth/               # AuthProvider + KeyPool
│   ├── events/             # EventBus + Synthesizer
│   ├── errors/             # 예외 계층
│   ├── models/             # Pydantic 스키마
│   └── engine.py           # OrchestratorEngine
├── api/                    # FastAPI (REST + WebSocket)
└── cli.py                  # typer thin client

frontend/                   # React 대시보드 (칸반 보드 뷰)

presets/                    # YAML 프리셋 번들
├── agents/                 # architect, implementer, elk-analyst, ...
└── teams/                  # feature-team, incident-analysis, ...
```

---

## 9. 성공 기준

| # | 기준 |
|---|------|
| 1 | 코딩: 분해→병렬 실행→merge→결과물 |
| 2 | 인시던트 분석: 다수 에이전트 병렬→종합 보고서 |
| 3 | 실패→폴백 작동 |
| 4 | 중단 후 resume |
| 5 | CLI와 웹 동일 동작 |
| 6 | 프리셋으로 팀 변경 (코드 수정 없이) |
| 7 | 커스텀 에이전트 추가 (AgentExecutor 구현만으로) |

---

## 10. 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.12+ |
| 오케스트레이션 | LangGraph (planning) + TaskBoard (execution) |
| API | FastAPI + WebSocket |
| 모델 | Pydantic v2 + pydantic-settings |
| CLI | Typer + httpx |
| 프론트엔드 | React + Vite + TypeScript |
| 린트/타입 | ruff + mypy (strict) |

---

## 11. Out of Scope (v1.0)

| 기능 | 시기 |
|------|------|
| MCP 서버 모드 | v2.0 |
| Docker 샌드박싱 | v2.0 |
| Vault 연동 | v2.0 |
| GitHub PR 자동 생성 | v1.5 |
| 멀티 테넌트 | v3.0 |
| 비용 추적 | N/A |
