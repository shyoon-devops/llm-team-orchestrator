# 코드 컨벤션 + 개발 원칙 + 방법론 명세

> v1.0 | 2026-04-05
> SPEC.md 기준 작성

---

## 1. 코드 컨벤션

### 1.1 Python 스타일 (ruff)

모든 Python 코드는 **ruff**로 린트 및 포맷팅한다.

#### pyproject.toml — `[tool.ruff]` 설정

```toml
[tool.ruff]
target-version = "py312"
line-length = 99
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "A",      # flake8-builtins
    "C4",     # flake8-comprehensions
    "DTZ",    # flake8-datetimez
    "T20",    # flake8-print (print() 사용 금지)
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking (TYPE_CHECKING 강제)
    "RUF",    # ruff-specific rules
    "ASYNC",  # flake8-async
    "S",      # flake8-bandit (보안)
    "PT",     # flake8-pytest-style
    "RET",    # flake8-return
    "ARG",    # flake8-unused-arguments
]
ignore = [
    "S101",   # assert 허용 (테스트에서 사용)
    "S603",   # subprocess 호출 허용 (CLI adapter 핵심 기능)
    "S607",   # partial executable path 허용
    "B008",   # Depends() in FastAPI 허용
]

[tool.ruff.lint.isort]
known-first-party = ["orchestrator"]
force-single-line = false
lines-after-imports = 2
section-order = [
    "future",
    "standard-library",
    "third-party",
    "first-party",
    "local-folder",
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
    "S101",   # assert 허용
    "ARG",    # unused arguments 허용 (fixtures)
    "S106",   # hardcoded passwords 허용 (test fixtures)
]
"src/orchestrator/cli.py" = [
    "T20",    # CLI에서 print 허용 (typer output)
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
docstring-code-format = true
```

#### Import 순서

ruff의 `isort` 규칙(`I`)이 자동 정렬한다. 수동 작성 시 아래 순서를 따른다:

```python
# 1. future
from __future__ import annotations

# 2. standard library
import asyncio
import json
from pathlib import Path

# 3. third-party
from pydantic import BaseModel
import structlog

# 4. first-party (orchestrator)
from orchestrator.core.models import TaskItem
from orchestrator.core.errors import CLIError

# 5. local-folder (같은 패키지 내 — 가능하면 회피)
from .base import AgentExecutor
```

**규칙:** `from .module import X` 형태의 relative import는 같은 패키지 내 `__init__.py`에서만 허용한다. 그 외에는 **absolute import만 사용**한다.

```python
# Good
from orchestrator.core.executor.base import AgentExecutor

# Bad
from ..executor.base import AgentExecutor
```

---

### 1.2 네이밍 규칙

| 대상 | 스타일 | 예시 |
|------|--------|------|
| 클래스 | `PascalCase` | `AgentExecutor`, `TaskBoard`, `CLIAdapter` |
| 함수 / 메서드 | `snake_case` | `submit_task()`, `health_check()` |
| 변수 | `snake_case` | `task_item`, `retry_count` |
| 상수 | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Private 멤버 | `_prefix` | `_event_bus`, `_parse_output()` |
| 파일명 | `snake_case.py` | `agent_executor.py`, `task_board.py` |
| 디렉토리명 | `snake_case` | `core/`, `worktree/` |
| 환경변수 | `UPPER_SNAKE_CASE` | `ORCH_API_PORT`, `CLAUDE_API_KEY` |
| YAML 키 | `snake_case` | `preferred_cli`, `max_retries` |
| API 경로 | `kebab-case` 금지, `snake_case` | `/api/tasks`, `/api/board/lanes` |
| Enum 멤버 | `UPPER_SNAKE_CASE` | `TaskState.IN_PROGRESS` |

**약어 규칙:**
- 2글자 약어: 모두 대문자 (`CLIAdapter`, `MCPServer`, `IO`)
- 3글자 이상 약어: PascalCase (`Mcp` 아님, `MCP` 사용)

---

### 1.3 타입 힌트

#### 필수 규칙

