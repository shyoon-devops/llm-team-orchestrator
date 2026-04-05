# 파일 구조 명세서

> v1.0 | 2026-04-05
> SPEC.md v2.0 기반

---

## 1. 개요

이 문서는 Agent Team Orchestrator 프로젝트의 **전체 파일 구조**를 정의한다. 모든 소스 파일, 테스트 파일, 설정 파일, 프리셋, 프론트엔드 컴포넌트, CI 워크플로우를 포함한다.

### 범례

| 기호 | 의미 |
|------|------|
| `[P1]` | Phase 1에서 생성 |
| `[P2]` | Phase 2에서 생성 |
| `[P3]` | Phase 3에서 생성 |
| `[PoC→]` | PoC 코드에서 리팩터링 (기존 pyc 기반 재작성) |
| `[NEW]` | 완전 신규 작성 |

### PoC 모듈 매핑

PoC(pyc 기반)에서 MVP로 전환 시, 아래 모듈이 리팩터링 대상이다.

| PoC 모듈 | MVP 위치 | 변경 사항 |
|----------|----------|----------|
| `adapters/base.py` | `core/adapters/base.py` | ABC 시그니처 변경 없음, `core/` 하위로 이동 |
| `adapters/claude.py` | `core/adapters/claude.py` | JSON 파싱 강화 |
| `adapters/codex.py` | `core/adapters/codex.py` | 그대로 이동 |
| `adapters/gemini.py` | `core/adapters/gemini.py` | stream-json 필터링 강화 |
| `adapters/factory.py` | `core/adapters/factory.py` | AdapterFactory 그대로 유지 |
| `graph/state.py` | `core/models/schemas.py` | OrchestratorState → Pipeline/TaskItem 모델로 분리 |
| `graph/nodes.py` | `core/planner/decomposer.py` + `core/queue/worker.py` | 노드 함수를 도메인별 클래스로 분리 |
| `graph/builder.py` | `core/planner/team_planner.py` | LangGraph 기반 planning 전용 |
| `auth/provider.py` | `core/auth/provider.py` | 인터페이스 동일, KeyPool 통합 |
| `auth/key_pool.py` | `core/auth/key_pool.py` | 그대로 이동 |
| `config/schema.py` | `core/config/schema.py` | config/ 서브디렉토리로 이동 |
| `config/loader.py` | `core/config/loader.py` | 설정 로더 유지 |
| `context/artifact_store.py` | `core/context/artifact_store.py` | 그대로 이동 |
| `events/bus.py` | `core/events/bus.py` | WebSocket 브로드캐스트 추가 |
| `events/types.py` | `core/events/types.py` | 이벤트 타입 확장 |
| `events/tracker.py` | `core/events/tracker.py` | 그대로 이동 |
| `worktree/manager.py` | `core/worktree/manager.py` | 그대로 이동 |
| `worktree/collector.py` | `core/worktree/collector.py` | FileDiffCollector로 그대로 이동 |
| `errors/exceptions.py` | `core/errors/exceptions.py` | 에러 계층 확장 |
| `models/schemas.py` | `core/models/schemas.py` | Preset 모델 추가 |
| `web/app.py` | `api/app.py` | CORS, lifespan 추가 |
| `web/routes.py` | `api/routes.py` | 엔드포인트 확장 (board, presets) |
| `web/ws.py` | `api/ws.py` | 그대로 이동 |
| `queue/board.py` | `core/queue/board.py` | 그대로 이동 |
| `queue/models.py` | `core/queue/models.py` | TaskItem, TaskState, Lane 모델 유지 |
| `queue/worker.py` | `core/queue/worker.py` | 그대로 이동 |
| `executor/base.py` | `core/executor/base.py` | AgentExecutor ABC |
| `executor/cli_executor.py` | `core/executor/cli_executor.py` | CLIAgentExecutor |
| `executor/mcp_executor.py` | `core/executor/mcp_executor.py` | MCPAgentExecutor |
| `executor/synthesizer.py` | `core/events/synthesizer.py` | events/ 하위로 이동 |
| `hybrid/orchestrator.py` | `core/engine.py` | HybridOrchestrator → OrchestratorEngine으로 리팩터링 |
| `poc/demo.py` | 삭제 | MVP에서 제거 |
| `poc/mock_adapters.py` | `tests/mocks/mock_adapter.py` | 테스트 전용으로 이동 |
| `utils.py` | `core/utils.py` | 그대로 이동 |

---

## 2. 전체 파일 트리

