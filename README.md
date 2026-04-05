# Agent Team Orchestrator

> Multi-LLM agent team orchestrator: coordinate Claude Code, Codex CLI, and Gemini CLI as a collaborative team.

## Quick Start

```bash
# Install
uv sync --dev

# Run CLI
uv run orchestrator --help

# Start API server
uv run orchestrator serve

# Submit a task
uv run orchestrator run "Implement JWT auth middleware" --team-preset feature-team --wait
```

## Features

- **Agent Presets**: Define agents with persona + tools + constraints in YAML
- **Team Composition**: Combine presets or let the orchestrator auto-compose
- **Kanban Task Board**: Agents independently consume tasks from lanes
- **DAG Dependencies**: Subtask execution respects dependency ordering
- **Result Synthesis**: Synthesizer merges multi-agent outputs into reports
- **Error Handling**: Retry with exponential backoff, CLI fallback chains
- **Checkpointing**: SQLite-backed pipeline state for resume after failure
- **Real-time Events**: WebSocket streaming with subscription filtering
- **Git Worktree Isolation**: Each agent works in its own branch

## Architecture

```
[CLI / Web / MCP] -> [API (FastAPI)] -> [OrchestratorEngine]
                                           |-- TeamPlanner (decomposition)
                                           |-- TaskBoard (kanban queue)
                                           |-- AgentWorker (per-lane consumer)
                                           |-- AgentExecutor (CLI + MCP)
                                           |-- PresetRegistry (YAML presets)
                                           |-- Synthesizer (result aggregation)
                                           |-- WorktreeManager (git isolation)
                                           |-- CheckpointStore (resume support)
                                           \-- EventBus (real-time events)
```

## API

- `POST /api/tasks` -- submit task
- `GET /api/tasks` -- list pipelines
- `GET /api/tasks/{id}` -- pipeline detail
- `POST /api/tasks/{id}/resume` -- resume failed pipeline
- `DELETE /api/tasks/{id}` -- cancel pipeline
- `GET /api/board` -- kanban board state
- `GET /api/board/tasks/{id}` -- board task detail
- `GET /api/agents` -- agent worker status
- `GET /api/presets/agents` -- agent presets
- `GET /api/presets/teams` -- team presets
- `GET /api/artifacts/{task_id}` -- pipeline artifacts
- `GET /api/events` -- event history
- `GET /api/health` -- health check
- `WS /ws/events` -- real-time event stream

## Development

```bash
# Lint + format
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/

# Type check
uv run mypy src/

# Tests
uv run pytest tests/unit/ tests/api/ -v
```

## License

MIT