```python
# 모든 파일 첫 줄
from __future__ import annotations

# 모든 public 함수에 완전한 타입 힌트
async def submit_task(
    self,
    task: str,
    *,
    team_preset: str | None = None,
    target_repo: Path | None = None,
) -> Pipeline:
    ...

# 변수 타입이 명확하지 않은 경우 annotation
results: list[AgentResult] = []
callback: Callable[[Event], None] | None = None
```

#### `TYPE_CHECKING` 패턴 (circular import 방지)

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrator.core.engine import OrchestratorEngine
    from orchestrator.core.models import Pipeline

class TaskBoard:
    def __init__(self, engine: OrchestratorEngine) -> None:
        self._engine = engine

    async def get_pipeline(self, task_id: str) -> Pipeline | None:
        ...
```

#### 타입 힌트 스타일 가이드

| 패턴 | 사용 | 미사용 |
|------|------|--------|
| Union | `str \| None` | `Optional[str]`, `Union[str, None]` |
| 리스트 | `list[str]` | `List[str]` |
| 딕셔너리 | `dict[str, Any]` | `Dict[str, Any]` |
| 튜플 | `tuple[str, int]` | `Tuple[str, int]` |
| Callable | `Callable[[str], None]` | (동일) |
| Self 반환 | `-> Self` (Python 3.11+) | `-> "ClassName"` |

#### mypy 설정

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
disallow_untyped_calls = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_reexport = true
warn_redundant_casts = true
warn_unused_ignores = true
show_error_codes = true
namespace_packages = true
explicit_package_bases = true
mypy_path = "src"

[[tool.mypy.overrides]]
module = [
    "langgraph.*",
    "litellm.*",
]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_untyped_calls = false
```

---

### 1.4 Async 규칙

| 규칙 | 설명 |
|------|------|
| IO-bound 함수는 모두 `async` | 파일 I/O, 네트워크, subprocess |
| CLI 호출 | `asyncio.create_subprocess_exec()` 사용 — `subprocess.run()` 금지 |
| 큐 기반 조율 | `asyncio.Queue` for TaskBoard ↔ Worker 통신 |
| 동시 실행 | `asyncio.gather()` 또는 `asyncio.TaskGroup` for 병렬 에이전트 실행 |
| Lock | `asyncio.Lock` for 공유 상태 (board state) 보호 |
| Timeout | 모든 외부 호출에 `asyncio.wait_for(coro, timeout=)` 적용 |
| Event loop | `asyncio.run()` 사용은 `cli.py` 진입점에서만 — 내부에서 절대 사용 금지 |

```python
# Good: CLI subprocess 호출
async def _execute_cli(self, cmd: list[str], timeout: float) -> str:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=self._workdir,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except TimeoutError:
        proc.kill()
        raise CLITimeoutError(cmd=cmd, timeout=timeout)
    if proc.returncode != 0:
        raise CLIExecutionError(cmd=cmd, stderr=stderr.decode())
    return stdout.decode()

# Bad: 동기 subprocess
import subprocess
result = subprocess.run(cmd, capture_output=True)  # 금지
```

---

### 1.5 Docstring

**Google 스타일** docstring을 사용한다.

```python
class AgentExecutor(ABC):
    """에이전트 실행을 위한 추상 기본 클래스.

    모든 에이전트 유형(CLI, MCP, Mock)은 이 ABC를 상속하여
    run()과 health_check()를 구현한다.

    Attributes:
        executor_type: 실행기 유형 ("cli" | "mcp" | "mock").
        name: 에이전트 인스턴스 이름.
    """

    @abstractmethod
    async def run(
        self,
        prompt: str,
        *,
        timeout: float = 300.0,
        context: dict[str, str] | None = None,
    ) -> AgentResult:
        """프롬프트를 실행하고 결과를 반환한다.

        Args:
            prompt: 에이전트에게 전달할 작업 프롬프트.
            timeout: 최대 실행 시간(초). 기본값 300초.
            context: 이전 태스크 결과 등 추가 컨텍스트.

        Returns:
            실행 결과를 담은 AgentResult.

        Raises:
            CLITimeoutError: timeout 초과 시.
            CLIExecutionError: CLI 프로세스가 비정상 종료 시.
        """
```