```
llm-team-orchestrator/
├── pyproject.toml                           # 프로젝트 메타데이터 + 의존성 (uv)           [P1][PoC→]
├── uv.lock                                  # uv 락파일 (자동 생성)                       [P1]
├── .python-version                          # Python 버전 고정 (3.12)                     [P1]
├── .env.example                             # 환경변수 템플릿                               [P1][NEW]
├── .gitignore                               # Git 제외 패턴                                [P1]
├── .pre-commit-config.yaml                  # pre-commit 훅 설정                          [P1][NEW]
│
├── docs/
│   ├── SPEC.md                              # 프로젝트 기획서                               [P1]
│   ├── file-structure.md                    # 이 문서                                      [P1]
│   ├── dependencies.md                      # 의존성 명세서                                 [P1]
│   └── testing.md                           # 테스트 명세서                                 [P1]
│
├── src/
│   └── orchestrator/                        # 메인 패키지
│       ├── __init__.py                      # 패키지 초기화, __version__ 내보내기           [P1][PoC→]
│       ├── __main__.py                      # python -m orchestrator 진입점               [P1][NEW]
│       ├── cli.py                           # typer CLI 앱                                [P1][NEW]
│       │
│       ├── core/                            # Core 계층 (비즈니스 로직 전체)
│       │   ├── __init__.py                  # core 패키지 초기화                           [P1]
│       │   ├── engine.py                    # OrchestratorEngine (단일 진입점)             [P1][PoC→]
│       │   ├── utils.py                     # 공용 유틸리티 함수                            [P1][PoC→]
│       │   │
│       │   ├── config/                      # 설정 관리
│       │   │   ├── __init__.py              # config 패키지                               [P1]
│       │   │   ├── schema.py                # OrchestratorConfig (pydantic-settings)      [P1][PoC→]
│       │   │   └── loader.py                # 설정 로더 (환경변수, .env, YAML)            [P1][PoC→]
│       │   │
│       │   ├── executor/                    # AgentExecutor 계층
│       │   │   ├── __init__.py              # executor 패키지, public API 내보내기         [P1]
│       │   │   ├── base.py                  # AgentExecutor ABC                           [P1][PoC→]
│       │   │   ├── cli_executor.py          # CLIAgentExecutor (subprocess)               [P1][PoC→]
│       │   │   └── mcp_executor.py          # MCPAgentExecutor (LLM + MCP tools)          [P3][PoC→]
│       │   │
│       │   ├── queue/                       # TaskBoard 칸반 큐
│       │   │   ├── __init__.py              # queue 패키지                                [P1]
│       │   │   ├── models.py                # TaskItem, TaskState, Lane 큐 모델            [P1][PoC→]
│       │   │   ├── board.py                 # TaskBoard (칸반 보드 상태 관리)               [P1][PoC→]
│       │   │   └── worker.py                # AgentWorker (레인별 태스크 소비)              [P1][PoC→]
│       │   │
│       │   ├── presets/                     # 프리셋 시스템
│       │   │   ├── __init__.py              # presets 패키지                               [P2][NEW]
│       │   │   ├── models.py                # AgentPreset, TeamPreset, PersonaDef 모델     [P2][NEW]
│       │   │   └── registry.py              # PresetRegistry (YAML 로드/저장/조회)          [P2][NEW]
│       │   │
│       │   ├── planner/                     # LLM 기반 태스크 분해 + 팀 구성
│       │   │   ├── __init__.py              # planner 패키지                               [P2][NEW]
│       │   │   ├── decomposer.py            # TaskDecomposer (LLM 호출 → 서브태스크)       [P2][PoC→]
│       │   │   └── team_planner.py          # TeamPlanner (자동 팀 구성)                   [P3][NEW]
│       │   │
│       │   ├── adapters/                    # CLI 어댑터 레이어
│       │   │   ├── __init__.py              # adapters 패키지, public API                 [P1]
│       │   │   ├── base.py                  # CLIAdapter ABC                              [P1][PoC→]
│       │   │   ├── claude.py                # ClaudeAdapter                               [P1][PoC→]
│       │   │   ├── codex.py                 # CodexAdapter                                [P2][PoC→]
│       │   │   ├── gemini.py                # GeminiAdapter                               [P2][PoC→]
│       │   │   └── factory.py               # AdapterFactory (프리셋→AgentExecutor 생성)   [P2][PoC→]
│       │   │
│       │   ├── worktree/                    # Git worktree 격리
│       │   │   ├── __init__.py              # worktree 패키지                              [P2]
│       │   │   ├── manager.py               # WorktreeManager (생성/정리/병합)             [P2][PoC→]
│       │   │   └── collector.py             # FileDiffCollector (worktree 파일 변경 수집)   [P2][PoC→]
│       │   │
│       │   ├── context/                     # 아티팩트 스토어
│       │   │   ├── __init__.py              # context 패키지                               [P2]
│       │   │   ├── artifact_store.py         # ArtifactStore (파일 기반 결과 저장)           [P2][PoC→]
│       │   │   └── prompt_builder.py         # PromptBuilder (컨텍스트 주입 프롬프트)        [P3][NEW]
│       │   │
│       │   ├── auth/                        # 인증 관리
│       │   │   ├── __init__.py              # auth 패키지                                 [P1]
│       │   │   ├── provider.py              # AuthProvider ABC + EnvAuthProvider          [P1][PoC→]
│       │   │   └── key_pool.py              # KeyPool (키 풀링, Phase 3)                  [P3][PoC→]
│       │   │
│       │   ├── events/                      # 이벤트 버스 + Synthesizer
│       │   │   ├── __init__.py              # events 패키지                               [P1]
│       │   │   ├── bus.py                   # EventBus (pub/sub + WebSocket 브로드캐스트)  [P1][PoC→]
│       │   │   ├── types.py                 # EventType enum + Event 모델                 [P1][PoC→]
│       │   │   ├── tracker.py               # EventTracker (이벤트 히스토리 저장)           [P2][PoC→]
│       │   │   └── synthesizer.py           # Synthesizer (결과 종합)                      [P2][PoC→]
│       │   │
│       │   ├── errors/                      # 에러 계층
│       │   │   ├── __init__.py              # errors 패키지, 예외 클래스 re-export         [P1]
│       │   │   ├── exceptions.py            # OrchestratorError 계층 구조                  [P1][PoC→]
│       │   │   ├── retry.py                 # RetryPolicy (지수 백오프, tenacity 래퍼)     [P3][NEW]
│       │   │   └── fallback.py              # FallbackChain (CLI 폴백 체인)                [P3][NEW]
│       │   │
│       │   └── models/                      # Pydantic 공유 모델
│       │       ├── __init__.py              # models 패키지                                [P1]
│       │       ├── schemas.py               # 공통 스키마 (AgentResult, Config 등)          [P1][PoC→]
│       │       └── pipeline.py              # Pipeline, PipelineStatus 모델               [P1][NEW]
│       │
│       └── api/                             # API 계층 (FastAPI)
│           ├── __init__.py                  # api 패키지                                   [P1]
│           ├── app.py                       # FastAPI 앱 팩토리 (CORS, lifespan)           [P1][PoC→]
│           ├── routes.py                    # REST 엔드포인트 (tasks, board, presets)       [P1][PoC→]
│           ├── ws.py                        # WebSocket 이벤트 스트림 (/ws/events)          [P1][PoC→]
│           └── deps.py                      # FastAPI 의존성 주입 (get_engine 등)           [P1][NEW]
│
├── presets/                                 # YAML 프리셋 번들
│   ├── agents/                              # 에이전트 프리셋
│   │   ├── architect.yaml                   # 시니어 아키텍트 (설계 전문)                    [P2][NEW]
│   │   ├── implementer.yaml                 # 시니어 개발자 (구현 전문)                      [P2][NEW]
│   │   ├── reviewer.yaml                    # 코드 리뷰어 (리뷰 전문)                       [P2][NEW]
│   │   ├── elk-analyst.yaml                 # ELK 분석가 (MCP: Elasticsearch)             [P3][NEW]
│   │   ├── grafana-monitor.yaml             # Grafana 모니터링 전문가 (MCP: Grafana)        [P3][NEW]
│   │   └── k8s-operator.yaml                # K8s 운영자 (MCP: kubectl)                   [P3][NEW]
│   └── teams/                               # 팀 프리셋
│       ├── feature-team.yaml                # 코딩 팀 (architect → implementer → reviewer) [P2][NEW]
│       ├── incident-analysis.yaml           # 장애 분석 팀 (ELK + Grafana + K8s 병렬)      [P3][NEW]
│       └── deploy-team.yaml                 # 배포 팀 (모니터링 → 배포 → 검증)              [P3][NEW]
│
├── frontend/                                # React 대시보드 SPA
│   ├── package.json                         # Node.js 의존성                               [P2][NEW]
│   ├── tsconfig.json                        # TypeScript 설정                              [P2][NEW]
│   ├── vite.config.ts                       # Vite 빌드 설정                               [P2][NEW]
│   ├── index.html                           # HTML 진입점                                  [P2][NEW]
│   ├── public/
│   │   └── favicon.ico                      # 파비콘                                       [P2][NEW]
│   └── src/
│       ├── main.tsx                          # React 앱 진입점                              [P2][NEW]
│       ├── App.tsx                           # 최상위 App 컴포넌트 + 라우팅                  [P2][NEW]
│       ├── api/
│       │   ├── client.ts                    # Axios/fetch 클라이언트 (REST)                [P2][NEW]
│       │   └── websocket.ts                 # WebSocket 클라이언트 (/ws/events)            [P2][NEW]
│       ├── types/
│       │   └── index.ts                     # TypeScript 타입 정의 (Pipeline, TaskItem 등) [P2][NEW]
│       ├── hooks/
│       │   ├── useBoard.ts                  # 칸반 보드 상태 훅                             [P2][NEW]
│       │   ├── useEvents.ts                 # WebSocket 이벤트 구독 훅                     [P2][NEW]
│       │   └── usePipeline.ts               # 파이프라인 상태 훅                            [P2][NEW]
│       ├── components/
│       │   ├── Layout.tsx                   # 앱 레이아웃 (사이드바 + 메인)                  [P2][NEW]
│       │   ├── BoardView.tsx                # 칸반 보드 뷰 (레인 + 카드)                    [P2][NEW]
│       │   ├── TaskCard.tsx                 # 태스크 카드 컴포넌트                           [P2][NEW]
│       │   ├── LaneColumn.tsx               # 칸반 레인 컬럼                                [P2][NEW]
│       │   ├── AgentStatus.tsx              # 에이전트 상태 인디케이터                       [P2][NEW]
│       │   ├── PipelineList.tsx             # 파이프라인 목록                                [P2][NEW]
│       │   ├── PipelineDetail.tsx           # 파이프라인 상세 (결과 뷰어)                    [P2][NEW]
│       │   ├── EventLog.tsx                 # 이벤트 로그 (실시간 스트림)                    [P2][NEW]
│       │   ├── TaskSubmitForm.tsx           # 태스크 제출 폼                                [P2][NEW]
│       │   ├── PresetSelector.tsx           # 프리셋 선택 드롭다운                           [P3][NEW]
│       │   └── ResultViewer.tsx             # 결과 마크다운 렌더러                           [P3][NEW]
│       └── styles/
│           └── global.css                   # 전역 스타일 (Tailwind 또는 CSS Modules)       [P2][NEW]
│
├── tests/
│   ├── conftest.py                          # 공통 fixture 정의                            [P1][NEW]
│   │
│   ├── unit/                                # 유닛 테스트
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── test_engine.py               # OrchestratorEngine 테스트                   [P1][NEW]
│   │   │   │
│   │   │   ├── config/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_schema.py           # OrchestratorConfig 테스트                   [P1][NEW]
│   │   │   │   └── test_loader.py           # 설정 로더 테스트                             [P1][NEW]
│   │   │   │
│   │   │   ├── executor/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_base_executor.py    # AgentExecutor ABC 테스트                    [P1][NEW]
│   │   │   │   ├── test_cli_executor.py     # CLIAgentExecutor 테스트                     [P1][NEW]
│   │   │   │   └── test_mcp_executor.py     # MCPAgentExecutor 테스트                     [P3][NEW]
│   │   │   │
│   │   │   ├── queue/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_models.py           # TaskItem, TaskState 모델 테스트              [P1][NEW]
│   │   │   │   ├── test_board.py            # TaskBoard 테스트                             [P1][NEW]
│   │   │   │   └── test_worker.py           # AgentWorker 테스트                           [P1][NEW]
│   │   │   │
│   │   │   ├── presets/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_models.py           # 프리셋 모델 테스트                            [P2][NEW]
│   │   │   │   └── test_registry.py         # PresetRegistry 테스트                       [P2][NEW]
│   │   │   │
│   │   │   ├── planner/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_decomposer.py       # TaskDecomposer 테스트                       [P2][NEW]
│   │   │   │   └── test_team_planner.py     # TeamPlanner 테스트                          [P3][NEW]
│   │   │   │
│   │   │   ├── adapters/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_base_adapter.py     # CLIAdapter ABC 테스트                       [P1][NEW]
│   │   │   │   ├── test_claude.py           # ClaudeAdapter 테스트                        [P1][NEW]
│   │   │   │   ├── test_codex.py            # CodexAdapter 테스트                         [P2][NEW]
│   │   │   │   ├── test_gemini.py           # GeminiAdapter 테스트                        [P2][NEW]
│   │   │   │   └── test_adapter_factory.py  # AdapterFactory 테스트                       [P2][NEW]
│   │   │   │
│   │   │   ├── worktree/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_manager.py          # WorktreeManager 테스트                      [P2][NEW]
│   │   │   │   └── test_collector.py        # FileDiffCollector 테스트                     [P2][NEW]
│   │   │   │
│   │   │   ├── context/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_artifact_store.py   # ArtifactStore 테스트                        [P2][NEW]
│   │   │   │   └── test_prompt_builder.py   # PromptBuilder 테스트                        [P3][NEW]
│   │   │   │
│   │   │   ├── auth/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_provider.py         # AuthProvider 테스트                         [P1][NEW]
│   │   │   │   └── test_key_pool.py         # KeyPool 테스트                              [P3][NEW]
│   │   │   │
│   │   │   ├── events/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_bus.py              # EventBus 테스트                             [P1][NEW]
│   │   │   │   ├── test_types.py            # EventType 테스트                            [P1][NEW]
│   │   │   │   ├── test_tracker.py          # EventTracker 테스트                         [P2][NEW]
│   │   │   │   └── test_synthesizer.py      # Synthesizer 테스트                          [P2][NEW]
│   │   │   │
│   │   │   ├── errors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_exceptions.py       # 에러 계층 테스트                              [P1][NEW]
│   │   │   │   ├── test_retry.py            # RetryPolicy 테스트                          [P3][NEW]
│   │   │   │   └── test_fallback.py         # FallbackChain 테스트                        [P3][NEW]
│   │   │   │
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── test_schemas.py          # AgentResult 등 공통 모델 테스트               [P1][NEW]
│   │   │       └── test_pipeline.py         # Pipeline 모델 테스트                         [P1][NEW]
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── test_routes.py               # REST 엔드포인트 테스트                        [P1][NEW]
│   │   │   ├── test_ws.py                   # WebSocket 테스트                             [P1][NEW]
│   │   │   └── test_deps.py                 # 의존성 주입 테스트                            [P1][NEW]
│   │   │
│   │   └── test_cli.py                      # typer CLI 테스트                             [P1][NEW]
│   │
│   ├── integration/                         # 통합 테스트
│   │   ├── __init__.py
│   │   ├── conftest.py                      # 통합 테스트 전용 fixture                     [P2][NEW]
│   │   ├── test_claude_adapter.py           # 실 Claude CLI 호출 테스트                    [P2][NEW]
│   │   ├── test_codex_adapter.py            # 실 Codex CLI 호출 테스트                     [P2][NEW]
│   │   ├── test_gemini_adapter.py           # 실 Gemini CLI 호출 테스트                    [P2][NEW]
│   │   ├── test_worktree_ops.py             # 실 Git worktree 생성/병합 테스트              [P2][NEW]
│   │   └── test_pipeline_mock.py            # Mock 어댑터 기반 파이프라인 통합 테스트        [P2][NEW]
│   │
│   ├── e2e/                                 # E2E 테스트
│   │   ├── __init__.py
│   │   ├── conftest.py                      # E2E 전용 fixture                            [P3][NEW]
│   │   ├── test_coding_scenario.py          # 코딩 팀 E2E (JWT 미들웨어)                   [P3][NEW]
│   │   ├── test_incident_scenario.py        # 장애 분석 E2E (MCP 에이전트)                 [P3][NEW]
│   │   ├── test_failure_scenario.py         # 실패→재시도→폴백 E2E                         [P3][NEW]
│   │   └── test_resume_scenario.py          # 중단→재개 E2E (체크포인팅)                    [P3][NEW]
│   │
│   ├── api/                                 # API 전용 테스트 (httpx AsyncClient)
│   │   ├── __init__.py
│   │   ├── conftest.py                      # API 테스트 전용 fixture (async client)       [P1][NEW]
│   │   ├── test_task_endpoints.py           # POST/GET/DELETE /api/tasks                  [P1][NEW]
│   │   ├── test_board_endpoints.py          # GET /api/board, /api/board/lanes            [P2][NEW]
│   │   ├── test_preset_endpoints.py         # GET/POST /api/presets/agents, teams         [P2][NEW]
│   │   ├── test_agent_endpoints.py          # GET /api/agents                             [P2][NEW]
│   │   ├── test_event_endpoints.py          # GET /api/events                             [P2][NEW]
│   │   └── test_health_endpoint.py          # GET /api/health                             [P1][NEW]
│   │
│   ├── mocks/                               # 테스트 mock 모듈
│   │   ├── __init__.py                      # mock 패키지                                 [P1][NEW]
│   │   ├── mock_adapter.py                  # MockCLIAdapter (테스트용)                    [P1][PoC→]
│   │   ├── mock_executor.py                 # MockAgentExecutor (테스트용)                 [P1][NEW]
│   │   └── fixtures/                        # JSON 응답 fixture
│   │       ├── claude_response.json         # Claude 정상 응답 샘플                        [P1][NEW]
│   │       ├── claude_error.json            # Claude 에러 응답 샘플                        [P1][NEW]
│   │       ├── codex_response.json          # Codex 정상 응답 샘플                         [P2][NEW]
│   │       ├── gemini_response.json         # Gemini 정상 응답 샘플 (stream-json)          [P2][NEW]
│   │       ├── gemini_polluted.json         # Gemini stdout 오염 샘플 (#21433)            [P2][NEW]
│   │       ├── decomposition_result.json    # 태스크 분해 결과 샘플                         [P2][NEW]
│   │       ├── agent_preset_sample.yaml     # 에이전트 프리셋 테스트 데이터                  [P2][NEW]
│   │       └── team_preset_sample.yaml      # 팀 프리셋 테스트 데이터                       [P2][NEW]
│   │
│   └── pytest.ini                           # pytest 추가 설정 (필요 시)                    [P1][NEW]
│
├── scripts/
│   ├── setup_dev.sh                         # 개발 환경 셋업 스크립트                       [P1][NEW]
│   └── run_integration.sh                   # 통합 테스트 실행 (키 필요)                    [P2][NEW]
│
└── .github/
    └── workflows/
        ├── ci.yml                           # PR 유닛 테스트 + 린트                        [P1][NEW]
        └── integration.yml                  # 통합 테스트 (수동/주간)                       [P2][NEW]
```

