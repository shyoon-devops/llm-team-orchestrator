# Phase 1 Implementation Checklist

## T1.1 Project scaffolding
- [x] pyproject.toml with exact dependencies
- [x] .python-version (3.12)
- [x] src/orchestrator/__init__.py with __version__
- [x] src/orchestrator/__main__.py
- [x] uv sync --dev

## T1.2 Core models + errors
- [x] core/models/schemas.py (AgentResult, AdapterConfig)
- [x] core/models/pipeline.py (PipelineStatus, SubTask, FileChange, WorkerResult, Pipeline)
- [x] core/errors/exceptions.py (full hierarchy: 18 exception classes)
- [x] __init__.py for each package

## T1.3 Core events
- [x] core/events/types.py (EventType with 30 types, OrchestratorEvent)
- [x] core/events/bus.py (EventBus with subscribe/emit/history)

## T1.4 Core adapters
- [x] core/adapters/base.py (CLIAdapter ABC, _NPM_BIN, stdin=DEVNULL, cwd)
- [x] core/adapters/claude.py (--system-prompt, --permission-mode, --output-format json)
- [x] core/adapters/codex.py (--full-auto --json, JSONL parsing)
- [x] core/adapters/gemini.py (--output-format stream-json --sandbox=none, result filtering)
- [x] core/adapters/factory.py (AdapterFactory)

## T1.5 Core executor
- [x] core/executor/base.py (AgentExecutor ABC)
- [x] core/executor/cli_executor.py (CLIAgentExecutor)
- [x] core/executor/mcp_executor.py (MCPAgentExecutor stub)
- [x] core/events/synthesizer.py (Synthesizer)

## T1.6 Core queue
- [x] core/queue/models.py (TaskState, TaskItem)
- [x] core/queue/board.py (TaskBoard with multi-lane, depends_on DAG, retry)
- [x] core/queue/worker.py (AgentWorker with claim->run->complete/fail loop)

## T1.7 Core auth, config, context, worktree
- [x] core/auth/provider.py (AuthProvider ABC, EnvAuthProvider)
- [x] core/config/schema.py (OrchestratorConfig with pydantic-settings)
- [x] core/config/loader.py
- [x] core/context/artifact_store.py
- [x] core/worktree/manager.py (WorktreeManager)
- [x] core/worktree/collector.py (FileDiffCollector)
- [x] core/presets/models.py (PersonaDef, AgentPreset, TeamPreset, etc.)
- [x] core/presets/registry.py (PresetRegistry)
- [x] core/utils.py (generate_id, truncate, setup_logging, run_with_timeout)

## T1.8 Core OrchestratorEngine
- [x] core/engine.py (15 methods: submit_task, get_pipeline, list_pipelines, cancel_task, resume_task, list_agent_presets, list_team_presets, save_agent_preset, save_team_preset, get_board_state, list_agents, subscribe, get_events, _execute_pipeline)

## T1.9 API layer
- [x] api/app.py (FastAPI factory with lifespan)
- [x] api/deps.py (Engine singleton DI)
- [x] api/routes.py (REST endpoints: tasks CRUD, board, agents, presets, events, health)
- [x] api/ws.py (WebSocket manager + /ws/events handler)

## T1.10 CLI
- [x] cli.py (typer: run, status, cancel, presets, serve)

## T1.11 Test infrastructure
- [x] tests/conftest.py (common fixtures)
- [x] tests/unit/conftest.py
- [x] tests/api/conftest.py (httpx AsyncClient)
- [x] Unit tests: models (7), errors (9), events (9), queue (14), auth (5), config (3), adapters (6), executor (3), worker (3), engine (12)
- [x] API tests (5)

## T1.12 Final verification
- [x] ruff check src/ tests/ -- All checks passed
- [x] ruff format --check src/ tests/ -- 79 files already formatted
- [x] mypy src/ -- Success: no issues found in 48 source files
- [x] pytest tests/unit/ tests/api/ -v -- 78 passed

---

# Phase 2 Implementation Checklist

## T2.1 Preset Models + Registry
- [x] core/presets/models.py verified — PersonaDef, ToolAccess, AgentLimits, MCPServerDef, AgentPreset, TeamAgentDef, TeamTaskDef, TeamPreset
- [x] core/presets/registry.py upgraded — YAML scanning, _normalize_agent_yaml, _normalize_team_yaml, file I/O save, search path priority