| 대상 | Docstring 필수 여부 |
|------|---------------------|
| Public 클래스 | 필수 |
| Public 메서드/함수 | 필수 |
| `__init__` | 필수 (복잡한 경우) |
| Private 메서드 (`_prefix`) | 복잡한 로직인 경우만 |
| 테스트 함수 | 불필요 (함수명이 설명) |
| 모듈 레벨 | 선택 (패키지의 `__init__.py`에는 권장) |

---

### 1.6 Enum

JSON 직렬화를 위해 `StrEnum`을 사용한다.

```python
from enum import StrEnum


class TaskState(StrEnum):
    """칸반 보드 태스크 상태."""

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class ExecutorType(StrEnum):
    """에이전트 실행기 유형."""

    CLI = "cli"
    MCP = "mcp"
    MOCK = "mock"


class WorkflowType(StrEnum):
    """팀 워크플로우 유형."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    DAG = "dag"
```

**규칙:**
- 모든 Enum은 `StrEnum` 상속 — JSON 직렬화 시 `.value` 호출 불필요
- Enum 멤버 값은 `snake_case` 문자열
- Pydantic 모델에서 직접 사용 가능

---

### 1.7 Pydantic

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class TaskItem(BaseModel):
    """칸반 보드의 개별 태스크."""

    id: str = Field(description="고유 태스크 ID (ULID)")
    title: str = Field(description="태스크 제목")
    lane: str = Field(description="할당 레인 (에이전트 이름)")
    state: TaskState = Field(default=TaskState.BACKLOG)
    depends_on: list[str] = Field(default_factory=list)
    assigned_to: str | None = Field(default=None)
    result: str = Field(default="")
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    pipeline_id: str = Field(default="")

    model_config = {"frozen": False, "extra": "forbid"}
```

| 패턴 | 사용 | 설명 |
|------|------|------|
| 데이터 정의 | `BaseModel` | 모든 도메인 모델 |
| 파싱 | `model_validate(data)` | dict/JSON → 모델 |
| 직렬화 | `model_dump()` | 모델 → dict |
| JSON 직렬화 | `model_dump_json()` | 모델 → JSON 문자열 |
| 설정 | `BaseSettings` (pydantic-settings) | 환경변수 로딩 |
| `extra` | `"forbid"` (기본) | 알 수 없는 필드 거부 |
| Immutable 모델 | `frozen=True` | 이벤트, 결과 등 |

---

### 1.8 Error Handling

```python
# Good: 구체적 예외만 catch
try:
    result = await executor.run(prompt, timeout=timeout)
except CLITimeoutError:
    logger.warning("agent_timeout", agent=agent.name, timeout=timeout)
    raise
except CLIExecutionError as e:
    logger.error("agent_execution_failed", agent=agent.name, error=str(e))
    raise TaskExecutionError(task_id=task.id, cause=e) from e

# Bad: bare except
try:
    result = await executor.run(prompt)
except:  # 절대 금지
    pass

# Bad: 너무 넓은 except
try:
    result = await executor.run(prompt)
except Exception:  # 최소한 로깅 필수, 가능하면 구체적 예외 사용
    pass
```

| 규칙 | 설명 |
|------|------|
| 구체적 예외만 catch | `except CLIError`, `except TimeoutError` 등 |
| `bare except:` 금지 | ruff `E722` 규칙으로 강제 |
| `from e` 필수 | 예외 체이닝: `raise NewError() from e` |
| `Exception` catch | 최상위 핸들러(API endpoint, worker loop)에서만 허용 |
| 에러 로깅 | `structlog` 사용, key=value 포맷 |
| 재시도 vs 전파 | 재시도 가능한 에러만 retry, 그 외 즉시 전파 |

---

### 1.9 Logging

**`structlog`**을 사용하며, `print()` 사용은 금지한다 (ruff `T20` 규칙).

```python
import structlog

logger = structlog.get_logger()

# 구조화된 로깅
logger.info("task_submitted", task_id=task.id, team=team_preset)
logger.warning("agent_timeout", agent=agent.name, timeout=timeout)
logger.error("cli_execution_failed", cmd=cmd, returncode=proc.returncode)