---

## 3. 파일별 상세 명세

### 3.1 루트 설정 파일

#### `pyproject.toml` [P1][PoC→]
- **목적:** 프로젝트 메타데이터, 의존성, 빌드 설정, 도구 설정 통합
- **내용:** 별도 `docs/dependencies.md` 참조
- **LOC:** ~120

#### `.env.example` [P1][NEW]
- **목적:** 환경변수 템플릿 (API 키, 설정값)
- **내용:** `ANTHROPIC_API_KEY`, `CODEX_API_KEY`, `GEMINI_API_KEY`, `ORCHESTRATOR_*` 설정
- **LOC:** ~20

#### `.pre-commit-config.yaml` [P1][NEW]
- **목적:** ruff lint/format + mypy pre-commit 훅
- **내용:** `ruff-pre-commit`, `mirrors-mypy` 설정
- **LOC:** ~15

#### `.gitignore` [P1]
- **목적:** `__pycache__/`, `.venv/`, `.env`, `*.pyc`, `node_modules/`, `dist/`, `coverage/` 등 제외
- **LOC:** ~30

---

### 3.2 `src/orchestrator/` — 메인 패키지

#### `__init__.py` [P1][PoC→]
- **목적:** 패키지 초기화, 버전 내보내기
- **내용:** `__version__ = "0.1.0"`
- **의존성:** 없음
- **LOC:** ~5

#### `__main__.py` [P1][NEW]
- **목적:** `python -m orchestrator` 진입점
- **주요 함수:** `main()` — `cli.app()` 호출
- **의존성:** `orchestrator.cli`
- **LOC:** ~10

#### `cli.py` [P1][NEW]
- **목적:** typer CLI 앱 (사용자 명령어 인터페이스)
- **주요 클래스/함수:**
  - `app = typer.Typer()` — 최상위 CLI 앱
  - `run(task, repo, team_preset, timeout)` — 태스크 실행 명령
  - `status(task_id)` — 파이프라인 상태 조회
  - `cancel(task_id)` — 태스크 취소
  - `presets()` — 프리셋 목록 조회
  - `serve(host, port)` — API 서버 실행 (uvicorn)
- **의존성:** `typer`, `rich`, `httpx`, `orchestrator.core.engine`, `orchestrator.core.config.schema`
- **LOC:** ~150

---

### 3.3 `src/orchestrator/core/` — Core 계층

