---
name: testing-patterns
description: 테스트 작성 패턴 — testing.md 기반
---

# 테스트 작성 패턴

## 파일 매핑
```
src/orchestrator/core/engine.py → tests/unit/test_engine.py
src/orchestrator/core/queue/board.py → tests/unit/test_board.py
src/orchestrator/api/routes.py → tests/api/test_routes.py
```

## 유닛 테스트 패턴
```python
"""Unit tests for {모듈명}."""
from __future__ import annotations
import pytest
from orchestrator.core.xxx import TargetClass

@pytest.fixture
def instance() -> TargetClass:
    return TargetClass(...)

class TestTargetClass:
    async def test_method_success(self, instance: TargetClass) -> None:
        result = await instance.method(...)
        assert result.field == expected

    async def test_method_failure(self, instance: TargetClass) -> None:
        with pytest.raises(SpecificError, match="expected message"):
            await instance.method(invalid_input)
```

## API 테스트 패턴
```python
"""API tests for {엔드포인트}."""
import httpx
import pytest
from orchestrator.api.app import create_app

@pytest.fixture
async def client():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

class TestEndpoint:
    async def test_post_success(self, client: httpx.AsyncClient) -> None:
        resp = await client.post("/api/tasks", json={"task": "..."})
        assert resp.status_code == 201
```

## 규칙
- 모든 테스트 함수: `async def test_*`
- Fixture: conftest.py에 공통, 테스트 파일에 개별
- Mock: `MockCLIAdapter`, `MockAgentExecutor` (conftest.py에 정의)
- CLI subprocess 호출 시: `cwd=tempfile.mkdtemp()` (sandbox)
- 마커: `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`