# context binding
log = logger.bind(pipeline_id=pipeline.id, phase="decomposition")
log.info("decomposition_started", subtask_count=len(subtasks))
log.info("decomposition_completed")
```

| 규칙 | 설명 |
|------|------|
| Logger 생성 | `structlog.get_logger()` — 모듈 레벨에서 한 번 |
| 이벤트명 | `snake_case` — `"task_submitted"`, `"agent_timeout"` |
| 데이터 | keyword arguments — `task_id=...`, `agent=...` |
| 민감 정보 | API 키, 토큰 절대 로깅 금지 |
| 성능 데이터 | `duration_ms=...` 형태로 기록 |
| `print()` 사용 | `cli.py`에서 사용자 출력 용도로만 허용 |

---

### 1.10 Commit 메시지

**Conventional Commits** 형식을 따른다.

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Type 목록

| Type | 용도 | 예시 |
|------|------|------|
| `feat` | 새 기능 | `feat(executor): add MCP injection to CLIAdapter` |
| `fix` | 버그 수정 | `fix(adapter): handle claude stdin >7000 chars` |
| `test` | 테스트 추가/수정 | `test(board): add TaskBoard concurrent access tests` |
| `docs` | 문서 | `docs: add deployment specification` |
| `chore` | 빌드/설정 | `chore: update ruff config` |
| `refactor` | 리팩토링 | `refactor(queue): extract lane management` |
| `perf` | 성능 개선 | `perf(worktree): parallelize branch creation` |
| `ci` | CI/CD | `ci: add GitHub Actions workflow` |

#### 규칙
- Subject는 50자 이내, 소문자 시작, 마침표 없음
- Body는 72자 줄바꿈
- Breaking change: `feat!:` 또는 footer에 `BREAKING CHANGE:`
- Scope는 모듈 디렉토리 이름: `executor`, `adapter`, `board`, `web`, `cli`

---

### 1.11 Branch 전략

```
main ──────────────────────────────────────── (stable, PoC → MVP merge)
  │
  └── mvp ──────────────────────────────────── (MVP development)
        │
        ├── feat/executor-mcp ──────────── (feature branch)
        ├── feat/board-dag ─────────────── (feature branch)
        ├── fix/gemini-stdout ──────────── (bugfix branch)
        └── test/adapter-integration ───── (test branch)
```

| 브랜치 | 용도 | Merge 대상 |
|--------|------|------------|
| `main` | 안정 릴리스 | - |
| `mvp` | MVP 개발 | `main` (PR) |
| `feat/<scope>-<name>` | 기능 개발 | `mvp` (PR) |
| `fix/<scope>-<name>` | 버그 수정 | `mvp` (PR) |
| `test/<scope>-<name>` | 테스트 추가 | `mvp` (PR) |

---

## 2. 개발 원칙

### 2.1 3-Layer 의존 규칙

```
┌────────────────────────────────────────┐
│ Interface (CLI, Web Dashboard)         │ ← 의존 방향
├────────────────────────────────────────┤
│ API (FastAPI REST + WebSocket)         │ ← 의존 방향
├────────────────────────────────────────┤
│ Core (Engine, Board, Executor, ...)    │
└────────────────────────────────────────┘
```

| 규칙 | 설명 | 예시 |
|------|------|------|
| Core는 API를 모른다 | `core/` 내에서 `api/` import 금지 | `from orchestrator.api.routes import ...` 금지 |
| API는 Interface를 모른다 | `api/` 내에서 `cli.py` import 금지 | `from orchestrator.cli import ...` 금지 |
| 역방향 import 금지 | 하위 계층이 상위 계층 import 금지 | Core → API 금지, API → CLI 금지 |
| Interface → API 직접 호출 | CLI는 httpx로 API 호출 | CLI → REST API → Engine |
| API → Core 직접 호출 | API 핸들러가 Engine 메서드 호출 | `engine.submit_task()` |

#### 허용/금지 import 매트릭스

| From \ To | `core/` | `api/` | `cli.py` |
|-----------|---------|--------|----------|
| `core/` | O (내부 모듈 간) | **X** | **X** |
| `api/` | O | O (내부 모듈 간) | **X** |
| `cli.py` | **X** (httpx 사용) | **X** (httpx 사용) | - |

**CLI는 Core와 API를 import하지 않는다.** CLI는 HTTP client(httpx)로 API 서버에 요청을 보내는 thin client다.

---

### 2.2 Core는 프레임워크 무관

`core/` 디렉토리 내부에서는 외부 프레임워크를 import하지 않는다.

| 금지 import (core/ 내) | 대안 |
|-------------------------|------|
| `from fastapi import ...` | API 계층에서 처리 |
| `import typer` | CLI 계층에서 처리 |
| `import uvicorn` | 진입점에서 처리 |
| `from starlette import ...` | API 계층에서 처리 |

**허용 import (core/ 내):**
- `pydantic` — 도메인 모델 정의
- `structlog` — 로깅
- `asyncio` — 비동기 실행
- `langgraph` — 오케스트레이션 그래프 (planner 모듈)
- `litellm` — LLM 호출 (planner, synthesizer 모듈)
- `pydantic_settings` — 설정 로딩 (config 모듈)

---

### 2.3 API-first

CLI는 API를 호출하는 **thin client**다. 비즈니스 로직을 CLI에 작성하지 않는다.

```python
# Good: CLI → httpx → API → Engine
# cli.py
@app.command()
def run(task: str, team: str | None = None) -> None:
    response = httpx.post(
        f"{base_url}/api/tasks",
        json={"task": task, "team_preset": team},
    )
    pipeline = response.json()
    typer.echo(f"Pipeline started: {pipeline['id']}")