#### `core/__init__.py` [P1]
- **목적:** core 패키지 초기화
- **LOC:** ~3

#### `core/engine.py` [P1][PoC→]
- **목적:** OrchestratorEngine — Core 계층 단일 진입점. API/CLI는 이것만 의존
- **주요 클래스:**
  - `OrchestratorEngine`
    - `__init__(config, preset_registry, event_bus)` — 의존성 주입
    - `async submit_task(task, *, team_preset, target_repo) -> Pipeline` — 태스크 제출
    - `async get_pipeline(task_id) -> Pipeline | None` — 파이프라인 조회
    - `async list_pipelines() -> list[Pipeline]` — 파이프라인 목록
    - `async cancel_task(task_id) -> bool` — 태스크 취소
    - `async resume_task(task_id) -> Pipeline` — 중단 태스크 재개
    - `list_agent_presets() -> list[AgentPreset]` — 에이전트 프리셋 목록
    - `list_team_presets() -> list[TeamPreset]` — 팀 프리셋 목록
    - `save_agent_preset(preset) -> None` — 에이전트 프리셋 저장
    - `save_team_preset(preset) -> None` — 팀 프리셋 저장
    - `get_board_state() -> dict` — 칸반 보드 상태
    - `list_agents() -> list[Agent]` — 에이전트 상태 목록
    - `subscribe(callback) -> None` — 이벤트 구독
    - `get_events(task_id) -> list[Event]` — 이벤트 히스토리
  - `Pipeline` (NamedTuple 또는 dataclass)
    - `id: str`, `task: str`, `status: str`, `board: TaskBoard`, `result: str | None`
- **의존성:** `core.queue.board.TaskBoard`, `core.presets.registry.PresetRegistry`, `core.events.bus.EventBus`, `core.events.synthesizer.Synthesizer`, `core.executor.base.AgentExecutor`, `core.planner.decomposer.TaskDecomposer`, `core.models.pipeline`, `core.queue.models`, `core.adapters.factory.AdapterFactory`
- **LOC:** ~250

#### `core/config/__init__.py` [P1]
- **목적:** config 패키지 초기화, OrchestratorConfig re-export
- **LOC:** ~3

#### `core/config/schema.py` [P1][PoC→]
- **목적:** OrchestratorConfig (pydantic-settings) — 환경변수 기반 설정 로딩
- **주요 클래스:**
  - `OrchestratorConfig(BaseSettings)`
    - `app_name: str = "agent-team-orchestrator"`
    - `debug: bool = False`
    - `log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"`
    - `default_timeout: int = 300`
    - `max_retries: int = 3`
    - `max_iterations: int = 5`
    - `cli_priority: list[str] = ["claude", "codex", "gemini"]`
    - `worktree_base_dir: str = "/tmp/orchestrator-worktrees"`
    - `cleanup_worktrees: bool = True`
    - `api_host: str = "0.0.0.0"`
    - `api_port: int = 8000`
    - `preset_dir: str = "presets"`
- **의존성:** `pydantic_settings`
- **LOC:** ~70

#### `core/config/loader.py` [P1][PoC→]
- **목적:** 설정 로더 — 환경변수, .env 파일, CLI 인자 병합
- **주요 함수:**
  - `load_config(env_file: str | None = None) -> OrchestratorConfig` — 설정 로딩
- **의존성:** `core.config.schema.OrchestratorConfig`
- **LOC:** ~30

#### `core/utils.py` [P1][PoC→]
- **목적:** 공용 유틸리티 함수
- **주요 함수:**
  - `generate_id(prefix) -> str` — UUID 기반 고유 ID 생성
  - `truncate(text, max_len) -> str` — 텍스트 길이 제한
  - `setup_logging(level) -> None` — structlog 설정
  - `async run_with_timeout(coro, timeout) -> Any` — 타임아웃 래퍼
- **의존성:** `structlog`, `uuid`, `asyncio`
- **LOC:** ~50

---

### 3.4 `src/orchestrator/core/executor/` — 에이전트 실행

#### `executor/__init__.py` [P1]
- **목적:** AgentExecutor, CLIAgentExecutor, AgentResult re-export
- **LOC:** ~5

#### `executor/base.py` [P1][PoC→]
- **목적:** AgentExecutor ABC — 도메인 무관 에이전트 실행 인터페이스
- **주요 클래스:**
  - `AgentResult(BaseModel)`
    - `success: bool`, `output: str`, `exit_code: int`, `duration_ms: float`
    - `executor_type: str`, `agent_name: str`
    - `raw_stdout: str`, `raw_stderr: str`
  - `AgentExecutor(ABC)`
    - `executor_type: str` — `"cli"` | `"mcp"` | `"mock"`
    - `async run(prompt, *, timeout, context) -> AgentResult` — 추상 메서드
    - `async health_check() -> bool` — 추상 메서드
- **의존성:** `pydantic`, `abc`
- **LOC:** ~50

#### `executor/cli_executor.py` [P1][PoC→]
- **목적:** CLIAgentExecutor — CLIAdapter를 감싸는 AgentExecutor 구현
- **주요 클래스:**
  - `CLIAgentExecutor(AgentExecutor)`
    - `__init__(adapter: CLIAdapter, workdir: Path)`
    - `async run(prompt, *, timeout, context) -> AgentResult` — adapter.execute() 호출
    - `async health_check() -> bool` — adapter.health_check() 호출
    - `executor_type = "cli"`
- **의존성:** `core.executor.base.AgentExecutor`, `core.adapters.base.CLIAdapter`
- **LOC:** ~60

#### `executor/mcp_executor.py` [P3][PoC→]
- **목적:** MCPAgentExecutor — LLM + MCP tools 기반 에이전트 실행
- **주요 클래스:**
  - `MCPAgentExecutor(AgentExecutor)`
    - `__init__(llm_config, mcp_servers: dict)`
    - `async run(prompt, *, timeout, context) -> AgentResult` — LiteLLM + MCP 호출
    - `async health_check() -> bool` — MCP 서버 연결 확인
    - `executor_type = "mcp"`
- **의존성:** `core.executor.base.AgentExecutor`, `litellm`
- **LOC:** ~120

---

### 3.5 `src/orchestrator/core/queue/` — 칸반 태스크 큐

#### `queue/__init__.py` [P1]
- **목적:** TaskBoard, AgentWorker, TaskItem re-export
- **LOC:** ~5

#### `queue/models.py` [P1][PoC→]
- **목적:** 칸반 큐 도메인 모델
- **주요 클래스:**
  - `TaskState(StrEnum)` — `BACKLOG`, `TODO`, `IN_PROGRESS`, `DONE`, `FAILED`
  - `Lane(BaseModel)` — `name`, `agent_preset`, `tasks: list[TaskItem]`
  - `TaskItem(BaseModel)` — `id`, `title`, `lane`, `state`, `depends_on`, `assigned_to`, `result`, `retry_count`, `max_retries`, `pipeline_id`, `created_at`, `started_at`, `completed_at`
- **의존성:** `pydantic`, `enum`, `datetime`
- **LOC:** ~60

#### `queue/board.py` [P1][PoC→]
- **목적:** TaskBoard — 칸반 보드 상태 관리 (백로그→TODO→진행중→완료/실패)
- **주요 클래스:**
  - `TaskBoard`
    - `__init__(pipeline_id: str)`
    - `add_task(task: TaskItem) -> None` — 태스크 투입
    - `claim_task(lane: str, agent_id: str) -> TaskItem | None` — 태스크 소유권 획득
    - `complete_task(task_id: str, result: str) -> None` — 태스크 완료 처리
    - `fail_task(task_id: str, error: str) -> None` — 태스크 실패 처리
    - `get_ready_tasks() -> list[TaskItem]` — depends_on 충족된 태스크 조회
    - `get_state() -> dict` — 전체 보드 상태 (레인별 태스크)
    - `all_done() -> bool` — 전체 완료 여부
    - `has_failures() -> bool` — 실패 태스크 존재 여부
    - `get_retryable() -> list[TaskItem]` — 재시도 가능 태스크 목록
- **의존성:** `core.queue.models.TaskItem`, `core.events.bus.EventBus`
- **LOC:** ~150

#### `queue/worker.py` [P1][PoC→]
- **목적:** AgentWorker — 칸반 레인에서 태스크를 독립 소비하는 워커
- **주요 클래스:**
  - `AgentWorker`
    - `__init__(agent_id, executor: AgentExecutor, board: TaskBoard)`
    - `async process_task(task: TaskItem) -> AgentResult` — 단일 태스크 처리
    - `async run_loop() -> None` — 레인 태스크 연속 소비 루프
    - `async stop() -> None` — 워커 중단
- **의존성:** `core.executor.base.AgentExecutor`, `core.queue.board.TaskBoard`, `core.events.bus.EventBus`
- **LOC:** ~100

---

### 3.6 `src/orchestrator/core/presets/` — 프리셋 시스템

