# LLM Team Orchestrator

Multi-LLM CLI team coding orchestrator — combines Claude Code, Codex CLI, and Gemini CLI into a coordinated **plan → implement → review** pipeline using LangGraph.

> **Status**: PoC (v0.2.0) — core pipeline + web dashboard + auth management

## Quick Start

```bash
# Install dependencies
uv sync --dev

# Run demo (mock adapters, no real CLI needed)
uv run python -m orchestrator.poc.demo

# Run via CLI
uv run orchestrator run "Implement user auth" --mock

# Start web dashboard (★ PoC)
uv run uvicorn orchestrator.web.app:app --host 0.0.0.0 --port 3000

# Run tests
uv run pytest tests/ -v
```

### Frontend (★ PoC)

```bash
cd frontend
npm install && npm run dev    # Dev server on :5173
npm run build                 # Production build (61KB gzipped)
```

## Architecture

```
Task → [Plan Node] → [Implement Node] → [Review Node] → Result
         (Claude)       (Codex)           (Gemini)
              ↕              ↕               ↕
           EventBus ← → WebSocket → React Dashboard
```

Each node uses a **CLIAdapter** to call the underlying CLI tool in headless mode. Artifacts are shared between nodes via an **ArtifactStore**. An **EventBus** publishes node lifecycle events to the **WebSocket** layer for real-time dashboard updates.

## Project Structure

```
src/orchestrator/
├── adapters/       # CLIAdapter ABC + Claude/Codex/Gemini implementations
├── auth/           # EnvAuthProvider + KeyPool (round-robin multi-key)
├── config/         # YAML config loader + Pydantic schema
├── context/        # File-based artifact store for context sharing
├── errors/         # Exception hierarchy + retry + circuit breaker
├── events/         # EventBus (asyncio pub/sub) + event types
├── graph/          # LangGraph state, nodes, and graph builder
├── models/         # Pydantic schemas (AgentResult, PipelineStatus, etc.)
├── web/            # ★ FastAPI app, REST routes, WebSocket manager
├── cli.py          # Typer CLI entrypoint
└── poc/            # ★ PoC-only mock adapters and demo

frontend/           # ★ React + Vite + TypeScript dashboard
├── src/components/ # AgentStatusPanel, EventLog, ArtifactViewer, TaskSubmitForm
├── src/hooks/      # useWebSocket (auto-reconnect), useApi
└── src/types/      # TypeScript interfaces
```

## Development

```bash
uv run ruff check src/ tests/     # Lint
uv run ruff format src/ tests/    # Format
uv run mypy src/                   # Type check (strict)
uv run pytest tests/ -v            # All tests (68 tests)
```

## PoC Hypotheses

| # | Hypothesis | Status |
|---|-----------|--------|
| H1 | Claude Code CLI headless subprocess | ✅ Adapter implemented |
| H2 | Codex CLI headless subprocess | ✅ Adapter implemented |
| H3 | Gemini CLI headless subprocess | ✅ Adapter implemented |
| H4 | LangGraph 3-node orchestration | ✅ Verified (40 tests) |
| H5 | Inter-agent context sharing | ✅ ArtifactStore working |
| H6 | Auto-recovery on errors | ✅ Retry + circuit breaker |
| H7 | FastAPI real-time status | ✅ REST + WebSocket |
| H8 | React web dashboard | ✅ Agent/event/artifact views |
| H9 | Encrypted multi-key auth | ✅ KeyPool round-robin |
| H10 | Declarative YAML config | ✅ Pydantic-validated |
| H11 | EventBus observability | ✅ asyncio pub/sub + WS |
| H12 | Web UI task submission | ✅ POST → background pipeline |
