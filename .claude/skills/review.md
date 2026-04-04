---
name: review
description: Review code for quality and convention compliance
---

# Review Code

Check for:
1. Type annotations on all public functions
2. Proper exception handling using the project's exception hierarchy
3. Async patterns (no blocking calls in async functions)
4. PoC-only markers where appropriate
5. ruff compliance (`uv run ruff check`)
6. mypy strict compliance (`uv run mypy src/`)
7. Test coverage for the changed code