#### `presets/__init__.py` [P2][NEW]
- **목적:** PresetRegistry, AgentPreset, TeamPreset re-export
- **LOC:** ~3

#### `presets/models.py` [P2][NEW]
- **목적:** 프리셋 Pydantic 모델
- **주요 클래스:**
  - `PersonaDef(BaseModel)` — `role`, `goal`, `backstory`, `constraints`
  - `ToolAccess(BaseModel)` — `allowed: list[str]`, `denied: list[str]`
  - `AgentLimits(BaseModel)` — `max_tokens: int`, `timeout: int`, `max_retries: int`
  - `AgentPreset(BaseModel)` — `name`, `persona`, `execution_mode`, `preferred_cli`, `mcp_servers`, `tools`, `limits`
  - `TeamAgentDef(BaseModel)` — `preset: str`, `count: int`, `lane: str`
  - `TeamTaskDef(BaseModel)` — `description`, `assigned_to`, `depends_on`
  - `TeamPreset(BaseModel)` — `name`, `agents`, `tasks`, `workflow`, `synthesis_strategy`
- **의존성:** `pydantic`
- **LOC:** ~80

#### `presets/registry.py` [P2][NEW]
- **목적:** PresetRegistry — YAML 프리셋 로드/저장/조회
- **주요 클래스:**
  - `PresetRegistry`
    - `__init__(preset_dir: Path)`
    - `load_all() -> None` — YAML 파일 일괄 로드
    - `get_agent_preset(name) -> AgentPreset | None`
    - `get_team_preset(name) -> TeamPreset | None`
    - `list_agent_presets() -> list[AgentPreset]`
    - `list_team_presets() -> list[TeamPreset]`
    - `save_agent_preset(preset) -> None` — YAML 파일로 저장
    - `save_team_preset(preset) -> None`
- **의존성:** `pyyaml`, `core.presets.models`
- **LOC:** ~100

---

### 3.7 `src/orchestrator/core/planner/` — LLM 기반 태스크 분해

#### `planner/__init__.py` [P2][NEW]
- **목적:** TaskDecomposer, TeamPlanner re-export
- **LOC:** ~3

#### `planner/decomposer.py` [P2][PoC→]
- **목적:** TaskDecomposer — LLM 호출로 사용자 요청을 서브태스크로 분해
- **주요 클래스:**
  - `TaskDecomposer`
    - `__init__(llm_config: dict)`
    - `async decompose(task: str, *, team_preset: TeamPreset | None) -> list[TaskItem]` — LLM에게 태스크 분해 요청
    - `_build_decomposition_prompt(task, preset) -> str` — 분해 프롬프트 생성
    - `_parse_decomposition(llm_output: str) -> list[TaskItem]` — LLM 출력 파싱
- **의존성:** `litellm`, `core.queue.models.TaskItem`, `core.presets.models.TeamPreset`
- **LOC:** ~120

#### `planner/team_planner.py` [P3][NEW]
- **목적:** TeamPlanner — 팀 프리셋 없이 LLM이 자동으로 팀 구성
- **주요 클래스:**
  - `TeamPlanner`
    - `__init__(llm_config: dict, preset_registry: PresetRegistry)`
    - `async plan_team(task: str) -> TeamPreset` — LLM에게 최적 팀 구성 요청
    - `_build_planning_prompt(task, available_presets) -> str`
    - `_parse_team_plan(llm_output: str) -> TeamPreset`
- **의존성:** `litellm`, `core.presets.registry.PresetRegistry`, `core.presets.models.TeamPreset`
- **LOC:** ~100

---

### 3.8 `src/orchestrator/core/adapters/` — CLI 어댑터

#### `adapters/__init__.py` [P1]
- **목적:** CLIAdapter, ClaudeAdapter 등 public API re-export
- **LOC:** ~5

#### `adapters/base.py` [P1][PoC→]
- **목적:** CLIAdapter ABC — CLI 코딩 도구 어댑터 추상 베이스
- **주요 클래스:**
  - `CLIAdapter(ABC)`
    - `__init__(name: str, timeout: int = 300)`
    - `_build_command(prompt: str, workdir: Path) -> list[str]` — 추상 메서드
    - `_parse_output(stdout: str, stderr: str) -> str` — 추상 메서드
    - `async execute(prompt, workdir, env) -> AgentResult` — asyncio 서브프로세스 실행
    - `async health_check() -> bool` — CLI 가용성 확인
    - `get_capabilities() -> list[str]` — CLI 기능 목록 (선택)
- **의존성:** `asyncio`, `core.executor.base.AgentResult`
- **LOC:** ~80

#### `adapters/claude.py` [P1][PoC→]
- **목적:** ClaudeAdapter — Claude Code CLI 어댑터
- **주요 클래스:**
  - `ClaudeAdapter(CLIAdapter)`
    - `_build_command(prompt, workdir) -> list[str]` — `claude --bare -p ... --output-format json --permission-mode bypassPermissions`
    - `_parse_output(stdout, stderr) -> str` — JSON `result` 필드 추출
    - `_handle_long_prompt(prompt, workdir) -> Path` — stdin 7,000자 제한 대응 (임시 파일)
- **의존성:** `core.adapters.base.CLIAdapter`
- **LOC:** ~70

#### `adapters/codex.py` [P2][PoC→]
- **목적:** CodexAdapter — Codex CLI 어댑터
- **주요 클래스:**
  - `CodexAdapter(CLIAdapter)`
    - `_build_command(prompt, workdir) -> list[str]` — `codex exec --json --ephemeral --full-auto`
    - `_parse_output(stdout, stderr) -> str` — JSON 파싱
- **의존성:** `core.adapters.base.CLIAdapter`
- **LOC:** ~60

