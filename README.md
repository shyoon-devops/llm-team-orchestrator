# LLM Team Orchestrator

Multi-LLM CLI team coding orchestrator — combines Claude Code, Codex CLI, and Gemini CLI into a coordinated **plan → implement → review** pipeline using LangGraph.

> **Status**: PoC (v0.1.0) — validates core architecture with mock adapters

## Quick Start

```bash
# Install dependencies
uv sync --dev

# Run demo (mock adapters, no real CLI needed)
uv run python -m orchestrator.poc.demo

# Run via CLI
uv run orchestrator run "Implement user auth" --mock

# Run tests
uv run pytest tests/unit/ -v
```

## Architecture

```
Task → [Plan Node] → [Implement Node] → [Review Node] → Result
         (Claude)       (Codex)           (Gemini)
```

Each node uses a **CLIAdapter** to call the underlying CLI tool in headless mode. Artifacts are shared between nodes via an **ArtifactStore**.

## Project Structure

```
src/orchestrator/
├── adapters/       # CLIAdapter ABC + Claude/Codex/Gemini implementations
├── auth/           # API key management (env-based for PoC)
├── context/        # File-based artifact store for context sharing
├── errors/         # Exception hierarchy + retry + circuit breaker
├── graph/          # LangGraph state, nodes, and graph builder
├── models/         # Pydantic schemas (AgentResult, TaskConfig)
├── cli.py          # Typer CLI entrypoint
└── poc/            # PoC-only mock adapters and demo (★)
```

## Development

```bash
uv run ruff check src/ tests/     # Lint
uv run ruff format src/ tests/    # Format
uv run mypy src/                   # Type check (strict)
uv run pytest tests/ -v            # All tests
```

## PoC Hypotheses

| # | Hypothesis | Status |
|---|-----------|--------|
| H1 | Claude Code CLI headless subprocess | Adapter implemented |
| H2 | Codex CLI headless subprocess | Adapter implemented |
| H3 | Gemini CLI headless subprocess | Adapter implemented |
| H4 | LangGraph 3-node orchestration | Verified with mock |
| H5 | Inter-agent context sharing | ArtifactStore working |
| H6 | Auto-recovery on errors | Retry + circuit breaker |