# Bad: CLI → Engine 직접 호출
@app.command()
def run(task: str, team: str | None = None) -> None:
    engine = OrchestratorEngine()  # 금지
    pipeline = asyncio.run(engine.submit_task(task))  # 금지
```

---

### 2.4 프리셋 = 도메인 지식

코어 코드에 도메인 특화 로직을 하드코딩하지 않는다. 도메인 지식은 YAML 프리셋에만 존재한다.

```python
# Bad: 코어에 도메인 하드코딩
class IncidentAnalyzer:
    def analyze(self):
        elk_query = "status:500 AND service:payment"  # 금지

# Good: 프리셋 YAML에 도메인 지식
# presets/agents/elk-analyst.yaml
persona:
  role: "ELK 로그 분석가"
  constraints:
    - "최근 1시간 로그만 분석"
    - "status:5xx 에러에 집중"
```

---

### 2.5 테스트 필수

소스 코드 변경 시 반드시 테스트를 작성하고 실행한 후 커밋한다.

```bash
# 커밋 전 필수 실행
uv run pytest tests/ -x --tb=short
uv run ruff check src/ tests/
uv run mypy src/
```

#### pytest 설정

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--strict-markers",
    "--strict-config",
    "-x",
    "--tb=short",
    "--cov=orchestrator",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
]
markers = [
    "unit: 단위 테스트 (mock 사용, 외부 의존 없음)",
    "integration: 통합 테스트 (실제 CLI 호출 포함)",
    "slow: 느린 테스트 (timeout >10s)",
    "e2e: 엔드투엔드 테스트 (API 서버 필요)",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:langgraph.*",
]
```

#### 테스트 디렉토리 구조

```
tests/
├── conftest.py              # 공통 fixtures
├── unit/
│   ├── test_executor.py
│   ├── test_adapter.py
│   ├── test_board.py
│   ├── test_presets.py
│   ├── test_worktree.py
│   └── test_events.py
├── integration/
│   ├── test_cli_adapter.py
│   └── test_engine.py
└── e2e/
    ├── test_api.py
    └── test_pipeline.py
```

#### 테스트 커버리지 기준

| 모듈 | 최소 커버리지 |
|------|---------------|
| `core/executor/` | 90% |
| `core/queue/` | 90% |
| `core/adapters/` | 85% |
| `core/presets/` | 85% |
| `core/engine.py` | 85% |
| `api/` | 80% |
| `cli.py` | 70% |
| 전체 | 80% |

---

### 2.6 CLI Sandbox