## T2.2 Preset YAML Bundles
- [x] presets/agents/architect.yaml — CLI(claude), 시니어 소프트웨어 아키텍트
- [x] presets/agents/implementer.yaml — CLI(codex), 시니어 백엔드 개발자
- [x] presets/agents/reviewer.yaml — CLI(claude), 시니어 코드 리뷰어
- [x] presets/agents/tester.yaml — CLI(codex), QA 엔지니어
- [x] presets/agents/security-auditor.yaml — CLI(claude), 시니어 보안 감사자
- [x] presets/agents/elk-analyst.yaml — MCP(elasticsearch), ELK 로그 분석 전문가
- [x] presets/teams/feature-team.yaml — DAG: 설계→구현→리뷰+테스트
- [x] presets/teams/incident-analysis-team.yaml — parallel: ELK 분석
- [x] presets/teams/review-team.yaml — parallel: 보안 감사 + 코드 리뷰

## T2.3 TeamPlanner
- [x] core/planner/team_planner.py — plan_team(preset) + plan_team(auto stub)
- [x] _plan_from_preset: TeamTaskDef → SubTask 변환, depends_on 매핑, CLI 해석
- [x] _plan_auto: 기본 implementer 팀 반환 (LLM 자동 구성은 향후 구현)
- [x] _resolve_cli: preset_registry 기반 CLI 해석

## T2.4 Preset API + CLI
- [x] GET /api/presets/agents — 에이전트 프리셋 목록
- [x] GET /api/presets/agents/{name} — 에이전트 프리셋 상세
- [x] POST /api/presets/agents — 에이전트 프리셋 생성 (409 중복)
- [x] GET /api/presets/teams — 팀 프리셋 목록
- [x] GET /api/presets/teams/{name} — 팀 프리셋 상세
- [x] POST /api/presets/teams — 팀 프리셋 생성 (409 중복)
- [x] CLI: orchestrator presets list — 전체 프리셋 테이블 출력
- [x] CLI: orchestrator presets show <name> — 프리셋 상세 출력

## T2.5 Tests
- [x] tests/unit/test_preset_models.py — 27 tests (PersonaDef, ToolAccess, AgentLimits, MCPServerDef, AgentPreset, TeamAgentDef, TeamTaskDef, TeamPreset)
- [x] tests/unit/test_registry.py — 26 tests (init, load, list, save, merge, deep_merge, search path priority)
- [x] tests/unit/test_planner.py — 15 tests (preset-based planning, auto planning, validation, CLI resolution)
- [x] tests/api/test_presets.py — 13 tests (list/get/create agent+team presets, error cases)

## T2.6 Final verification
- [x] ruff check src/ tests/ -- All checks passed
- [x] ruff format --check src/ tests/ -- All files formatted
- [x] mypy src/ -- Success: no issues found in 49 source files
- [x] pytest tests/unit/ tests/api/ -v -- 159 passed (78 Phase 1 + 81 Phase 2)

---

# Phase 3 Implementation Checklist (Branch B — Hybrid Orchestration)

## T3.1 Engine Integration — submit_task uses Hybrid flow
- [x] _execute_pipeline() fully implements Hybrid orchestration:
  - PENDING → PLANNING: TeamPlanner.plan_team() decomposes task into subtasks
  - PLANNING → RUNNING: SubTasks → TaskItems on TaskBoard, AgentWorker per lane started
  - RUNNING: Workers consume tasks from board via polling loop
  - RUNNING → SYNTHESIZING: All tasks done → Synthesizer.synthesize() generates report
  - SYNTHESIZING → COMPLETED/PARTIAL_FAILURE: Pipeline finalized with results + synthesis
- [x] _create_executor_for_preset(): creates CLIAgentExecutor from AgentPreset (persona, CLI adapter, config)
- [x] _stop_pipeline_workers(): cleanup helper for stopping pipeline-scoped workers
- [x] Background task tracking via _bg_tasks dict (per pipeline)
- [x] Cancellation support: _execute_pipeline checks for CANCELLED status during execution loop
- [x] Error handling: all subtask failures → FAILED, partial failures → PARTIAL_FAILURE

## T3.2 LangGraph Planning Graph (stub — uses TeamPlanner directly)
- [x] TeamPlanner from Phase 2 handles decomposition (no separate LangGraph graph needed for MVP)
- [x] _plan_from_preset: TeamTaskDef → SubTask with depends_on DAG
- [x] _plan_auto: single implementer fallback when no preset given

## T3.3 Worktree + FileDiff Integration
- [x] WorktreeManager.create() called per lane when target_repo is set
- [x] cwd passed to executor via _create_executor_for_preset()
- [x] FileDiffCollector.collect_changes() after workers complete
- [x] WorktreeManager.merge_to_target() added — merges worktree branch to target
- [x] WorktreeManager.cleanup() in finally block
- [x] WORKTREE_CREATED / WORKTREE_MERGED events emitted

