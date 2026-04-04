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
- **Testing**: pytest + pytest-asyncio
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
```

## Architecture

```
src/orchestrator/
├── adapters/     # CLIAdapter ABC + Claude/Codex/Gemini implementations
├── auth/         # EnvAuthProvider (env-based for PoC)
├── context/      # ArtifactStore (file-based context sharing)
├── errors/       # Exception hierarchy + retry + circuit breaker
├── graph/        # LangGraph state, nodes (plan/implement/review), builder
├── models/       # Pydantic schemas (AgentResult, TaskConfig, AdapterConfig)
├── cli.py        # Typer CLI entrypoint
└── poc/          # ★ PoC-only (remove at MVP transition)
```

## Conventions

- **Commits**: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`)
- **PoC-only files**: Marked with `★ PoC 전용` comment — directories: `src/orchestrator/poc/`, `tests/poc/`, `examples/`, `scripts/`
- **Imports**: Use absolute imports (`from orchestrator.models.schemas import AgentResult`)
- **Async**: All CLI adapter methods are async (asyncio.create_subprocess_exec)
- **Type annotations**: All public functions must have complete type annotations
- **Tests**: Unit tests use MockCLIAdapter; integration tests use `@pytest.mark.integration`

## Key Patterns

- **CLIAdapter ABC**: `run(prompt, timeout) -> AgentResult` + `health_check() -> bool`
- **OrchestratorState**: TypedDict with `messages: Annotated[list[dict], operator.add]`
- **Error hierarchy**: `OrchestratorError → CLIError → CLIExecutionError | CLITimeoutError | CLIParseError | CLINotFoundError`
- **Retry**: tenacity with exponential backoff, max 3 attempts
- **Circuit breaker**: aiobreaker, fail_max=3, timeout_duration=30s

## Out of Scope (PoC)

- Git worktree parallel isolation
- Web UI / dashboard
- Production secret management (Vault, Doppler)
- MCP/A2A protocol integration
- Docker sandboxing
- Distributed deployment
- Cost analysis