subprocess 호출 시 반드시 `cwd=tempdir`로 작업 디렉토리를 격리한다.

```python
# Good: sandbox 디렉토리에서 실행
async def run(self, prompt: str, *, timeout: float = 300.0) -> AgentResult:
    workdir = self._worktree_manager.get_workdir(self._agent_name)
    proc = await asyncio.create_subprocess_exec(
        *self._build_cmd(prompt),
        cwd=workdir,  # 반드시 격리된 디렉토리
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=self._filtered_env(),  # 필터링된 환경변수만 전달
    )
    ...

# Bad: 현재 디렉토리에서 실행
proc = await asyncio.create_subprocess_exec(*cmd)  # cwd 미지정 — 금지
```

---

### 2.7 문서 현행화

코드 변경 시 관련 명세 문서를 반드시 업데이트한다.

| 코드 변경 | 업데이트 대상 문서 |
|-----------|---------------------|
| API endpoint 추가/변경 | `docs/SPEC.md` (API 스펙 섹션) |
| 환경변수 추가 | `docs/deployment.md` |
| WebSocket 이벤트 추가 | `docs/websocket-protocol.md` |
| 프리셋 스키마 변경 | `docs/presets-guide.md` |
| 보안 관련 변경 | `docs/security.md` |
| 에러 유형 추가 | `docs/SPEC.md` (에러 체계 섹션) |
| CLI 명령어 추가 | `docs/deployment.md` |

---

### 2.8 느슨한 결합

AgentWorker는 TaskBoard만 의존하며, 다른 워커나 오케스트레이터와 직접 통신하지 않는다.

```python
# Good: Worker → TaskBoard만 의존
class AgentWorker:
    def __init__(self, board: TaskBoard, executor: AgentExecutor) -> None:
        self._board = board
        self._executor = executor

    async def run_loop(self) -> None:
        while True:
            task = await self._board.claim_next(lane=self._lane)
            if task is None:
                await asyncio.sleep(0.5)
                continue
            result = await self._executor.run(task.title)
            await self._board.complete(task.id, result=result.output)

# Bad: Worker가 다른 Worker와 직접 통신
class AgentWorker:
    def __init__(self, other_workers: list[AgentWorker]) -> None:  # 금지
        self._peers = other_workers
```

---

## 3. 개발 방법론

### 3.1 기능 요청 루틴

새로운 기능을 추가할 때 아래 순서를 따른다:

```
1. 연구 (필요 시)
   └── research/ 디렉토리에 관련 연구 추가
   
2. 기획 업데이트
   ├── docs/SPEC.md 업데이트
   └── docs/PLAN.md 업데이트 (있는 경우)
   
3. 명세서 현행화
   ├── docs/conventions.md (컨벤션 변경 시)
   ├── docs/deployment.md (환경변수/CLI 추가 시)
   ├── docs/presets-guide.md (프리셋 변경 시)
   ├── docs/websocket-protocol.md (이벤트 추가 시)
   └── docs/security.md (보안 관련 시)
   
4. 구현
   ├── feature branch 생성
   ├── 테스트 시나리오 정의 (TDD-lite)
   ├── 코드 작성
   ├── 테스트 작성 & 실행
   └── ruff + mypy 통과 확인
   
5. PR & Merge
   ├── feature → mvp PR 생성
   ├── 테스트 통과 확인
   └── merge
```

---

### 3.2 TDD-lite

완전한 TDD는 아니지만, 테스트를 먼저 고려하는 개발 방식을 따른다.

```python
# Step 1: 테스트 시나리오 정의 (구현 전)
def test_submit_task_creates_pipeline():
    """태스크 제출 시 Pipeline이 생성되어야 한다."""

def test_submit_task_with_team_preset():
    """팀 프리셋 지정 시 해당 프리셋의 에이전트를 사용해야 한다."""

def test_submit_task_without_team_auto_composes():
    """팀 미지정 시 오케스트레이터가 자동으로 팀을 구성해야 한다."""

# Step 2: 구현

# Step 3: 테스트 통과 확인
# uv run pytest tests/unit/test_engine.py -x
```

---

### 3.3 PR 규칙

