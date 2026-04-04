---
name: test
description: Run project test suite
---

# Run Tests

```bash
# Unit tests (always run)
uv run pytest tests/unit/ -v --tb=short

# Integration tests (requires real CLIs)
uv run pytest tests/integration/ -v -m integration --tb=short

# Full suite with coverage
uv run pytest tests/ -v --cov=orchestrator --cov-report=term-missing
```