## T3.4 Full Pipeline E2E Tests
- [x] tests/unit/test_hybrid_pipeline.py — 11 tests:
  - test_submit_task_creates_pipeline
  - test_pipeline_decomposes_and_distributes
  - test_pipeline_respects_dependencies
  - test_pipeline_synthesizes_results
  - test_pipeline_with_target_repo (worktree mock)
  - test_pipeline_handles_all_subtasks_failed
  - test_cancel_during_execution
  - test_submit_empty_task_raises
  - test_submit_task_invalid_preset_raises
  - test_pipeline_auto_team_creates_single_subtask
  - test_board_state_after_pipeline

## T3.5 Final verification
- [x] ruff check src/ tests/ -- All checks passed
- [x] ruff format -- All files formatted
- [x] mypy src/ -- Success: no issues found in 49 source files
- [x] pytest tests/unit/ tests/api/ -v -- 170 passed (78 Phase 1 + 81 Phase 2 + 11 Phase 3)

---

# Phase 4 Implementation Checklist (Branch B — Error Handling + Synthesizer)

## T4.1 FallbackChain
- [x] core/errors/fallback.py — FallbackChain class
  - cli_priority 순서대로 시도, 첫 성공 결과 반환
  - CLIError/CLITimeoutError → 다음 CLI로 폴백
  - AuthError → skip (재시도 없음)
  - AllProvidersFailedError when all exhausted
  - FALLBACK_TRIGGERED / FALLBACK_SUCCEEDED / FALLBACK_EXHAUSTED 이벤트 발행
- [x] core/errors/exceptions.py — AllProvidersFailedError.__init__ 추가 (task_id, attempted 파라미터)

## T4.2 RetryPolicy
- [x] core/errors/retry.py — RetryPolicy class with tenacity
  - 지수 백오프: 1s, 2s, 4s (configurable)
  - 재시도 대상: CLITimeoutError, CLIExecutionError (exit 137/139 제외)
  - 재시도 불가: AuthError, CLINotFoundError, CLIParseError
  - max_attempts 초과 시 마지막 예외 reraise
  - before_sleep 로깅 콜백

## T4.3 Partial Failure Handling
- [x] core/engine.py — _execute_pipeline 부분 실패 처리 업그레이드
  - 0% 실패 → COMPLETED (정상 종합)
  - 1~49% 실패 → PARTIAL_FAILURE (성공 결과로 종합, 실패 태스크 표시)
  - 50~100% 실패 → FAILED (파이프라인 실패, 결과 보존)
  - 이벤트에 fail_count, success_count, fail_ratio 포함

## T4.4 Synthesizer Production
- [x] core/events/synthesizer.py — Template-based 종합기로 업그레이드
  - Strategy 패턴: narrative / structured / checklist
  - narrative: 자연어 보고서 (배경→에이전트별 결과→결론)
  - structured: 구조화 보고서 (상태 요약 표 + 서브태스크 상세 표 + 결과 본문)
  - checklist: 체크리스트 ([x] / [ ] 형태, 진행률 표시)
  - 실패 태스크 정보 포함 (실패 노트 섹션)
  - 성공/실패 분류 후 적절한 요약 메시지 생성

## T4.5 Error Scenario Tests
- [x] tests/unit/test_fallback.py — 8 tests
  - test_fallback_first_cli_succeeds
  - test_fallback_tries_next_on_timeout
  - test_fallback_skips_auth_error
  - test_fallback_all_failed_raises
  - test_fallback_emits_event
  - test_fallback_exhausted_emits_event
  - test_fallback_single_cli_success
  - test_fallback_mixed_errors
- [x] tests/unit/test_retry.py — 9 tests
  - test_retry_on_timeout
  - test_retry_on_execution_error
  - test_no_retry_on_auth_error
  - test_no_retry_on_cli_not_found
  - test_no_retry_on_parse_error
  - test_max_retries_then_fail
  - test_retry_succeeds_on_first_try
  - test_retry_policy_custom_config
  - test_retry_context_passed
- [x] tests/unit/test_partial_failure.py — 10 tests
  - test_all_success_pipeline
  - test_partial_success_pipeline
  - test_majority_fail_pipeline
  - test_all_fail_pipeline
  - test_partial_failure_events
  - test_synthesizer_includes_failures
  - test_synthesizer_narrative_all_success
  - test_synthesizer_structured_strategy
  - test_synthesizer_checklist_strategy
  - test_synthesizer_empty_results

## T4.6 Final verification
- [x] ruff check src/ tests/ -- All checks passed
- [x] ruff format --check src/ tests/ -- 90 files already formatted
- [x] mypy src/ -- Success: no issues found in 51 source files
- [x] pytest tests/unit/ tests/api/ -v -- 197 passed (170 Phase 1-3 + 27 Phase 4)

---

# Phase 5 Implementation Checklist (Branch A -- Checkpointing + React Dashboard)