| 항목 | 규칙 |
|------|------|
| 소스 브랜치 | `feat/*`, `fix/*`, `test/*` |
| 대상 브랜치 | `mvp` |
| 테스트 | 모든 테스트 통과 필수 (`pytest -x`) |
| 린트 | `ruff check` 통과 필수 |
| 타입 체크 | `mypy src/` 통과 필수 |
| PR 크기 | 가능한 300줄 이내 (리뷰 용이) |
| PR 제목 | Conventional Commits 형식 |

---

### 3.4 코드 리뷰 체크리스트

PR 리뷰 시 아래 항목을 확인한다:

- [ ] **타입 힌트**: 모든 public 함수에 타입 힌트가 있는가?
- [ ] **에러 핸들링**: 구체적 예외만 catch하는가? `from e` 체이닝이 되어 있는가?
- [ ] **테스트 커버리지**: 새 코드에 대한 테스트가 있는가? 커버리지 기준을 충족하는가?
- [ ] **문서 업데이트**: 관련 명세 문서가 업데이트되었는가?
- [ ] **Docstring**: 새 public 클래스/함수에 Google style docstring이 있는가?
- [ ] **3-Layer 규칙**: 의존 방향이 올바른가? (Core ← API ← Interface)
- [ ] **Async 규칙**: IO-bound 함수가 async인가? subprocess가 `create_subprocess_exec`를 사용하는가?
- [ ] **Logging**: `structlog` 사용, key=value 포맷, 민감 정보 미포함?
- [ ] **Sandbox**: CLI subprocess가 격리된 `cwd`에서 실행되는가?
- [ ] **프리셋 분리**: 도메인 로직이 코어가 아닌 YAML에 있는가?

---

## 4. 전체 pyproject.toml 참조 설정

아래는 위에서 정의한 모든 도구 설정을 통합한 `pyproject.toml` 참조본이다.

```toml
[project]
name = "agent-team-orchestrator"
version = "0.1.0"
description = "Multi-LLM agent team orchestration platform"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "structlog>=24.4.0",
    "typer>=0.12.0",
    "httpx>=0.27.0",
    "langgraph>=0.2.0",
    "litellm>=1.40.0",
    "python-ulid>=2.7.0",
    "pyyaml>=6.0.0",
    "websockets>=13.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.7.0",
    "mypy>=1.11.0",
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "coverage>=7.6.0",
    "httpx",  # TestClient용
]

[project.scripts]
orchestrator = "orchestrator.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/orchestrator"]

# --- ruff ---
[tool.ruff]
target-version = "py312"
line-length = 99
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "N", "UP", "B", "A", "C4",
    "DTZ", "T20", "SIM", "TCH", "RUF", "ASYNC",
    "S", "PT", "RET", "ARG",
]
ignore = ["S101", "S603", "S607", "B008"]

[tool.ruff.lint.isort]
known-first-party = ["orchestrator"]
force-single-line = false
lines-after-imports = 2
section-order = [
    "future", "standard-library", "third-party",
    "first-party", "local-folder",
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "ARG", "S106"]
"src/orchestrator/cli.py" = ["T20"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
docstring-code-format = true

# --- mypy ---
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
disallow_untyped_calls = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_reexport = true
warn_redundant_casts = true
warn_unused_ignores = true
show_error_codes = true
namespace_packages = true
explicit_package_bases = true
mypy_path = "src"

[[tool.mypy.overrides]]
module = ["langgraph.*", "litellm.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_untyped_calls = false

# --- pytest ---
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--strict-markers",
    "--strict-config",
    "-x",
    "--tb=short",
    "--cov=orchestrator",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
]
markers = [
    "unit: 단위 테스트 (mock 사용, 외부 의존 없음)",
    "integration: 통합 테스트 (실제 CLI 호출 포함)",
    "slow: 느린 테스트 (timeout >10s)",
    "e2e: 엔드투엔드 테스트 (API 서버 필요)",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:langgraph.*",
]

# --- coverage ---
[tool.coverage.run]
source = ["orchestrator"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
    "@abstractmethod",
    "raise NotImplementedError",
]
show_missing = true
fail_under = 80
```
