# 아키텍처 명세서

> v1.0 | 2026-04-05
> 기반: `docs/SPEC.md` v2.0

---

## 목차

1. [3-Layer 아키텍처](#1-3-layer-아키텍처)
2. [Core 계층 상세](#2-core-계층-상세)
3. [Hybrid 오케스트레이션 모델](#3-hybrid-오케스트레이션-모델)
4. [컴포넌트 상호작용](#4-컴포넌트-상호작용)
5. [데이터 흐름](#5-데이터-흐름)
6. [동시성 모델](#6-동시성-모델)
7. [상태 관리](#7-상태-관리)
8. [배포 모델](#8-배포-모델)
9. [확장 포인트](#9-확장-포인트)

---

## 1. 3-Layer 아키텍처

### 아키텍처 다이어그램

```
═══════════════════════════════════════════════════════════════════════
 Layer 1: Interface (Presentation)
═══════════════════════════════════════════════════════════════════════
 ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
 │  CLI (typer)     │  │  Web (React SPA) │  │  External (MCP/SDK)  │
 │                  │  │                  │  │                      │
 │  orchestrator    │  │  http://host:3000│  │  Python import 또는  │
 │  run "태스크"    │  │  대시보드 + 칸반  │  │  MCP client 연결     │
 │                  │  │                  │  │                      │
 │  ► httpx로       │  │  ► fetch/WS로    │  │  ► 직접 Engine 호출  │
 │    API 호출      │  │    API 호출      │  │    또는 REST 호출    │
 └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘
          │                     │                       │
          ▼                     ▼                       ▼
═══════════════════════════════════════════════════════════════════════
 Layer 2: API (Transport)
═══════════════════════════════════════════════════════════════════════
 ┌──────────────────────────────────────────────────────────────────┐
 │                    FastAPI Application                           │
 │                                                                  │
 │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐ │
 │  │ REST Router │  │ WebSocket   │  │ Middleware               │ │
 │  │             │  │ Handler     │  │                          │ │
 │  │ /api/tasks  │  │ /ws/events  │  │ ► CORS                  │ │
 │  │ /api/board  │  │             │  │ ► Request logging        │ │
 │  │ /api/agents │  │ subscribe/  │  │ ► Error → JSON 변환     │ │
 │  │ /api/presets│  │ broadcast   │  │ ► (v2.0) Auth middleware │ │
 │  │ /api/events │  │             │  │                          │ │
 │  │ /api/health │  │             │  │                          │ │
 │  └──────┬──────┘  └──────┬──────┘  └──────────────────────────┘ │
 │         │                │                                       │
 │         └───────┬────────┘                                       │
 │                 │  OrchestratorEngine 의존 (DI)                   │
 └─────────────────┼────────────────────────────────────────────────┘
                   │
                   ▼
═══════════════════════════════════════════════════════════════════════
 Layer 3: Core (Business Logic)
═══════════════════════════════════════════════════════════════════════
 ┌──────────────────────────────────────────────────────────────────┐
 │                    OrchestratorEngine                            │
 │                    (Core 계층 단일 진입점)                        │
 │                                                                  │
 │  ┌──────────────────────────────────────────────────────────┐   │
 │  │ Planning (LangGraph)                                      │   │
 │  │  ► TaskDecomposer: 태스크 → 서브태스크 분해               │   │
 │  │  ► TeamPlanner: 에이전트 팀 자동 구성                     │   │
 │  │  ► QualityEvaluator: 결과 품질 평가                       │   │
 │  └──────────────┬───────────────────────────────────────────┘   │
 │                 │                                                │
 │  ┌──────────────▼───────────────────────────────────────────┐   │
 │  │ Execution (TaskBoard + AgentWorker)                       │   │
 │  │  ► TaskBoard: 칸반 보드 (큐 관리, DAG 의존성, retry)      │   │
 │  │  ► AgentWorker: 레인별 태스크 소비, AgentExecutor 호출     │   │
 │  │  ► AgentExecutor: CLI 실행 추상화 (MCP/Skills는 CLI 플래그) │   │
 │  └──────────────┬───────────────────────────────────────────┘   │
 │                 │                                                │
 │  ┌──────────────▼───────────────────────────────────────────┐   │
 │  │ Support Services                                          │   │
 │  │  ► PresetRegistry: YAML 프리셋 로딩/검색                  │   │
 │  │  ► EventBus: 이벤트 발행/구독                             │   │
 │  │  ► Synthesizer: 결과 종합                                 │   │
 │  │  ► WorktreeManager: Git worktree 격리                     │   │
 │  │  ► ArtifactStore: 아티팩트 저장/조회                      │   │
 │  │  ► AuthProvider: 인증 키 관리                             │   │
 │  └──────────────────────────────────────────────────────────┘   │
 └──────────────────────────────────────────────────────────────────┘
```

### 각 계층의 역할과 제약

#### Layer 1: Interface

| 항목 | 내용 |
|------|------|
| **역할** | 사용자 입력을 받아 API 계층에 전달, 결과를 사용자에게 표시 |
| **구현체** | CLI (typer + httpx), Web (React + Vite), External (Python SDK, MCP client) |
| **의존** | API 계층만 의존 (HTTP/WS 프로토콜) |
| **제약** | Core 계층을 직접 import 불가. 반드시 API를 경유 |
| **예외** | External SDK는 `OrchestratorEngine`을 직접 임포트하여 in-process 사용 가능 |

#### Layer 2: API

| 항목 | 내용 |
|------|------|
| **역할** | HTTP/WS 프로토콜 처리, 요청 검증, 응답 직렬화, 에러 변환 |
| **구현체** | FastAPI application (`api/` 디렉토리) |
| **의존** | Core 계층의 `OrchestratorEngine` 인스턴스 (DI로 주입) |
| **제약** | 비즈니스 로직 불포함. Engine 메서드 호출 → 결과 직렬화만 수행 |
| **책임** | Pydantic 요청 모델 검증, HTTP 상태 코드 매핑, CORS, 로깅 미들웨어 |

#### Layer 3: Core

| 항목 | 내용 |
|------|------|
| **역할** | 모든 비즈니스 로직. 태스크 분해, 팀 구성, 작업 실행, 결과 종합 |
| **구현체** | `OrchestratorEngine` + 하위 컴포넌트 (`core/` 디렉토리) |
| **의존** | 외부 라이브러리만 (LangGraph, LiteLLM, Pydantic, asyncio). API/Interface 미의존 |
| **제약** | HTTP/WS 개념 불포함. 프로토콜 독립적 |
| **진입점** | `OrchestratorEngine` — API 계층은 이것만 의존 |

### 의존성 규칙

```
Interface → API → Core
    ×         ×      ×
   Core     Interface  API     (역방향 의존 금지)
```

- **Core는 API를 모른다**: `OrchestratorEngine`은 FastAPI import 없이 동작
- **API는 Interface를 모른다**: REST 라우터는 CLI/React의 존재를 모름
- **테스트 독립성**: Core 계층은 API 서버 없이 단위 테스트 가능

---

## 2. Core 계층 상세

### 디렉토리 구조와 모듈 책임

```
src/orchestrator/core/
├── engine.py              # OrchestratorEngine (단일 진입점)
├── executor/
│   ├── base.py            # AgentExecutor ABC
│   └── cli_executor.py    # CLIAgentExecutor (subprocess + MCP/Skills)
├── queue/
│   ├── board.py           # TaskBoard (칸반 보드 큐)
│   ├── models.py          # TaskItem, TaskState, Lane
│   └── worker.py          # AgentWorker (레인별 소비자)
├── planner/
│   ├── decomposer.py      # TaskDecomposer (LangGraph 태스크 분해)
│   └── team_planner.py    # TeamPlanner (자동 팀 구성)
├── presets/
│   ├── registry.py        # PresetRegistry (YAML 로딩, deep merge)
│   └── models.py          # PersonaDef, AgentPreset, TeamPreset
├── adapters/
│   ├── base.py            # CLIAdapter ABC
│   ├── claude.py          # ClaudeAdapter
│   ├── codex.py           # CodexAdapter
│   └── gemini.py          # GeminiAdapter
├── worktree/
│   ├── manager.py         # WorktreeManager
│   └── collector.py       # FileDiffCollector
├── context/
│   └── artifact_store.py  # ArtifactStore
├── auth/
│   ├── provider.py        # AuthProvider
│   └── key_pool.py        # KeyPool (v2.0 확장)
├── events/
│   ├── bus.py             # EventBus
│   ├── types.py           # EventType enum, Event model
│   └── synthesizer.py     # Synthesizer
├── errors/
│   └── exceptions.py      # 예외 계층 전체
└── models/
    └── schemas.py          # Pipeline, AgentResult, Config 등 Pydantic 스키마
```

### OrchestratorEngine 내부 구조

```python
class OrchestratorEngine:
    """Core 계층 단일 진입점.

    모든 컴포넌트를 소유하고, API 계층에 유일한 인터페이스를 제공한다.
    """

    # === 소유 컴포넌트 ===
    _board: TaskBoard              # 칸반 보드 (태스크 큐)
    _workers: dict[str, AgentWorker]  # 레인별 워커
    _decomposer: TaskDecomposer    # LangGraph 태스크 분해기
    _team_planner: TeamPlanner     # 자동 팀 구성
    _preset_registry: PresetRegistry  # 프리셋 레지스트리
    _event_bus: EventBus           # 이벤트 버스
    _synthesizer: Synthesizer      # 결과 종합
    _worktree_mgr: WorktreeManager # Git worktree 관리
    _artifact_store: ArtifactStore # 아티팩트 저장소
    _auth: AuthProvider            # 인증 관리
    _pipelines: dict[str, Pipeline]  # 활성 파이프라인 맵
    _checkpointer: SqliteSaver     # LangGraph 체크포인터

    # === Public API ===
    # 태스크
    async def submit_task(task, *, team_preset, target_repo, config) -> Pipeline
    async def get_pipeline(task_id) -> Pipeline | None
    async def list_pipelines(*, offset, limit, status) -> PaginatedResult[Pipeline]
    async def cancel_task(task_id) -> bool
    async def resume_task(task_id) -> Pipeline

    # 프리셋
    def list_agent_presets() -> list[AgentPreset]
    def list_team_presets() -> list[TeamPreset]
    def save_agent_preset(preset: AgentPreset) -> None
    def save_team_preset(preset: TeamPreset) -> None

    # 보드
    def get_board_state() -> BoardState
    def get_board_lanes() -> list[LaneSummary]
    def get_board_task(task_id) -> TaskItem | None
    def list_agents() -> list[AgentInfo]

    # 아티팩트
    def list_artifacts(task_id) -> list[ArtifactMeta]
    def get_artifact(task_id, path) -> bytes

    # 이벤트
    def subscribe(callback: Callable[[Event], Awaitable[None]]) -> None
    def unsubscribe(callback) -> None
    def get_events(*, task_id, limit, offset, event_type) -> PaginatedResult[Event]

    # 헬스
    async def health_check() -> HealthStatus
```

---

## 3. Hybrid 오케스트레이션 모델

### 개념

Hybrid 모델은 두 가지 실행 메커니즘을 명확히 분리한다:

| 영역 | 엔진 | 역할 | 특징 |
|------|------|------|------|
| **Planning** | LangGraph | LLM이 필요한 의사결정 | 태스크 분해, 팀 구성, 품질 평가 |
| **Execution** | TaskBoard + AgentWorker | 기계적 분배 | 큐 관리, DAG 의존성 해소, retry, 워커 디스패치 |

### 전체 흐름 다이어그램

```
사용자 입력: "JWT 인증 미들웨어 구현"
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│                  OrchestratorEngine                        │
│                                                            │
│   [1] Pipeline 생성                                        │
│       status: "planning"                                   │
│       │                                                    │
│       ▼                                                    │
│   ┌───────────────────────────┐                            │
│   │ PLANNING PHASE (LangGraph)│                            │
│   │                           │                            │
│   │ [2] TeamPlanner           │                            │
│   │     team_preset 있으면    │                            │
│   │     → 프리셋 로딩        │                            │
│   │     없으면               │                            │
│   │     → LLM 자동 팀 구성   │                            │
│   │     │                     │                            │
│   │     ▼                     │                            │
│   │ [3] TaskDecomposer        │                            │
│   │     태스크 → 서브태스크   │                            │
│   │     depends_on 관계 결정  │                            │
│   │     │                     │                            │
│   │     ▼                     │                            │
│   │ [4] Board 투입            │                            │
│   │     서브태스크 → TaskItem │                            │
│   │     레인 할당             │                            │
│   └───────────┬───────────────┘                            │
│               │                                            │
│               ▼                                            │
│   ┌───────────────────────────┐                            │
│   │ EXECUTION PHASE (Board)   │                            │
│   │                           │                            │
│   │ [5] TaskBoard             │                            │
│   │     DAG 의존성 해소       │   status: "running"        │
│   │     todo → in_progress    │                            │
│   │     │                     │                            │
│   │     ▼                     │                            │
│   │ [6] AgentWorker (N개)     │                            │
│   │     레인에서 태스크 소비  │                            │
│   │     │                     │                            │
│   │     ▼                     │                            │
│   │ [7] AgentExecutor         │                            │
│   │     CLI subprocess 실행   │                            │
│   │     (persona+MCP+skills   │                            │
│   │      → CLI 플래그)        │                            │
│   │     │                     │                            │
│   │     ├─ 성공 → done        │                            │
│   │     └─ 실패 → retry/fail  │                            │
│   │                           │                            │
│   │ [8] 모든 태스크 완료?     │                            │
│   │     ├─ 아니오 → [5]로    │                            │
│   │     └─ 예 → [9]로        │                            │
│   └───────────┬───────────────┘                            │
│               │                                            │
│               ▼                                            │
│   ┌───────────────────────────┐                            │
│   │ SYNTHESIS PHASE           │                            │
│   │                           │                            │
│   │ [9] Synthesizer           │                            │
│   │     결과 수집 + LLM 종합  │                            │
│   │     │                     │                            │
│   │     ▼                     │                            │
│   │ [10] Pipeline 완료        │   status: "completed"      │
│   │      result 저장          │                            │
│   └───────────────────────────┘                            │
│                                                            │
└───────────────────────────────────────────────────────────┘
```

### Pipeline 상태 전이

```
              ┌───────────┐
              │  planning  │  ← 초기 상태 (submit_task)
              └─────┬─────┘
                    │ 분해 성공
                    ▼
              ┌───────────┐
         ┌────│  running   │────┐
         │    └─────┬─────┘    │
         │          │          │
    실패 (재시도    │ 모든      │ cancel_task()
     소진 후)      │ 태스크     │
         │          │ 완료      │
         ▼          ▼          ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │  failed   │ │completed │ │cancelled │
   └─────┬────┘ └──────────┘ └──────────┘
         │
         │ resume_task()
         ▼
   ┌──────────┐
   │  running  │  (체크포인트에서 재개)
   └──────────┘
```

**상태 전이 규칙:**

| 현재 상태 | 가능한 전이 | 트리거 |
|----------|------------|--------|
| `planning` | `running` | 태스크 분해 + 팀 구성 완료 |
| `planning` | `failed` | 분해 실패 (DecompositionError) |
| `running` | `completed` | 모든 서브태스크 done + 종합 완료 |
| `running` | `failed` | 임계 서브태스크 실패 (재시도 소진) |
| `running` | `cancelled` | cancel_task() 호출 |
| `failed` | `running` | resume_task() 호출 |
| `paused` | `running` | resume_task() 호출 |
| `completed` | (종단 상태) | — |
| `cancelled` | (종단 상태) | — |

### LangGraph Planning 그래프

```
                START
                  │
                  ▼
        ┌─────────────────┐
        │  compose_team    │  ← team_preset 로딩 또는 LLM 자동 구성
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ decompose_task   │  ← LLM으로 서브태스크 분해
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ submit_to_board  │  ← TaskBoard에 서브태스크 투입
        └────────┬────────┘
                 │
                 ▼
                END
```

**compose_team 노드:**

```python
async def compose_team(state: PlanningState) -> dict:
    """팀 구성.

    team_preset이 있으면 PresetRegistry에서 로딩.
    없으면 TeamPlanner(LLM)이 태스크 분석 후 자동 구성.

    Returns:
        {"team": TeamComposition, "agents": list[AgentConfig]}
    """
```

**decompose_task 노드:**

```python
async def decompose_task(state: PlanningState) -> dict:
    """태스크 분해.

    LLM에게 태스크와 팀 구성을 입력하여 서브태스크 목록 생성.
    각 서브태스크에 레인(역할), 의존성, 설명 포함.

    Returns:
        {"subtasks": list[SubTaskPlan]}
    """
```

**submit_to_board 노드:**

```python
async def submit_to_board(state: PlanningState) -> dict:
    """서브태스크를 TaskBoard에 투입.

    SubTaskPlan → TaskItem 변환 후 board.submit().
    워커 시작 시그널 발행.

    Returns:
        {"board_submitted": True}
    """
```

### TaskBoard 상태 전이 (서브태스크)

```
  ┌──────────┐
  │ backlog  │  ← 초기 투입 (depends_on 미충족)
  └────┬─────┘
       │ 의존 태스크 모두 done
       ▼
  ┌──────────┐
  │   todo    │  ← 실행 가능 (워커 대기)
  └────┬─────┘
       │ AgentWorker가 꺼내감
       ▼
  ┌──────────┐
  │in_progress│ ← AgentExecutor 실행 중
  └────┬─────┘
       │
       ├─ 성공 ──────────────────▶ ┌──────┐
       │                           │ done │
       │                           └──────┘
       │
       └─ 실패 ──┬── retry_count < max_retries
                 │         │
                 │         ▼
                 │   ┌──────────┐
                 │   │   todo    │  (retry_count++)
                 │   └──────────┘
                 │
                 └── retry_count >= max_retries
                           │
                           ▼
                     ┌──────────┐
                     │  failed  │
                     └──────────┘
```

---

## 4. 컴포넌트 상호작용

### 컴포넌트 의존 관계도

```
┌─────────────────────────────────────────────────────────────────┐
│                      OrchestratorEngine                          │
│                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐  │
│  │ TeamPlanner   │────▶│PresetRegistry│     │  AuthProvider     │  │
│  └──────┬───────┘     └──────────────┘     └────────┬─────────┘  │
│         │                                           │             │
│         │ team 구성                                  │ 키 제공     │
│         ▼                                           ▼             │
│  ┌──────────────┐                          ┌──────────────────┐  │
│  │TaskDecomposer│                          │  CLIAdapter(s)    │  │
│  └──────┬───────┘                          │  ┌────────────┐  │  │
│         │ 서브태스크                        │  │ Claude     │  │  │
│         ▼                                  │  │ Codex      │  │  │
│  ┌──────────────┐    ┌──────────────┐     │  │ Gemini     │  │  │
│  │  TaskBoard    │◀──▶│ AgentWorker  │─────▶│  └────────────┘  │  │
│  │              │    │  (per lane)  │     └────────┬─────────┘  │
│  │  ► lanes     │    │              │              │             │
│  │  ► DAG 관리  │    │  ► 태스크    │              │ subprocess  │
│  │  ► 상태 전이 │    │    소비/실행  │              ▼             │
│  └──────┬───────┘    └──────┬───────┘     ┌──────────────────┐  │
│         │                   │              │  AgentExecutor    │  │
│         │                   │              │  (CLI+MCP+Skills) │  │
│         │                   │              └──────────────────┘  │
│         │                   │                                     │
│         │                   │ 실행 결과                           │
│         │                   ▼                                     │
│         │            ┌──────────────┐     ┌──────────────────┐  │
│         │            │ArtifactStore │     │WorktreeManager   │  │
│         │            └──────────────┘     └──────────────────┘  │
│         │                                                        │
│         │ 모든 태스크 완료                                       │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ Synthesizer   │                                                │
│  └──────┬───────┘                                                │
│         │ 결과 종합                                               │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │  EventBus     │ ──────────▶ WebSocket subscribers              │
│  └──────────────┘                                                │
└──────────────────────────────────────────────────────────────────┘
```

### 핵심 상호작용 시퀀스

#### 시퀀스 1: 태스크 제출 → 실행 완료

```
Client          API              Engine         Planner       Board        Worker      Executor
  │              │                 │               │            │            │            │
  │─POST /tasks─▶│                │               │            │            │            │
  │              │─submit_task()─▶│               │            │            │            │
  │              │                │─compose_team()▶│            │            │            │
  │              │                │               │─load_preset│            │            │
  │              │                │◀──TeamConfig──│            │            │            │
  │              │                │─decompose()──▶│            │            │            │
  │              │                │◀─subtasks─────│            │            │            │
  │              │                │─submit()──────────────────▶│            │            │
  │              │                │               │            │─notify()──▶│            │
  │◀─201 Pipeline│               │               │            │            │            │
  │              │                │               │            │◀─poll()────│            │
  │              │                │               │            │─TaskItem──▶│            │
  │              │                │               │            │            │─run()─────▶│
  │              │                │               │            │            │            │─subprocess
  │              │                │               │            │            │◀─result────│
  │              │                │               │            │◀─done()────│            │
  │              │                │               │   (다음 태스크 반복)      │            │
  │              │                │               │            │            │            │
  │              │                │◀─all_done()───────────────│            │            │
  │              │                │─synthesize()──▶            │            │            │
  │              │                │◀─final_result─│            │            │            │
  │              │                │─emit(pipeline_completed)   │            │            │
```

#### 시퀀스 2: 서브태스크 실패 → 재시도 → 폴백

```
Worker          Executor         Board           EventBus
  │               │                │                │
  │─run(claude)──▶│                │                │
  │               │─subprocess────▶│                │
  │               │◀──timeout──────│                │
  │◀─CLITimeout───│                │                │
  │                                │                │
  │─report_failure()──────────────▶│                │
  │                                │─emit(agent_error)────────▶│
  │                                │                │
  │                                │  retry_count < max_retries│
  │                                │  → state: todo │
  │                                │                │
  │◀─poll() (재시도)───────────────│                │
  │                                │                │
  │─run(codex)───▶│   (폴백 CLI)  │                │
  │               │─subprocess────▶│                │
  │               │◀──result───────│                │
  │◀─success──────│                │                │
  │                                │                │
  │─report_done()─────────────────▶│                │
  │                                │─emit(agent_fallback)─────▶│
  │                                │─emit(task_state_changed)─▶│
```

---

## 5. 데이터 흐름

### 전체 데이터 흐름 (End-to-End)

```
[사용자 입력]
    │
    │  "JWT 인증 미들웨어 구현"
    │  team_preset: "feature-team"
    │  target_repo: "/home/user/my-project"
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ (1) 태스크 제출                                      │
│                                                      │
│  POST /api/tasks → Engine.submit_task()              │
│  Pipeline 생성 (UUID, status: planning)              │
│  EventBus.emit(pipeline_started)                     │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│ (2) 팀 구성                                          │
│                                                      │
│  PresetRegistry.load("feature-team")                 │
│  → agents: {architect, implementer, reviewer}        │
│  → tasks: {design, implement, review}                │
│  EventBus.emit(team_composed)                        │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│ (3) 태스크 분해 (LLM)                                │
│                                                      │
│  TaskDecomposer.decompose(task, team)                 │
│  LLM 호출 → 서브태스크 3개 생성:                     │
│    [A] 시스템 설계 (architect, depends_on: [])        │
│    [B] 코드 구현 (implementer, depends_on: [A])      │
│    [C] 코드 리뷰 (reviewer, depends_on: [B])         │
│  EventBus.emit(decomposition_completed)              │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│ (4) 보드 투입                                        │
│                                                      │
│  TaskBoard.submit([A, B, C])                         │
│  [A] → todo (의존 없음, 즉시 실행 가능)              │
│  [B] → backlog (A 대기)                              │
│  [C] → backlog (B 대기)                              │
│  Pipeline.status: running                            │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│ (5) 워커 실행                                        │
│                                                      │
│  AgentWorker("architect")                            │
│    ├─ poll() → [A] 꺼내기                            │
│    ├─ WorktreeManager.create(task_id, branch)        │
│    ├─ AgentExecutor.run(prompt, worktree_path)       │
│    │   └─ CLIAdapter("claude").execute(prompt)       │
│    │       └─ subprocess: claude --bare -p "..."     │
│    ├─ ArtifactStore.save(task_id, output)            │
│    ├─ Board.mark_done([A])                           │
│    └─ EventBus.emit(task_state_changed, agent_output)│
│                                                      │
│  [A] done → [B] backlog→todo (의존 해소)             │
│                                                      │
│  AgentWorker("implementer")                          │
│    ├─ poll() → [B] 꺼내기                            │
│    ├─ context = ArtifactStore.load([A].output)       │
│    ├─ AgentExecutor.run(prompt + context)            │
│    ├─ Board.mark_done([B])                           │
│    └─ EventBus.emit(...)                             │
│                                                      │
│  [B] done → [C] backlog→todo                        │
│                                                      │
│  AgentWorker("reviewer")                             │
│    ├─ poll() → [C] 꺼내기                            │
│    ├─ context = ArtifactStore.load([A,B].output)     │
│    ├─ AgentExecutor.run(prompt + context)            │
│    ├─ Board.mark_done([C])                           │
│    └─ EventBus.emit(...)                             │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│ (6) Worktree 병합                                    │
│                                                      │
│  WorktreeManager.merge_all(pipeline_id)              │
│    ├─ architect-branch → main                        │
│    ├─ implementer-branch → main                      │
│    └─ (충돌 시 MergeConflictError 발생)             │
│  EventBus.emit(worktree_merged)                      │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│ (7) 결과 종합                                        │
│                                                      │
│  Synthesizer.synthesize(results, strategy="narrative")│
│    └─ LLM 호출: 모든 에이전트 결과 → 종합 보고서    │
│  Pipeline.result = final_report                      │
│  Pipeline.status: completed                          │
│  ArtifactStore.save("synthesis/final-report.md")     │
│  EventBus.emit(pipeline_completed)                   │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
[사용자에게 결과 반환]
    GET /api/tasks/{id} → Pipeline (result 포함)
    WS /ws/events → pipeline_completed 이벤트
```

### 데이터 저장 위치

| 데이터 | 저장 위치 | 형식 | 수명 |
|--------|----------|------|------|
| Pipeline 메타데이터 | `Engine._pipelines` (메모리) | Pydantic model | 서버 프로세스 수명 |
| TaskBoard 상태 | `TaskBoard._lanes` (메모리) | dict[str, Lane] | 서버 프로세스 수명 |
| LangGraph 체크포인트 | SQLite 파일 | LangGraph Saver | 영구 (디스크) |
| 에이전트 출력 | ArtifactStore 디렉토리 | JSON/텍스트 파일 | 영구 (디스크) |
| 이벤트 히스토리 | `EventBus._history` (메모리) | list[Event] | 서버 프로세스 수명 |
| 프리셋 | YAML 파일 | YAML | 영구 (디스크) |
| Git worktree | 파일시스템 | Git worktree | 파이프라인 완료 후 정리 |
| 인증 키 | 환경변수 / .env | 문자열 | 프로세스 수명 |

---

## 6. 동시성 모델

### asyncio 이벤트 루프

전체 시스템은 단일 asyncio 이벤트 루프에서 실행된다.

```
┌──────────────────────────────────────────────────────────┐
│                  asyncio Event Loop                       │
│                                                           │
│  ┌─────────────────┐  ┌─────────────────┐                │
│  │ FastAPI Server   │  │ WebSocket Mgr   │                │
│  │ (uvicorn)        │  │ (broadcast)     │                │
│  └────────┬────────┘  └────────┬────────┘                │
│           │                    │                          │
│  ┌────────┴────────────────────┴────────┐                │
│  │          OrchestratorEngine            │                │
│  │                                        │                │
│  │  ┌─────────────┐  ┌─────────────────┐ │                │
│  │  │ Planning    │  │ AgentWorkers     │ │                │
│  │  │ (LangGraph  │  │ (asyncio.Task)   │ │                │
│  │  │  coroutine) │  │                   │ │                │
│  │  └─────────────┘  │  Worker-1 ─────┐ │ │                │
│  │                    │  Worker-2 ─────┤ │ │                │
│  │                    │  Worker-3 ─────┘ │ │                │
│  │                    └─────────────────┘ │                │
│  └────────────────────────────────────────┘                │
│                                                           │
│  ┌─────────────────────────────────────┐                  │
│  │ subprocess pool (CLI 실행)           │                  │
│  │ asyncio.create_subprocess_exec()     │                  │
│  │                                      │                  │
│  │  proc-1: claude --bare -p "..."      │                  │
│  │  proc-2: codex exec --json "..."     │                  │
│  │  proc-3: gemini -p "..."             │                  │
│  └─────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────┘
```

### asyncio.Task 생명주기

| 컴포넌트 | Task 생성 시점 | Task 종료 시점 | 동시 실행 수 |
|----------|--------------|--------------|------------|
| **Planning** | `submit_task()` 호출 | 분해 완료 후 | 파이프라인당 1개 |
| **AgentWorker** | 레인 생성 시 | 파이프라인 완료 또는 취소 | 레인당 1개 |
| **CLI subprocess** | `AgentExecutor.run()` | subprocess 종료 | 동시 에이전트 수 |
| **Synthesis** | 모든 서브태스크 완료 | LLM 응답 완료 | 파이프라인당 1개 |
| **WS broadcast** | 이벤트 발생 | 전송 완료 | 이벤트당 1개 |

### AgentWorker 루프

```python
class AgentWorker:
    """레인별 태스크 소비자.

    각 워커는 독립 asyncio.Task로 실행되며,
    TaskBoard에서 자기 레인의 태스크를 poll하여 처리한다.
    """

    async def run(self):
        """메인 루프."""
        while not self._stopped:
            task_item = await self._board.poll(self._lane, timeout=1.0)
            if task_item is None:
                continue

            try:
                result = await self._execute(task_item)
                await self._board.mark_done(task_item.id, result)
            except Exception as e:
                await self._board.mark_failed(task_item.id, e)
```

### Queue 동작

TaskBoard 내부적으로 각 레인은 `asyncio.Queue`를 사용하지 않는다. 대신 상태 기반 폴링 방식을 사용한다.

```python
class TaskBoard:
    """칸반 보드.

    각 레인의 태스크를 상태별로 관리한다.
    DAG 의존성이 해소된 태스크만 todo로 전이된다.
    """

    async def poll(self, lane: str, timeout: float = 1.0) -> TaskItem | None:
        """레인에서 todo 상태 태스크를 하나 꺼낸다.

        todo 태스크가 없으면 timeout까지 대기 후 None 반환.
        꺼낸 태스크는 in_progress로 전이.
        """

    def _resolve_dependencies(self) -> None:
        """DAG 의존성 해소.

        모든 depends_on 태스크가 done이면
        backlog → todo로 전이.
        """
```

### 동시성 제한

| 리소스 | 제한 | 근거 |
|--------|------|------|
| 동시 파이프라인 | 제한 없음 (권장: 5 이하) | 메모리 + CLI 프로세스 수 고려 |
| 레인당 동시 태스크 | 1개 | 에이전트 1개 = 1 프로세스 |
| CLI subprocess | OS 프로세스 제한 | `ulimit -u` 값에 의존 |
| 이벤트 히스토리 | 최근 10,000건 유지 | 메모리 절약을 위한 ring buffer |

---

## 7. 상태 관리

### 상태 저장소 분류

```
┌───────────────────────────────────────────────────────────┐
│                   State Management                         │
│                                                            │
│  ┌────────────────────────┐   ┌─────────────────────────┐ │
│  │ Volatile (메모리)       │   │ Persistent (디스크)      │ │
│  │                         │   │                          │ │
│  │ ► Pipeline 맵           │   │ ► LangGraph Checkpoint   │ │
│  │ ► TaskBoard 상태        │   │   (SQLite)               │ │
│  │ ► AgentWorker 상태      │   │                          │ │
│  │ ► EventBus 히스토리     │   │ ► ArtifactStore          │ │
│  │ ► WebSocket 연결 목록   │   │   (파일시스템)           │ │
│  │                         │   │                          │ │
│  │ 서버 재시작 시 소실     │   │ ► Preset YAML            │ │
│  │                         │   │   (presets/ 디렉토리)    │ │
│  └────────────────────────┘   │                          │ │
│                                │ 서버 재시작 후에도 유지  │ │
│                                └─────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

### 체크포인팅

LangGraph SQLite 체크포인터를 사용하여 Planning 단계의 상태를 영속화한다.

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

checkpointer = AsyncSqliteSaver.from_conn_string("checkpoints.db")
```

**체크포인트 저장 시점:**
- compose_team 노드 완료 후
- decompose_task 노드 완료 후
- submit_to_board 노드 완료 후

**resume 동작:**
1. `resume_task(task_id)` 호출
2. 체크포인터에서 마지막 상태 로딩
3. 마지막 성공 노드 이후부터 재실행
4. TaskBoard의 failed 태스크를 todo로 재전이

### Engine 상태 일관성

```python
class OrchestratorEngine:
    """상태 일관성 보장.

    - Pipeline 생성/업데이트는 항상 EventBus.emit()과 함께
    - TaskBoard 상태 변경은 항상 lock 내에서
    - 에러 시 Pipeline.status를 failed로 전이 보장 (finally 블록)
    """

    _lock: asyncio.Lock  # 파이프라인 맵 접근 동기화

    async def submit_task(self, ...):
        async with self._lock:
            pipeline = Pipeline(id=uuid4(), ...)
            self._pipelines[pipeline.id] = pipeline

        try:
            await self._run_planning(pipeline)
            await self._run_execution(pipeline)
            await self._run_synthesis(pipeline)
        except Exception:
            async with self._lock:
                pipeline.status = "failed"
            raise
```

---

## 8. 배포 모델

### 단일 프로세스 모델

v1.0은 단일 Python 프로세스로 모든 컴포넌트를 실행한다.

```
┌──────────────────────────────────────────────────────┐
│              Python Process (단일)                     │
│                                                       │
│  uvicorn                                              │
│    └─ FastAPI app                                     │
│         ├─ REST routes                                │
│         ├─ WebSocket handler                          │
│         └─ OrchestratorEngine (lifespan에서 초기화)    │
│              ├─ TaskBoard                             │
│              ├─ AgentWorkers (asyncio.Tasks)           │
│              ├─ PresetRegistry                        │
│              ├─ EventBus                              │
│              └─ ...                                   │
└──────────────────────────────────────────────────────┘
```

### 서버 시작 시퀀스

```
[1] uvicorn 시작
     │
[2] FastAPI lifespan startup
     │
     ├─[2.1] AuthProvider 초기화
     │        └─ 환경변수에서 API 키 로딩
     │        └─ 키 없으면 WARNING 로그 (에러 아님)
     │
     ├─[2.2] PresetRegistry 초기화
     │        └─ presets/agents/*.yaml 로딩
     │        └─ presets/teams/*.yaml 로딩
     │        └─ deep merge (builtin → user 순서)
     │
     ├─[2.3] CLIAdapter 가용성 확인
     │        └─ claude --version (있으면 OK, 없으면 WARNING)
     │        └─ codex --version
     │        └─ gemini --version
     │
     ├─[2.4] OrchestratorEngine 초기화
     │        └─ TaskBoard 생성
     │        └─ EventBus 생성
     │        └─ ArtifactStore 디렉토리 확인
     │        └─ Checkpointer 연결 (SQLite)
     │
     ├─[2.5] API 라우터 등록
     │        └─ Engine 인스턴스를 app.state에 저장
     │
     └─[2.6] 시작 완료 로그
              └─ "Server started on http://0.0.0.0:8000"
              └─ "Available CLIs: claude(v1.0.34), codex(v0.1.2)"
              └─ "Loaded presets: 5 agents, 3 teams"

[3] 요청 수신 대기
```

### 서버 종료 시퀀스

```
[1] SIGTERM / SIGINT 수신
     │
[2] FastAPI lifespan shutdown
     │
     ├─[2.1] 실행 중인 파이프라인에 cancel 신호
     │        └─ 각 AgentWorker.stop()
     │        └─ 진행 중 subprocess SIGTERM → SIGKILL (5초 타임아웃)
     │
     ├─[2.2] WebSocket 연결 종료
     │        └─ 모든 클라이언트에 close frame 전송
     │
     ├─[2.3] 체크포인터 flush
     │        └─ SQLite 커밋
     │
     ├─[2.4] Worktree 정리
     │        └─ 임시 worktree 삭제
     │
     └─[2.5] 종료 완료 로그

[3] 프로세스 종료
```

### 설정

```python
from pydantic_settings import BaseSettings

class OrchestratorSettings(BaseSettings):
    """환경변수 기반 설정."""

    # 서버
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"                    # "debug" | "info" | "warning" | "error"

    # Core
    default_timeout: int = 600                  # 초
    default_max_retries: int = 3
    default_synthesis_strategy: str = "narrative"
    default_cli_priority: list[str] = ["claude", "codex", "gemini"]
    max_concurrent_pipelines: int = 5
    event_history_size: int = 10000

    # 경로
    preset_dir: str = "presets"
    artifact_dir: str = ".artifacts"
    checkpoint_db: str = "checkpoints.db"

    # 인증
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    model_config = {"env_prefix": "ORCH_"}
```

---

## 9. 확장 포인트

### 새 Executor 유형 추가

`AgentExecutor` ABC를 구현하여 새로운 에이전트 실행 방식을 추가한다.

```python
from orchestrator.core.executor.base import AgentExecutor, AgentResult

class DockerExecutor(AgentExecutor):
    """Docker 컨테이너 내에서 에이전트 실행."""

    executor_type: str = "docker"

    async def run(self, prompt: str, *, timeout: int = 300, context: dict | None = None) -> AgentResult:
        # Docker 컨테이너 시작
        # prompt를 stdin으로 전달
        # stdout에서 결과 수집
        ...

    async def health_check(self) -> bool:
        # docker daemon 연결 확인
        ...
```

**등록:**

```python
# engine 초기화 시
engine.register_executor_type("docker", DockerExecutor)
```

### 새 Synthesis 전략 추가

`Synthesizer`에 새로운 종합 전략을 추가한다.

```python
class Synthesizer:
    _strategies: dict[str, Callable] = {
        "narrative": self._narrative_synthesis,
        "structured": self._structured_synthesis,
        "checklist": self._checklist_synthesis,
    }

    def register_strategy(self, name: str, func: Callable) -> None:
        """커스텀 종합 전략 등록."""
        self._strategies[name] = func
```

**커스텀 전략 구현:**

```python
async def incident_report_synthesis(results: list[AgentResult], task: str) -> str:
    """인시던트 보고서 형식 종합."""
    # 타임라인, 원인 분석, 영향 범위, 권장 조치 섹션으로 구성
    ...

synthesizer.register_strategy("incident_report", incident_report_synthesis)
```

### 새 CLI Adapter 추가

`CLIAdapter` ABC를 구현하여 새로운 CLI 도구를 추가한다.

```python
from orchestrator.core.adapters.base import CLIAdapter

class CursorAdapter(CLIAdapter):
    """Cursor CLI 어댑터."""

    name: str = "cursor"

    def build_command(self, prompt: str, *, persona: PersonaDef | None = None) -> list[str]:
        cmd = ["cursor", "--headless", "--prompt", prompt]
        if persona:
            cmd.extend(["--system", self._format_persona(persona)])
        return cmd

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> AgentResult:
        # Cursor CLI 출력 파싱
        ...

    async def check_available(self) -> tuple[bool, str | None]:
        # cursor --version 실행
        ...
```

**등록:**

```python
# adapters/factory.py
ADAPTER_REGISTRY: dict[str, type[CLIAdapter]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "gemini": GeminiAdapter,
    "cursor": CursorAdapter,  # 추가
}
```

### 새 이벤트 유형 추가

`EventType` enum에 새 유형을 추가하고 EventBus를 통해 발행한다.

```python
# events/types.py
class EventType(StrEnum):
    # 기존 유형...
    CUSTOM_METRIC = "custom_metric"  # 추가

# 사용
event_bus.emit(Event(
    type=EventType.CUSTOM_METRIC,
    pipeline_id=pipeline_id,
    data={"metric": "token_usage", "value": 15000}
))
```

### 프리셋 확장

YAML 프리셋을 추가하여 코드 변경 없이 팀을 확장한다.

```yaml
# presets/agents/devops-engineer.yaml
name: devops-engineer
persona:
  role: DevOps 엔지니어
  goal: CI/CD 파이프라인 구성 및 인프라 자동화
  backstory: Terraform + GitHub Actions 전문가
  constraints:
    - IaC 원칙 준수 필수
    - 시크릿은 반드시 환경변수로 관리
preferred_cli: claude
limits:
  max_tokens: 32768
  timeout: 600
  max_turns: 15
```

```yaml
# presets/teams/deploy-team.yaml
name: deploy-team
agents:
  devops:
    preset: devops-engineer
    count: 1
  tester:
    preset: tester
    count: 1
tasks:
  deploy:
    description: 카나리 배포 구성
    agent: devops
  verify:
    description: 배포 검증
    agent: tester
    depends_on: [deploy]
workflow: sequential
synthesis_strategy: checklist
```

### 프리셋 검색 경로 (우선순위)

```
1. 사용자 디렉토리:  ~/.config/orchestrator/presets/
2. 프로젝트 디렉토리: ./presets/
3. 빌트인:           <package>/presets/

동일 이름 프리셋은 높은 우선순위가 override (deep merge).
```