#### `adapters/gemini.py` [P2][PoC→]
- **목적:** GeminiAdapter — Gemini CLI 어댑터
- **주요 클래스:**
  - `GeminiAdapter(CLIAdapter)`
    - `_build_command(prompt, workdir) -> list[str]` — `gemini -p ... --output-format stream-json --yolo`
    - `_parse_output(stdout, stderr) -> str` — stream-json에서 `result` 이벤트만 필터링
    - `_filter_stream_json(raw: str) -> str` — stdout 오염 버그 (#21433) 대응
- **의존성:** `core.adapters.base.CLIAdapter`
- **LOC:** ~80

#### `adapters/factory.py` [P2][PoC→]
- **목적:** AdapterFactory — AgentPreset + AuthProvider로부터 AgentExecutor 인스턴스 생성
- **주요 클래스:**
  - `AdapterFactory`
    - `__init__(auth_provider: AuthProvider, config: OrchestratorConfig)`
    - `create(preset: AgentPreset, *, working_dir: str | None) -> AgentExecutor` — 프리셋 기반 실행기 생성
    - `create_cli_executor(cli_name: str, working_dir: Path) -> CLIAgentExecutor` — CLI 실행기 직접 생성
    - `_resolve_adapter(cli_name: str) -> CLIAdapter` — CLI 이름 → 어댑터 인스턴스
    - `_inject_api_key(cli_name: str, env: dict) -> dict` — API 키 환경변수 주입
- **의존성:** `core.adapters.base.CLIAdapter`, `core.auth.provider.AuthProvider`, `core.config.schema.OrchestratorConfig`, `core.presets.models.AgentPreset`
- **LOC:** ~80

---

### 3.9 `src/orchestrator/core/worktree/` — Git worktree

#### `worktree/__init__.py` [P2]
- **목적:** WorktreeManager, FileDiffCollector re-export
- **LOC:** ~3

#### `worktree/manager.py` [P2][PoC→]
- **목적:** WorktreeManager — Git worktree 생성/정리/병합
- **주요 클래스:**
  - `WorktreeManager`
    - `__init__(repo_path: Path, base_dir: Path)`
    - `async create(branch_name: str) -> Path` — worktree 생성 + 새 브랜치
    - `async remove(branch_name: str) -> None` — worktree 제거
    - `async merge(source_branch: str, target_branch: str) -> MergeResult` — 병합
    - `async list_worktrees() -> list[WorktreeInfo]` — 활성 worktree 목록
    - `async cleanup_all() -> None` — 전체 worktree 정리
  - `WorktreeInfo(BaseModel)` — `path`, `branch`, `head_commit`
  - `MergeResult(BaseModel)` — `success`, `conflicts`, `merged_files`
- **의존성:** `asyncio` (subprocess git 명령), `core.errors.exceptions.WorktreeError`
- **LOC:** ~150

#### `worktree/collector.py` [P2][PoC→]
- **목적:** FileDiffCollector — 에이전트 실행 전후 worktree 파일 변경 수집
- **주요 클래스:**
  - `FileDiffCollector`
    - `__init__(worktree_path: str)`
    - `snapshot_before() -> None` — 실행 전 파일 상태 스냅샷
    - `collect_changes() -> list[FileChange]` — 실행 후 변경된 파일 수집
    - `get_diff() -> str` — Git diff 출력
  - `FileChange(BaseModel)` — `path`, `change_type` ("added"/"modified"/"deleted"), `diff`
- **의존성:** `asyncio` (subprocess git), `pydantic`
- **LOC:** ~80

---

### 3.10 `src/orchestrator/core/context/` — 아티팩트 스토어

#### `context/__init__.py` [P2]
- **목적:** ArtifactStore, PromptBuilder re-export
- **LOC:** ~3

#### `context/artifact_store.py` [P2][PoC→]
- **목적:** ArtifactStore — 파일 기반 아티팩트 저장소
- **주요 클래스:**
  - `ArtifactStore`
    - `__init__(base_dir: Path)`
    - `async save(pipeline_id: str, task_id: str, content: str, filename: str) -> Path` — 아티팩트 저장
    - `async load(pipeline_id: str, task_id: str, filename: str) -> str` — 아티팩트 로드
    - `async list_artifacts(pipeline_id: str) -> list[ArtifactInfo]`
    - `async cleanup(pipeline_id: str) -> None`
  - `ArtifactInfo(BaseModel)` — `path`, `task_id`, `filename`, `size_bytes`, `created_at`
- **의존성:** `aiofiles`, `pathlib`
- **LOC:** ~80

#### `context/prompt_builder.py` [P3][NEW]
- **목적:** PromptBuilder — 이전 태스크 결과를 다음 에이전트 프롬프트에 주입
- **주요 클래스:**
  - `PromptBuilder`
    - `build(task: TaskItem, context: dict, artifacts: list[ArtifactInfo]) -> str` — 프롬프트 조립
    - `_inject_persona(prompt: str, persona: PersonaDef) -> str` — 페르소나 주입
    - `_inject_context(prompt: str, prev_results: list[str]) -> str` — 이전 결과 주입
    - `_apply_constraints(prompt: str, constraints: list[str]) -> str` — 제약 조건 추가
- **의존성:** `core.presets.models.PersonaDef`, `core.context.artifact_store.ArtifactInfo`
- **LOC:** ~80

---

### 3.11 `src/orchestrator/core/auth/` — 인증 관리

#### `auth/__init__.py` [P1]
- **목적:** AuthProvider, EnvAuthProvider re-export
- **LOC:** ~3

#### `auth/provider.py` [P1][PoC→]
- **목적:** AuthProvider ABC + EnvAuthProvider 구현
- **주요 클래스:**
  - `AuthProvider(ABC)`
    - `get_key(provider: str) -> str | None` — 추상 메서드
    - `validate() -> dict[str, bool]` — 전체 키 유효성 검사
  - `EnvAuthProvider(AuthProvider)`
    - `__init__(config: OrchestratorConfig)`
    - `get_key(provider: str) -> str | None` — 환경변수에서 키 조회
    - `validate() -> dict[str, bool]` — 각 프로바이더별 키 존재 여부
- **의존성:** `core.config.schema.OrchestratorConfig`
- **LOC:** ~50

#### `auth/key_pool.py` [P3][PoC→]
- **목적:** KeyPool — 여러 API 키를 라운드 로빈/가중치로 분배
- **주요 클래스:**
  - `KeyPool`
    - `__init__(keys: list[str], strategy: str = "round_robin")`
    - `acquire() -> str` — 다음 키 획득
    - `release(key: str) -> None` — 키 반환
    - `mark_exhausted(key: str) -> None` — 소진된 키 비활성화
- **의존성:** `threading.Lock` 또는 `asyncio.Lock`
- **LOC:** ~60

---

### 3.12 `src/orchestrator/core/events/` — 이벤트 시스템

#### `events/__init__.py` [P1]
- **목적:** EventBus, EventType, Event re-export
- **LOC:** ~5

#### `events/types.py` [P1][PoC→]
- **목적:** 이벤트 타입 정의
- **주요 클래스:**
  - `EventType(StrEnum)` — `TASK_SUBMITTED`, `TASK_STARTED`, `TASK_COMPLETED`, `TASK_FAILED`, `AGENT_STARTED`, `AGENT_COMPLETED`, `AGENT_FAILED`, `BOARD_UPDATED`, `PIPELINE_COMPLETED`, `PIPELINE_FAILED`
  - `Event(BaseModel)` — `id`, `type: EventType`, `pipeline_id`, `task_id`, `agent_id`, `data: dict`, `timestamp`
- **의존성:** `pydantic`, `enum`
- **LOC:** ~40

#### `events/bus.py` [P1][PoC→]
- **목적:** EventBus — 비동기 pub/sub + WebSocket 브로드캐스트
- **주요 클래스:**
  - `EventBus`
    - `subscribe(callback: Callable) -> None` — 콜백 등록
    - `unsubscribe(callback: Callable) -> None` — 콜백 해제
    - `async emit(event: Event) -> None` — 이벤트 발행, 모든 구독자에게 전달
    - `_history: list[Event]` — 이벤트 히스토리 (메모리)
    - `get_history(pipeline_id: str | None) -> list[Event]` — 히스토리 조회
- **의존성:** `core.events.types.Event`, `asyncio`
- **LOC:** ~60

#### `events/tracker.py` [P2][PoC→]
- **목적:** EventTracker — 이벤트 기반 진행률 추적
- **주요 클래스:**
  - `EventTracker`
    - `__init__(bus: EventBus)`
    - `get_progress(pipeline_id: str) -> dict` — 완료율, 실패율, 남은 태스크
    - `get_timeline(pipeline_id: str) -> list[Event]` — 시간순 이벤트 목록
- **의존성:** `core.events.bus.EventBus`
- **LOC:** ~50

#### `events/synthesizer.py` [P2][PoC→]
- **목적:** Synthesizer — 다수 에이전트 결과를 종합 보고서로 합성
- **주요 클래스:**
  - `Synthesizer`
    - `__init__(strategy: str = "narrative")` — `"narrative"` | `"structured"` | `"checklist"`
    - `async synthesize(results: list[AgentResult], task: str) -> str` — LLM 호출로 결과 종합
    - `_build_synthesis_prompt(results, task, strategy) -> str` — 종합 프롬프트 생성
- **의존성:** `litellm`, `core.executor.base.AgentResult`
- **LOC:** ~80

---

### 3.13 `src/orchestrator/core/errors/` — 에러 체계

#### `errors/__init__.py` [P1]
- **목적:** 예외 클래스 re-export
- **LOC:** ~10

#### `errors/exceptions.py` [P1][PoC→]
- **목적:** OrchestratorError 계층 구조
- **주요 클래스:**
  - `OrchestratorError(Exception)` — 기본 에러
  - `CLIError(OrchestratorError)` — CLI 실행 에러
    - `CLIExecutionError(CLIError)` — 실행 실패
    - `CLITimeoutError(CLIError)` — 타임아웃
    - `CLIParseError(CLIError)` — 출력 파싱 실패
    - `CLINotFoundError(CLIError)` — CLI 바이너리 없음
  - `AuthError(OrchestratorError)` — 인증 에러
  - `WorktreeError(OrchestratorError)` — Git worktree 에러
  - `MergeConflictError(WorktreeError)` — 병합 충돌
  - `DecompositionError(OrchestratorError)` — 태스크 분해 실패
  - `AllProvidersFailedError(OrchestratorError)` — 모든 프로바이더 실패
- **의존성:** 없음
- **LOC:** ~50

#### `errors/retry.py` [P3][NEW]
- **목적:** RetryPolicy — 지수 백오프 재시도 정책 (tenacity 래퍼)
- **주요 클래스:**
  - `RetryPolicy`
    - `__init__(max_retries, base_delay, max_delay, retryable_errors)`
    - `wrap(func) -> Callable` — tenacity 데코레이터 적용
    - `async execute(func, *args, **kwargs) -> Any` — 재시도 로직 내장 실행
- **의존성:** `tenacity`
- **LOC:** ~50

#### `errors/fallback.py` [P3][NEW]
- **목적:** FallbackChain — CLI 폴백 체인 (Claude 실패 → Codex → Gemini)
- **주요 클래스:**
  - `FallbackChain`
    - `__init__(adapters: list[CLIAdapter], retry_policy: RetryPolicy)`
    - `async execute(prompt, workdir) -> AgentResult` — 순차 폴백 실행
    - `_on_fallback(failed_adapter, next_adapter, error) -> None` — 폴백 이벤트 발행
- **의존성:** `core.adapters.base.CLIAdapter`, `core.errors.retry.RetryPolicy`, `core.events.bus.EventBus`
- **LOC:** ~60

---

### 3.14 `src/orchestrator/core/models/` — Pydantic 공유 모델

#### `models/__init__.py` [P1]
- **목적:** 모델 re-export
- **LOC:** ~5

#### `models/schemas.py` [P1][PoC→]
- **목적:** 공통 스키마 (AgentResult, Agent 등)
- **주요 클래스:**
  - `AgentResult(BaseModel)` — `output`, `exit_code`, `duration_ms`, `agent_name`, `executor_type`, `raw_stdout`, `raw_stderr`, `files_changed`
  - `Agent(BaseModel)` — `id`, `name`, `executor_type`, `status`, `current_task`
- **의존성:** `pydantic`
- **LOC:** ~60

#### `models/pipeline.py` [P1][NEW]
- **목적:** Pipeline, PipelineStatus 모델
- **주요 클래스:**
  - `PipelineStatus(StrEnum)` — `PLANNING`, `EXECUTING`, `COLLECTING`, `COMPLETED`, `FAILED`, `CANCELLED`
  - `Pipeline(BaseModel)` — `id`, `task`, `status`, `team_preset_name`, `created_at`, `completed_at`, `board_state`, `result`, `error`
- **의존성:** `pydantic`, `enum`, `datetime`
- **LOC:** ~50

> **참고:** `TaskItem`, `TaskState`, `Lane` 모델은 `core/queue/models.py`에 정의한다 (도메인 근접성 원칙).

---

### 3.15 `src/orchestrator/api/` — API 계층

#### `api/__init__.py` [P1]
- **목적:** api 패키지 초기화
- **LOC:** ~3

#### `api/app.py` [P1][PoC→]
- **목적:** FastAPI 앱 팩토리
- **주요 함수:**
  - `create_app(engine: OrchestratorEngine) -> FastAPI` — 앱 생성
    - CORS 미들웨어 설정
    - lifespan 핸들러 (시작/종료 시 리소스 관리)
    - 라우터 포함 (routes, ws)
    - 에러 핸들러 등록
- **의존성:** `fastapi`, `core.engine.OrchestratorEngine`, `api.routes`, `api.ws`
- **LOC:** ~60

#### `api/routes.py` [P1][PoC→]
- **목적:** REST 엔드포인트 정의
- **주요 함수:**
  - `router = APIRouter(prefix="/api")`
  - `POST /api/tasks` — `submit_task()`
  - `GET /api/tasks` — `list_tasks()`
  - `GET /api/tasks/{id}` — `get_task()`
  - `POST /api/tasks/{id}/resume` — `resume_task()`
  - `DELETE /api/tasks/{id}` — `cancel_task()`
  - `GET /api/board` — `get_board()`
  - `GET /api/board/lanes` — `get_lanes()`
  - `GET /api/board/tasks/{id}` — `get_board_task()`
  - `GET /api/agents` — `list_agents()`
  - `GET /api/presets/agents` — `list_agent_presets()`
  - `GET /api/presets/teams` — `list_team_presets()`
  - `POST /api/presets/agents` — `create_agent_preset()`
  - `POST /api/presets/teams` — `create_team_preset()`
  - `GET /api/artifacts/{task_id}` — `list_artifacts()`
  - `GET /api/events` — `get_events()`
  - `GET /api/health` — `health_check()`
- **의존성:** `fastapi`, `api.deps`, `core.engine.OrchestratorEngine`, `core.models.schemas`
- **LOC:** ~200

#### `api/ws.py` [P1][PoC→]
- **목적:** WebSocket 이벤트 스트림
- **주요 함수:**
  - `ws_router = APIRouter()`
  - `WS /ws/events` — `websocket_events()` — EventBus 구독 → 클라이언트 실시간 전송
- **의존성:** `fastapi.WebSocket`, `core.events.bus.EventBus`
- **LOC:** ~50

#### `api/deps.py` [P1][NEW]
- **목적:** FastAPI 의존성 주입 팩토리
- **주요 함수:**
  - `get_engine() -> OrchestratorEngine` — 싱글톤 엔진 인스턴스
  - `get_config() -> OrchestratorConfig` — 설정 로딩
  - `get_event_bus() -> EventBus` — 이벤트 버스 인스턴스
- **의존성:** `core.engine.OrchestratorEngine`, `core.config.schema.OrchestratorConfig`, `core.events.bus.EventBus`
- **LOC:** ~40

---

### 3.16 `presets/` — YAML 프리셋 번들

#### `presets/agents/architect.yaml` [P2][NEW]
- **목적:** 시니어 아키텍트 에이전트 프리셋
- **LOC:** ~20

#### `presets/agents/implementer.yaml` [P2][NEW]
- **목적:** 시니어 개발자 (구현) 에이전트 프리셋
- **LOC:** ~20

#### `presets/agents/reviewer.yaml` [P2][NEW]
- **목적:** 코드 리뷰어 에이전트 프리셋
- **LOC:** ~20

#### `presets/agents/elk-analyst.yaml` [P3][NEW]
- **목적:** ELK 분석가 MCP 에이전트 프리셋
- **LOC:** ~25

#### `presets/agents/grafana-monitor.yaml` [P3][NEW]
- **목적:** Grafana 모니터링 MCP 에이전트 프리셋
- **LOC:** ~25

#### `presets/agents/k8s-operator.yaml` [P3][NEW]
- **목적:** K8s 운영자 MCP 에이전트 프리셋
- **LOC:** ~25

#### `presets/teams/feature-team.yaml` [P2][NEW]
- **목적:** 코딩 팀 (architect → implementer → reviewer) 워크플로우 정의
- **LOC:** ~30

#### `presets/teams/incident-analysis.yaml` [P3][NEW]
- **목적:** 장애 분석 팀 (ELK + Grafana + K8s 병렬) 워크플로우 정의
- **LOC:** ~30

#### `presets/teams/deploy-team.yaml` [P3][NEW]
- **목적:** 배포 팀 (모니터링 → 배포 → 검증) 워크플로우 정의
- **LOC:** ~30

---

### 3.17 `frontend/` — React 대시보드 SPA

#### `frontend/package.json` [P2][NEW]
- **목적:** Node.js 의존성 (React, Vite, TypeScript, Tailwind CSS)
- **LOC:** ~40

#### `frontend/tsconfig.json` [P2][NEW]
- **목적:** TypeScript 설정 (strict mode)
- **LOC:** ~20

#### `frontend/vite.config.ts` [P2][NEW]
- **목적:** Vite 빌드 설정 (React plugin, proxy)
- **LOC:** ~20

#### `frontend/index.html` [P2][NEW]
- **목적:** SPA HTML 진입점
- **LOC:** ~15

#### `frontend/src/main.tsx` [P2][NEW]
- **목적:** React 앱 마운트 (ReactDOM.createRoot)
- **의존성:** `react`, `react-dom`, `App`
- **LOC:** ~10

#### `frontend/src/App.tsx` [P2][NEW]
- **목적:** 최상위 App 컴포넌트, React Router 라우팅
- **주요 컴포넌트:** `<App />` — Route 정의 (`/board`, `/pipelines`, `/pipelines/:id`)
- **의존성:** `react-router-dom`, `Layout`, `BoardView`, `PipelineList`, `PipelineDetail`
- **LOC:** ~40

#### `frontend/src/api/client.ts` [P2][NEW]
- **목적:** REST API 클라이언트 (fetch wrapper)
- **주요 함수:** `submitTask()`, `getTasks()`, `getTask()`, `cancelTask()`, `getBoard()`, `getAgents()`, `getPresets()`, `getHealth()`
- **LOC:** ~80

#### `frontend/src/api/websocket.ts` [P2][NEW]
- **목적:** WebSocket 클라이언트 (/ws/events 연결)
- **주요 함수:** `connectWebSocket(onEvent)`, `disconnectWebSocket()`
- **LOC:** ~40

#### `frontend/src/types/index.ts` [P2][NEW]
- **목적:** TypeScript 타입 정의 (Python 모델과 동기화)
- **주요 타입:** `Pipeline`, `TaskItem`, `TaskState`, `Agent`, `Event`, `AgentPreset`, `TeamPreset`, `BoardState`
- **LOC:** ~60

#### `frontend/src/hooks/useBoard.ts` [P2][NEW]
- **목적:** 칸반 보드 상태 관리 React 훅
- **주요 훅:** `useBoard()` — board API 호출 + WebSocket 실시간 업데이트
- **LOC:** ~40

#### `frontend/src/hooks/useEvents.ts` [P2][NEW]
- **목적:** WebSocket 이벤트 구독 React 훅
- **주요 훅:** `useEvents(pipelineId?)` — WebSocket 연결 관리, 이벤트 목록 반환
- **LOC:** ~50

#### `frontend/src/hooks/usePipeline.ts` [P2][NEW]
- **목적:** 파이프라인 상태 관리 React 훅
- **주요 훅:** `usePipeline(id)` — 파이프라인 상세 조회 + 폴링
- **LOC:** ~30

#### `frontend/src/components/Layout.tsx` [P2][NEW]
- **목적:** 앱 레이아웃 (사이드바 네비게이션 + 메인 콘텐츠)
- **LOC:** ~40

#### `frontend/src/components/BoardView.tsx` [P2][NEW]
- **목적:** 칸반 보드 뷰 (레인별 카드 배치)
- **의존성:** `useBoard`, `LaneColumn`, `TaskCard`
- **LOC:** ~60

#### `frontend/src/components/TaskCard.tsx` [P2][NEW]
- **목적:** 칸반 태스크 카드 (상태 뱃지, 에이전트 이름, 진행률)
- **LOC:** ~40

#### `frontend/src/components/LaneColumn.tsx` [P2][NEW]
- **목적:** 칸반 레인 컬럼 (TODO, IN_PROGRESS, DONE, FAILED)
- **LOC:** ~30

#### `frontend/src/components/AgentStatus.tsx` [P2][NEW]
- **목적:** 에이전트 상태 인디케이터 (idle/running/error)
- **LOC:** ~30

#### `frontend/src/components/PipelineList.tsx` [P2][NEW]
- **목적:** 파이프라인 목록 (테이블 뷰)
- **LOC:** ~50

#### `frontend/src/components/PipelineDetail.tsx` [P2][NEW]
- **목적:** 파이프라인 상세 뷰 (보드 + 결과 + 이벤트 로그)
- **의존성:** `usePipeline`, `BoardView`, `EventLog`, `ResultViewer`
- **LOC:** ~60

#### `frontend/src/components/EventLog.tsx` [P2][NEW]
- **목적:** 이벤트 로그 (실시간 스트림, 타임스탬프 + 타입 + 데이터)
- **의존성:** `useEvents`
- **LOC:** ~50

#### `frontend/src/components/TaskSubmitForm.tsx` [P2][NEW]
- **목적:** 태스크 제출 폼 (task 입력 + team_preset 선택 + repo 경로)
- **LOC:** ~60

#### `frontend/src/components/PresetSelector.tsx` [P3][NEW]
- **목적:** 프리셋 선택 드롭다운 (에이전트/팀 프리셋)
- **LOC:** ~40

#### `frontend/src/components/ResultViewer.tsx` [P3][NEW]
- **목적:** 결과 마크다운 렌더러 (Synthesizer 출력 표시)
- **의존성:** `react-markdown`
- **LOC:** ~40

#### `frontend/src/styles/global.css` [P2][NEW]
- **목적:** 전역 스타일 (Tailwind CSS directives 또는 CSS Modules 기반)
- **LOC:** ~30

---

### 3.18 `tests/` — 테스트

테스트 파일의 상세 내용은 `docs/testing.md`에서 정의한다. 여기서는 파일 구조만 명시한다.

| 테스트 카테고리 | 파일 수 | Phase |
|----------------|---------|-------|
| `tests/unit/` | 28개 | P1: 16, P2: 8, P3: 4 |
| `tests/integration/` | 6개 | P2: 5, P3: 1 |
| `tests/e2e/` | 5개 | P3: 4, conftest 1 |
| `tests/api/` | 8개 | P1: 4, P2: 4 |
| `tests/mocks/` | 3개 | P1: 3 |
| **합계** | **50개** | |

---

### 3.19 `scripts/` — 스크립트

#### `scripts/setup_dev.sh` [P1][NEW]
- **목적:** 개발 환경 원클릭 셋업 (uv 설치 확인, 의존성 설치, pre-commit 설정)
- **LOC:** ~40

#### `scripts/run_integration.sh` [P2][NEW]
- **목적:** 통합 테스트 실행 스크립트 (API 키 존재 확인 + pytest 실행)
- **LOC:** ~30

---

### 3.20 `.github/workflows/` — CI

#### `.github/workflows/ci.yml` [P1][NEW]
- **목적:** PR 유닛 테스트 + 린트 (push/PR 시 자동)
- **Job:** `lint` (ruff + mypy) → `test` (pytest + coverage, Python 3.12/3.13 매트릭스)
- **LOC:** ~60

#### `.github/workflows/integration.yml` [P2][NEW]
- **목적:** 통합 테스트 (수동 트리거 + 주간 스케줄)
- **Job:** `integration` (실 CLI 설치 + API 키 + pytest)
- **LOC:** ~60

---

## 4. Phase별 파일 수 요약

| Phase | 신규 파일 | PoC 리팩터링 | 합계 | 누적 LOC (추정) |
|-------|----------|-------------|------|-----------------|
| **Phase 1** | 31 | 18 | 49 | ~2,500 |
| **Phase 2** | 38 | 8 | 46 | ~4,800 |
| **Phase 3** | 16 | 3 | 19 | ~6,200 |
| **합계** | **85** | **29** | **114** | **~6,200** |

### Phase 1 파일 목록 (49개)

**소스 (27개):**
- `src/orchestrator/__init__.py`, `__main__.py`, `cli.py`
- `src/orchestrator/core/__init__.py`, `engine.py`, `utils.py`
- `src/orchestrator/core/config/__init__.py`, `schema.py`, `loader.py`
- `src/orchestrator/core/executor/__init__.py`, `base.py`, `cli_executor.py`
- `src/orchestrator/core/queue/__init__.py`, `models.py`, `board.py`, `worker.py`
- `src/orchestrator/core/adapters/__init__.py`, `base.py`, `claude.py`
- `src/orchestrator/core/auth/__init__.py`, `provider.py`
- `src/orchestrator/core/events/__init__.py`, `bus.py`, `types.py`
- `src/orchestrator/core/errors/__init__.py`, `exceptions.py`
- `src/orchestrator/core/models/__init__.py`, `schemas.py`, `pipeline.py`
- `src/orchestrator/api/__init__.py`, `app.py`, `routes.py`, `ws.py`, `deps.py`

**테스트 (25개+):**
- `tests/conftest.py`
- `tests/unit/__init__.py`, `tests/unit/core/__init__.py`
- `tests/unit/core/test_engine.py`
- `tests/unit/core/config/__init__.py`, `test_schema.py`, `test_loader.py`
- `tests/unit/core/executor/__init__.py`, `test_base_executor.py`, `test_cli_executor.py`
- `tests/unit/core/queue/__init__.py`, `test_models.py`, `test_board.py`, `test_worker.py`
- `tests/unit/core/adapters/__init__.py`, `test_base_adapter.py`, `test_claude.py`
- `tests/unit/core/auth/__init__.py`, `test_provider.py`
- `tests/unit/core/events/__init__.py`, `test_bus.py`, `test_types.py`
- `tests/unit/core/errors/__init__.py`, `test_exceptions.py`
- `tests/unit/core/models/__init__.py`, `test_schemas.py`, `test_pipeline.py`
- `tests/unit/api/__init__.py`, `test_routes.py`, `test_ws.py`, `test_deps.py`
- `tests/unit/test_cli.py`
- `tests/api/__init__.py`, `conftest.py`, `test_task_endpoints.py`, `test_health_endpoint.py`
- `tests/mocks/__init__.py`, `mock_adapter.py`, `mock_executor.py`
- `tests/mocks/fixtures/claude_response.json`, `claude_error.json`

**설정 (6개):**
- `pyproject.toml`, `.env.example`, `.pre-commit-config.yaml`, `.gitignore`
- `scripts/setup_dev.sh`
- `.github/workflows/ci.yml`

---

## 5. 내부 의존성 그래프 (순환 참조 금지)

```
Layer 0 (최하위):  models/schemas.py, models/pipeline.py, queue/models.py,
                   errors/exceptions.py, events/types.py
                       ↑
Layer 1:           config/schema.py, config/loader.py, utils.py
                       ↑
Layer 2:           auth/provider.py, events/bus.py
                       ↑
Layer 3:           adapters/base.py, executor/base.py
                       ↑
Layer 4:           adapters/{claude,codex,gemini}.py, executor/cli_executor.py
                   adapters/factory.py
                       ↑
Layer 5:           queue/board.py, context/artifact_store.py
                       ↑
Layer 6:           queue/worker.py, worktree/manager.py, worktree/collector.py
                   events/tracker.py, events/synthesizer.py
                       ↑
Layer 7:           presets/models.py, presets/registry.py
                       ↑
Layer 8:           planner/decomposer.py, planner/team_planner.py
                   context/prompt_builder.py
                   errors/retry.py, errors/fallback.py
                       ↑
Layer 9 (최상위):  engine.py
                       ↑
API Layer:         api/deps.py → api/app.py → api/routes.py, api/ws.py
                       ↑
Interface Layer:   cli.py, __main__.py
```

**규칙:**
- 하위 Layer는 상위 Layer를 import 하지 않는다
- `engine.py`는 Core 계층의 단일 진입점이다
- `api/` 계층은 `engine.py`만 import 한다 (Core 내부 모듈 직접 참조 금지)
- `cli.py`는 `engine.py` 또는 `api/` 계층만 import 한다
- `models/`, `errors/`, `events/types.py`는 어디서든 import 가능 (Layer 0)
