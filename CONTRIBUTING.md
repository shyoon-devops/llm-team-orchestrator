# Contributing

## Development Setup

```bash
# Clone
git clone <repo-url>
cd agent-team-orchestrator

# Install with dev dependencies
uv sync --dev

# Run checks
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest tests/unit/ tests/api/ -v
```

## Code Quality

- **Linter/Formatter**: ruff (replaces black + isort + flake8)
- **Type Checking**: mypy (strict mode)
- **Tests**: pytest + pytest-asyncio

All checks must pass before committing.

## Project Structure

```
src/orchestrator/
  api/          # FastAPI routes, WebSocket, deps
  core/
    adapters/   # CLI wrappers (Claude, Codex, Gemini)
    auth/       # Authentication providers
    config/     # Configuration schema + loader
    context/    # Artifact store, checkpointing
    engine.py   # OrchestratorEngine (main entry point)
    errors/     # Exception hierarchy, retry, fallback
    events/     # EventBus, Synthesizer, event types
    executor/   # AgentExecutor (CLI, MCP)
    models/     # Pydantic data models
    planner/    # TeamPlanner (task decomposition)
    presets/    # Preset models + registry
    queue/      # TaskBoard, TaskItem, AgentWorker
    worktree/   # WorktreeManager, FileDiffCollector
  cli.py        # Typer CLI
tests/
  unit/         # Unit tests
  api/          # API integration tests
  e2e/          # End-to-end scenario tests
```

## Commit Messages

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `test:` test additions/changes
- `refactor:` code refactoring

## Testing

```bash
# Unit + API tests (default, fast)
uv run pytest tests/unit/ tests/api/ -v

# E2E tests (slower, mocked executors)
uv run pytest tests/e2e/ -v

# With coverage
uv run pytest --cov=orchestrator --cov-report=term-missing
```
