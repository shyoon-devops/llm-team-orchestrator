---
name: python-conventions
description: Python 코드 컨벤션 — conventions.md 기반 자동 적용
---

# Python 코드 컨벤션

이 프로젝트의 Python 코드 작성 시 반드시 따를 것.

## Import 순서
1. `from __future__ import annotations` (항상 첫 줄)
2. stdlib
3. third-party
4. local (absolute import only: `from orchestrator.core.xxx`)

## TYPE_CHECKING 패턴
```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from orchestrator.core.queue.board import TaskBoard
```

## 네이밍
- 클래스: `PascalCase` (예: `TaskBoard`, `AgentExecutor`)
- 함수/변수: `snake_case` (예: `submit_task`, `task_id`)
- 상수: `UPPER_SNAKE` (예: `MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- private: `_prefix` (예: `_run_loop`, `_tasks`)

## Async
- IO-bound 함수는 모두 `async def`
- subprocess: `asyncio.create_subprocess_exec` (shell=True 금지)
- 큐: `asyncio.Queue`
- 병렬: `asyncio.gather`

## Pydantic
- 데이터 모델: `BaseModel`
- 파싱: `model_validate()`
- 직렬화: `model_dump()`
- Enum: `StrEnum`

## Docstring (Google style)
```python
async def submit_task(self, task: str, *, team_preset: str | None = None) -> Pipeline:
    """태스크를 제출하고 파이프라인을 시작한다.

    Args:
        task: 자연어 태스크 설명.
        team_preset: 팀 프리셋 이름. None이면 자동 구성.

    Returns:
        생성된 Pipeline 객체.

    Raises:
        DecompositionError: 태스크 분해 실패 시.
    """
```

## 에러 처리
- 구체적 예외만 catch (bare `except:` 금지)
- exception chaining: `raise XError(...) from e`
- `contextlib.suppress()` for best-effort cleanup

## 로깅
- `structlog.get_logger()` 사용
- `print()` 절대 금지
- key=value 구조화: `log.info("task_submitted", task_id=tid, team=preset)`

## 3-Layer 의존 규칙
- `core/` → 외부 프레임워크 import 금지 (FastAPI, typer 등)
- `api/` → `core/` 만 import
- `cli.py` → httpx로 API 호출만
