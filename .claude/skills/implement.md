---
name: implement
description: Implement a feature following project conventions
---

# Implement Feature

1. Read the relevant section in poc-plan.md for the spec
2. Create the file with proper type annotations
3. Add `★ PoC 전용` comment if it's a PoC-only file
4. Use absolute imports (`from orchestrator.models.schemas import ...`)
5. Run `uv run ruff check` and `uv run mypy src/` to verify
6. Write corresponding unit tests in `tests/unit/`
7. Run `uv run pytest tests/unit/ -v` to verify