## T5.1 Checkpointing
- [x] core/context/checkpoint.py -- CheckpointStore class
  - SQLite-backed storage via standard sqlite3 module
  - save(pipeline_id, pipeline) -- upsert with ON CONFLICT
  - load(pipeline_id) -> Pipeline | None -- deserialize from JSON
  - list_checkpoints() -> list[str] -- ordered by updated_at DESC
  - delete(pipeline_id) -- remove checkpoint
  - Auto-creates DB file and parent directories
- [x] Engine integration: checkpoint saves at every state transition
  - PENDING -> PLANNING (with started_at)
  - After subtask decomposition (subtasks recorded)
  - PLANNING -> RUNNING
  - RUNNING -> SYNTHESIZING
  - COMPLETED / PARTIAL_FAILURE / FAILED (final states)
  - Exception handler (FAILED with error)
- [x] Config: checkpoint_enabled + checkpoint_db_path in OrchestratorConfig (already existed)

## T5.2 Resume
- [x] engine.resume_task(task_id) upgraded with checkpoint-based restore
  - Loads from checkpoint if not in memory (server restart scenario)
  - Validates resumable status (FAILED, PARTIAL_FAILURE only)
  - Resets failed TaskBoard tasks to TODO state
  - Clears pipeline error, sets status to RUNNING
  - Saves updated checkpoint
  - Emits PIPELINE_RUNNING event with resumed=True flag
- [x] API endpoint: POST /api/tasks/{id}/resume (already existed in routes.py)
- [x] CLI command: orchestrator resume <task-id>
  - Added to cli.py with KeyError/ValueError handling
  - Prints pipeline_id and status on success

## T5.3 React Dashboard
- [x] frontend/ project scaffolding
  - Vite + React 19 + TypeScript
  - package.json with vitest, @testing-library/react
  - vite.config.ts with API/WS proxy to localhost:8000
  - tsconfig.json (strict mode, ES2020)
  - Dark theme CSS (index.css with CSS variables)
- [x] Types (src/types.ts)
  - Pipeline, SubTask, WorkerResult, FileChange, TaskItem, AgentStatus, WSEvent, BoardState
- [x] Hooks
  - useWebSocket: exponential backoff reconnection, rolling event buffer (max 200)
  - useApi: usePipelines, useBoard, useAgents (auto-refresh), submitTask, resumeTask, cancelTask
- [x] Components
  - KanbanBoard: 5-column layout (backlog/todo/in_progress/done/failed), flattens all lanes
  - PipelineList: table view with status badges, Resume/Cancel action buttons
  - AgentStatusPanel: worker list with lane and status badges
  - TaskSubmitForm: task description + optional team_preset + target_repo
  - EventLog: real-time WebSocket events, newest first, Clear button
  - ResultViewer: synthesis report viewer + subtask results, Close button
- [x] App.tsx: root layout with header (connection status), grid layout

## T5.4 Tests
- [x] Backend tests
  - tests/unit/core/context/test_checkpoint.py -- 8 tests
    - test_checkpoint_save_load
    - test_checkpoint_load_nonexistent
    - test_checkpoint_overwrite
    - test_list_checkpoints
    - test_delete_checkpoint
    - test_delete_nonexistent
    - test_checkpoint_db_directory_creation
    - test_checkpoint_preserves_pipeline_fields
  - tests/unit/test_resume.py -- 8 tests
    - test_resume_from_checkpoint
    - test_resume_nonexistent
    - test_resume_already_completed
    - test_resume_running_pipeline
    - test_resume_partial_failure
    - test_resume_emits_event
    - test_resume_saves_checkpoint
    - test_resume_no_checkpoint_store
- [x] Frontend tests (6 test files, vitest)
  - PipelineList.test.tsx -- 5 tests (loading, empty, row render, resume/cancel buttons)
  - KanbanBoard.test.tsx -- 3 tests (null board, column headers, task cards)
  - TaskSubmitForm.test.tsx -- 2 tests (form inputs, disabled button)
  - EventLog.test.tsx -- 4 tests (empty/disconnected states, event items, clear button)
  - AgentStatusPanel.test.tsx -- 2 tests (empty state, agent list)
  - ResultViewer.test.tsx -- 4 tests (null pipeline, synthesis, subtask results, close button)

## T5.5 Final verification
- [x] ruff check src/ tests/ -- All checks passed
- [x] ruff format --check src/ tests/ -- 94 files already formatted
- [x] mypy src/ -- Success: no issues found in 52 source files
- [x] pytest tests/unit/ tests/api/ -v -- 213 passed (197 Phase 1-4 + 16 Phase 5)
- [ ] npm test -- (requires npm install; sandbox restriction)
- [ ] npm run build -- (requires npm install; sandbox restriction)
