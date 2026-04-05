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
