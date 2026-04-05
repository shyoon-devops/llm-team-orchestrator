# CLAUDE.md — LLM Team Orchestrator PoC

## Project Overview

Multi-LLM CLI team coding orchestrator PoC. Combines Claude Code, Codex CLI, Gemini CLI into a coordinated team using LangGraph for orchestration.

## Tech Stack

- **Language**: Python 3.12+
- **Package Manager**: uv
- **Orchestration**: LangGraph (StateGraph, TypedDict state, checkpointing)
- **Models**: Pydantic v2
- **CLI**: Typer
- **Logging**: structlog
- **Error Handling**: tenacity (retry) + aiobreaker (circuit breaker)
- **Web Backend**: FastAPI + uvicorn (★ PoC)
- **Web Frontend**: React + Vite + TypeScript (★ PoC)
- **Auth**: cryptography (Fernet encryption for key pool)
- **Config**: PyYAML + Pydantic validation
- **Testing**: pytest + pytest-asyncio + httpx (AsyncClient)
- **Lint/Format**: ruff
- **Type Check**: mypy (strict mode)

## Commands

```bash
# Install dependencies
uv sync --dev

# Run tests
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v -m integration  # requires real CLIs

# Lint & format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/

# Run demo (mock adapters)
uv run python -m orchestrator.poc.demo

# Start web server (★ PoC)
uv run uvicorn orchestrator.web.app:app --host 0.0.0.0 --port 3000

# Frontend (★ PoC)
cd frontend && npm install && npm run dev   # Dev server on :5173
cd frontend && npm run build                # Production build
```

## Architecture

```
src/orchestrator/
├── adapters/     # CLIAdapter ABC + Claude/Codex/Gemini implementations
├── auth/         # EnvAuthProvider + KeyPool (round-robin multi-key)
├── config/       # YAML config loader + Pydantic schema (OrchestratorConfig)
├── context/      # ArtifactStore (file-based context sharing)
├── errors/       # Exception hierarchy + retry + circuit breaker
├── events/       # EventBus (asyncio pub/sub) + EventType enum
├── graph/        # LangGraph state, nodes (plan/implement/review), builder
├── models/       # Pydantic schemas (AgentResult, PipelineStatus, etc.)
├── web/          # ★ FastAPI app, REST routes (/api/*), WebSocket (/ws/events)
├── cli.py        # Typer CLI entrypoint
└── poc/          # ★ PoC-only (remove at MVP transition)

frontend/         # ★ React dashboard (remove at MVP transition)
├── src/components/  # AgentStatusPanel, EventLog, ArtifactViewer, TaskSubmitForm
├── src/hooks/       # useWebSocket, useApi
└── src/types/       # TypeScript interfaces
```

## Conventions

- **Commits**: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`)
- **PoC-only files**: Marked with `★ PoC 전용` comment — directories: `src/orchestrator/poc/`, `src/orchestrator/web/`, `tests/poc/`, `frontend/`
- **Imports**: Use absolute imports (`from orchestrator.models.schemas import AgentResult`)
- **Async**: All CLI adapter methods are async (asyncio.create_subprocess_exec)
- **Type annotations**: All public functions must have complete type annotations
- **Tests**: Unit tests use MockCLIAdapter; integration tests use `@pytest.mark.integration`
- **Enums**: Use `StrEnum` for JSON-serializable enums (EventType, AgentStatus, TaskStatus)

## Key Patterns

- **CLIAdapter ABC**: `run(prompt, timeout) -> AgentResult` + `health_check() -> bool`
- **OrchestratorState**: TypedDict with `messages: Annotated[list[dict], operator.add]`
- **EventBus**: `subscribe(callback)` / `publish(event)` — asyncio pub/sub connecting LangGraph nodes → WebSocket
- **KeyPool**: Round-robin API key rotation with exhaustion marking and cooldown
- **Error hierarchy**: `OrchestratorError → CLIError → CLIExecutionError | CLITimeoutError | CLIParseError | CLINotFoundError`
- **Retry**: tenacity with exponential backoff, max 3 attempts
- **Circuit breaker**: aiobreaker, fail_max=3, timeout_duration=30s

## API Endpoints (★ PoC)

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/tasks | Submit new task (background pipeline) |
| GET | /api/tasks | List all pipelines |
| GET | /api/agents | List agent statuses |
| GET | /api/artifacts | List artifacts |
| GET | /api/events | Get event history |
| WS | /ws/events | Real-time event stream |

## Out of Scope (PoC)

- Git worktree parallel isolation
- Production secret management (Vault, Doppler)
- MCP/A2A protocol integration
- Docker sandboxing
- Distributed deployment
- Cost analysis
