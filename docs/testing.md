# 테스트 명세서

> v1.0 | 2026-04-05
> SPEC.md v2.0 기반

---

## 1. 테스트 전략 개요

### 1.1 테스트 피라미드

```
              /\
             /  \           E2E 테스트 (4개)
            / E2E\          실 CLI 3개 + 전체 파이프라인 흐름
           /------\
          / 통합    \        통합 테스트 (6개)
         / 테스트    \       실 CLI 1개 + mock 나머지, Git worktree 실제 사용
        /------------\
       / API 테스트    \     API 테스트 (8개)
      / (httpx async)  \    httpx AsyncClient + TestClient 기반
     /------------------\
    /    유닛 테스트       \   유닛 테스트 (28개)
   /     (가장 많음)        \  개별 함수/클래스 독립 검증, mock 전용
  /------------------------\
```

### 1.2 카테고리별 실행 환경

| 레벨 | 대상 | API 키 필요 | CI 실행 | 기본 타임아웃 | 마커 |
|------|------|------------|---------|-------------|------|
| **유닛** | 개별 함수/클래스 | 불필요 | 매 PR | 30초 | (마커 없음, 기본) |
| **API** | REST/WebSocket 엔드포인트 | 불필요 | 매 PR | 30초 | (마커 없음, 기본) |
| **통합 (mock)** | 파이프라인 흐름 + mock 어댑터 | 불필요 | 매 PR | 60초 | (마커 없음, 기본) |
| **통합 (실 CLI)** | 실 CLI 서브프로세스 호출 | 필요 | 수동/주간 | 120초 | `@pytest.mark.integration` |
| **E2E** | 전체 파이프라인 (CLI + worktree) | 필요 | 수동 | 300초 | `@pytest.mark.e2e` |

### 1.3 커버리지 목표

| 영역 | 최소 커버리지 | 비고 |
|------|-------------|------|
| `core/` 전체 | 80% | engine, queue, executor, adapters, events |
| `api/` 전체 | 70% | routes, ws, deps |
| `cli.py` | 60% | typer 앱은 통합 테스트로 보완 |
| **전체 (overall)** | **75%** | `pyproject.toml`의 `fail_under = 75` |

---

## 2. 테스트 인프라 설정

### 2.1 pytest 설정 (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "integration: 실 CLI 호출이 필요한 통합 테스트",
    "integration_claude: Claude CLI 통합 테스트",
    "integration_codex: Codex CLI 통합 테스트",
    "integration_gemini: Gemini CLI 통합 테스트",
    "slow: 실행 시간이 긴 테스트",
    "e2e: 전체 파이프라인 E2E 테스트",
]
addopts = "-m 'not integration and not e2e' --timeout=30"
```

### 2.2 테스트 실행 명령

```bash
# 유닛 + API 테스트 (기본, CI용)
uv run pytest

# 커버리지 리포트 포함
uv run pytest --cov --cov-report=html --cov-report=term-missing

# 특정 모듈만
uv run pytest tests/unit/core/test_engine.py -v

# 통합 테스트 (Claude만)
uv run pytest -m "integration_claude" --timeout=120

# 통합 테스트 (전체)
uv run pytest -m "integration" --timeout=120

# E2E 테스트
uv run pytest -m "e2e" --timeout=300

# 전체 (유닛 + 통합 + E2E)
uv run pytest -m "" --timeout=300
```

---

## 3. Fixture 정의

### 3.1 `tests/conftest.py` — 공통 fixture

```python
"""전체 테스트 공통 fixture."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.bus import EventBus
from orchestrator.core.events.types import Event, EventType
from orchestrator.core.executor.base import AgentExecutor, AgentResult
from orchestrator.core.models.pipeline import Pipeline
from orchestrator.core.queue.models import TaskItem, TaskState
from orchestrator.core.queue.board import TaskBoard


# ============================================================
# Configuration Fixtures
# ============================================================

@pytest.fixture
def mock_config() -> OrchestratorConfig:
    """테스트용 OrchestratorConfig (환경변수 불필요)."""
    return OrchestratorConfig(
        anthropic_api_key="test-key-anthropic",
        codex_api_key="test-key-codex",
        gemini_api_key="test-key-gemini",
        default_timeout=10,
        max_retries=2,
        max_iterations=3,
        log_level="DEBUG",
        cli_priority=["claude", "codex", "gemini"],
        worktree_base_dir="/tmp/test-worktrees",
        cleanup_worktrees=True,
        api_host="127.0.0.1",
        api_port=8888,
        preset_dir="tests/mocks/fixtures",
    )


# ============================================================
# Event System Fixtures
# ============================================================

@pytest.fixture
def event_bus() -> EventBus:
    """테스트용 EventBus 인스턴스."""
    return EventBus()


@pytest.fixture
def captured_events(event_bus: EventBus) -> list[Event]:
    """이벤트 버스에서 발행된 이벤트를 캡처하는 리스트.

    Usage:
        def test_something(event_bus, captured_events):
            await event_bus.emit(some_event)
            assert len(captured_events) == 1
    """
    events: list[Event] = []

    async def _capture(event: Event) -> None:
        events.append(event)

    event_bus.subscribe(_capture)
    return events


# ============================================================
# Model Fixtures
# ============================================================

@pytest.fixture
def sample_task_item() -> TaskItem:
    """테스트용 TaskItem 인스턴스."""
    return TaskItem(
        id="task-001",
        title="JWT 미들웨어 구현",
        lane="implementer",
        state=TaskState.TODO,
        depends_on=[],
        assigned_to=None,
        result="",
        retry_count=0,
        max_retries=3,
        pipeline_id="pipe-001",
    )


@pytest.fixture
def sample_task_items() -> list[TaskItem]:
    """3개의 테스트용 TaskItem (의존 관계 포함)."""
    return [
        TaskItem(
            id="task-001",
            title="인증 모듈 설계",
            lane="architect",
            state=TaskState.TODO,
            depends_on=[],
            pipeline_id="pipe-001",
        ),
        TaskItem(
            id="task-002",
            title="JWT 미들웨어 구현",
            lane="implementer",
            state=TaskState.BACKLOG,
            depends_on=["task-001"],
            pipeline_id="pipe-001",
        ),
        TaskItem(
            id="task-003",
            title="코드 리뷰",
            lane="reviewer",
            state=TaskState.BACKLOG,
            depends_on=["task-002"],
            pipeline_id="pipe-001",
        ),
    ]


@pytest.fixture
def sample_agent_result() -> AgentResult:
    """테스트용 AgentResult (성공)."""
    return AgentResult(
        success=True,
        output="JWT 미들웨어가 성공적으로 구현되었습니다.",
        exit_code=0,
        duration_ms=1500.0,
        executor_type="cli",
        agent_name="claude",
        raw_stdout='{"result": "JWT 미들웨어가 성공적으로 구현되었습니다."}',
        raw_stderr="",
    )


@pytest.fixture
def failed_agent_result() -> AgentResult:
    """테스트용 AgentResult (실패)."""
    return AgentResult(
        success=False,
        output="",
        exit_code=1,
        duration_ms=5000.0,
        executor_type="cli",
        agent_name="claude",
        raw_stdout="",
        raw_stderr="Error: API key invalid",
    )


# ============================================================
# TaskBoard Fixtures
# ============================================================

@pytest.fixture
def mock_board(sample_task_items: list[TaskItem]) -> TaskBoard:
    """테스트용 TaskBoard (3개 태스크 투입 상태)."""
    board = TaskBoard(pipeline_id="pipe-001")
    for task in sample_task_items:
        board.add_task(task)
    return board


# ============================================================
# Executor / Adapter Mock Fixtures
# ============================================================

@pytest.fixture
def mock_executor(sample_agent_result: AgentResult) -> AgentExecutor:
    """성공 응답을 반환하는 Mock AgentExecutor."""
    executor = MagicMock(spec=AgentExecutor)
    executor.executor_type = "mock"
    executor.run = AsyncMock(return_value=sample_agent_result)
    executor.health_check = AsyncMock(return_value=True)
    return executor


@pytest.fixture
def failing_executor(failed_agent_result: AgentResult) -> AgentExecutor:
    """실패 응답을 반환하는 Mock AgentExecutor."""
    executor = MagicMock(spec=AgentExecutor)
    executor.executor_type = "mock"
    executor.run = AsyncMock(return_value=failed_agent_result)
    executor.health_check = AsyncMock(return_value=True)
    return executor


@pytest.fixture
def timeout_executor() -> AgentExecutor:
    """타임아웃을 시뮬레이션하는 Mock AgentExecutor."""
    executor = MagicMock(spec=AgentExecutor)
    executor.executor_type = "mock"
    executor.run = AsyncMock(side_effect=asyncio.TimeoutError())
    executor.health_check = AsyncMock(return_value=True)
    return executor


# ============================================================
# Engine Fixtures
# ============================================================

@pytest.fixture
def mock_engine(mock_config: OrchestratorConfig, event_bus: EventBus) -> OrchestratorEngine:
    """테스트용 OrchestratorEngine (mock 의존성 주입).

    모든 내부 의존성이 mock으로 대체된 엔진.
    실제 CLI 호출, 파일 I/O, LLM 호출 없음.
    """
    engine = OrchestratorEngine.__new__(OrchestratorEngine)
    engine._config = mock_config
    engine._event_bus = event_bus
    engine._pipelines = {}
    return engine


# ============================================================
# Temporary Directory Fixtures
# ============================================================

@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """테스트용 임시 Git 리포지토리."""
    import subprocess

    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
    )

    # 초기 커밋 (worktree 생성에 필요)
    readme = repo_dir / "README.md"
    readme.write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        capture_output=True,
    )
    return repo_dir


@pytest.fixture
def tmp_artifact_dir(tmp_path: Path) -> Path:
    """테스트용 아티팩트 저장 디렉토리."""
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    return artifact_dir


@pytest.fixture
def tmp_preset_dir(tmp_path: Path) -> Path:
    """테스트용 프리셋 디렉토리 (YAML 파일 포함)."""
    preset_dir = tmp_path / "presets"
    agents_dir = preset_dir / "agents"
    teams_dir = preset_dir / "teams"
    agents_dir.mkdir(parents=True)
    teams_dir.mkdir(parents=True)

    # 샘플 에이전트 프리셋
    (agents_dir / "test-architect.yaml").write_text(
        "name: test-architect\n"
        "persona:\n"
        "  role: 테스트 아키텍트\n"
        "  goal: 아키텍처 설계\n"
        "execution_mode: cli\n"
        "preferred_cli: claude\n"
    )

    # 샘플 팀 프리셋
    (teams_dir / "test-team.yaml").write_text(
        "name: test-team\n"
        "agents:\n"
        "  architect:\n"
        "    preset: test-architect\n"
        "    count: 1\n"
        "    lane: architect\n"
        "workflow: sequential\n"
        "synthesis_strategy: narrative\n"
    )
    return preset_dir
```

### 3.2 `tests/api/conftest.py` — API 테스트 전용 fixture

```python
"""API 테스트 전용 fixture."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.api.app import create_app
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.bus import EventBus
from orchestrator.core.models.pipeline import Pipeline


@pytest.fixture
def mock_engine_for_api(event_bus: EventBus) -> OrchestratorEngine:
    """API 테스트용 mock 엔진 (모든 메서드 AsyncMock)."""
    engine = MagicMock(spec=OrchestratorEngine)

    # 태스크 관련
    engine.submit_task = AsyncMock(return_value=Pipeline(
        id="pipe-001",
        task="테스트 태스크",
        status="running",
    ))
    engine.get_pipeline = AsyncMock(return_value=Pipeline(
        id="pipe-001",
        task="테스트 태스크",
        status="running",
    ))
    engine.list_pipelines = AsyncMock(return_value=[])
    engine.cancel_task = AsyncMock(return_value=True)
    engine.resume_task = AsyncMock(return_value=Pipeline(
        id="pipe-001",
        task="테스트 태스크",
        status="running",
    ))

    # 보드 관련
    engine.get_board_state = MagicMock(return_value={})
    engine.list_agents = MagicMock(return_value=[])

    # 프리셋 관련
    engine.list_agent_presets = MagicMock(return_value=[])
    engine.list_team_presets = MagicMock(return_value=[])
    engine.save_agent_preset = MagicMock()
    engine.save_team_preset = MagicMock()

    # 이벤트 관련
    engine.get_events = MagicMock(return_value=[])
    engine.subscribe = MagicMock()

    return engine


@pytest.fixture
async def async_client(mock_engine_for_api: OrchestratorEngine) -> AsyncClient:
    """httpx AsyncClient (FastAPI 테스트용).

    Usage:
        async def test_api(async_client):
            response = await async_client.get("/api/health")
            assert response.status_code == 200
    """
    app = create_app(engine=mock_engine_for_api)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

### 3.3 `tests/integration/conftest.py` — 통합 테스트 전용 fixture

```python
"""통합 테스트 전용 fixture."""
import os
import shutil

import pytest


def _cli_available(name: str) -> bool:
    """CLI 도구 설치 여부 확인."""
    return shutil.which(name) is not None


def _has_api_key(env_var: str) -> bool:
    """API 키 환경변수 설정 여부 확인."""
    return bool(os.environ.get(env_var))


# === Skip 조건 ===
skip_no_claude = pytest.mark.skipif(
    not (_cli_available("claude") and _has_api_key("ANTHROPIC_API_KEY")),
    reason="Claude CLI 미설치 또는 ANTHROPIC_API_KEY 미설정",
)

skip_no_codex = pytest.mark.skipif(
    not (_cli_available("codex") and _has_api_key("CODEX_API_KEY")),
    reason="Codex CLI 미설치 또는 CODEX_API_KEY 미설정",
)

skip_no_gemini = pytest.mark.skipif(
    not (_cli_available("gemini") and _has_api_key("GEMINI_API_KEY")),
    reason="Gemini CLI 미설치 또는 GEMINI_API_KEY 미설정",
)
```

### 3.4 `tests/e2e/conftest.py` — E2E 테스트 전용 fixture

```python
"""E2E 테스트 전용 fixture."""
import subprocess
from pathlib import Path

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine


@pytest.fixture
def e2e_repo(tmp_path: Path) -> Path:
    """E2E 테스트용 실제 Git 리포지토리 (소스 코드 포함)."""
    repo_dir = tmp_path / "e2e-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
    )

    # Python 프로젝트 구조 생성
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "__init__.py").write_text("")
    (src_dir / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n"
        "@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n"
    )
    (repo_dir / "requirements.txt").write_text("fastapi\nuvicorn\n")

    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial project setup"],
        cwd=repo_dir,
        capture_output=True,
    )
    return repo_dir


@pytest.fixture
def e2e_engine() -> OrchestratorEngine:
    """E2E 테스트용 실제 OrchestratorEngine (환경변수에서 키 로드)."""
    config = OrchestratorConfig()  # 실제 환경변수 사용
    # 실제 어댑터, 실제 EventBus 등 전체 초기화
    return OrchestratorEngine(config=config)
```

### 3.5 Mock 모듈

#### `tests/mocks/mock_adapter.py`

```python
"""테스트용 MockCLIAdapter.

실제 CLI를 호출하지 않고 미리 정의된 응답을 반환한다.
"""
import asyncio
from pathlib import Path

from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.executor.base import AgentResult


class MockCLIAdapter(CLIAdapter):
    """테스트용 Mock CLI 어댑터."""

    def __init__(
        self,
        name: str = "mock",
        responses: dict[str, str] | None = None,
        should_fail: bool = False,
        latency_ms: float = 10,
        timeout: int = 30,
    ):
        super().__init__(name=name, timeout=timeout)
        self.responses = responses or {"default": "Mock implementation completed."}
        self.should_fail = should_fail
        self.latency_ms = latency_ms
        self.call_history: list[dict] = []

    def _build_command(self, prompt: str, workdir: Path) -> list[str]:
        return ["echo", "mock"]

    def _parse_output(self, stdout: str, stderr: str) -> str:
        return stdout

    async def execute(
        self,
        prompt: str,
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> AgentResult:
        await asyncio.sleep(self.latency_ms / 1000)
        self.call_history.append({"prompt": prompt, "workdir": str(workdir)})

        if self.should_fail:
            return AgentResult(
                success=False,
                output="",
                exit_code=1,
                duration_ms=self.latency_ms,
                executor_type="mock",
                agent_name=self.name,
                raw_stdout="",
                raw_stderr="Mock failure",
            )

        response = self.responses.get(prompt, self.responses.get("default", ""))
        return AgentResult(
            success=True,
            output=response,
            exit_code=0,
            duration_ms=self.latency_ms,
            executor_type="mock",
            agent_name=self.name,
            raw_stdout=response,
            raw_stderr="",
        )
```

#### `tests/mocks/mock_executor.py`

```python
"""테스트용 MockAgentExecutor.

AgentExecutor ABC를 구현하는 mock.
"""
import asyncio

from orchestrator.core.executor.base import AgentExecutor, AgentResult


class MockAgentExecutor(AgentExecutor):
    """테스트용 Mock AgentExecutor."""

    executor_type = "mock"

    def __init__(
        self,
        name: str = "mock-agent",
        response: str = "Mock result",
        should_fail: bool = False,
        latency_ms: float = 10,
    ):
        self.name = name
        self.response = response
        self.should_fail = should_fail
        self.latency_ms = latency_ms
        self.call_count = 0

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,
        context: dict | None = None,
    ) -> AgentResult:
        await asyncio.sleep(self.latency_ms / 1000)
        self.call_count += 1

        return AgentResult(
            success=not self.should_fail,
            output=self.response if not self.should_fail else "",
            exit_code=0 if not self.should_fail else 1,
            duration_ms=self.latency_ms,
            executor_type="mock",
            agent_name=self.name,
            raw_stdout=self.response if not self.should_fail else "",
            raw_stderr="Mock failure" if self.should_fail else "",
        )

    async def health_check(self) -> bool:
        return True
```

---

## 4. 테스트 파일 매핑 — 전체 명세

### 4.1 `tests/unit/core/test_engine.py` — OrchestratorEngine [P1]

```
소스: src/orchestrator/core/engine.py
Fixture: mock_config, event_bus, mock_executor, sample_task_items
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_submit_task_creates_pipeline` | submit_task 호출 시 Pipeline 생성 + ID 반환 |
| `test_submit_task_with_team_preset` | team_preset 지정 시 프리셋 기반 태스크 분해 |
| `test_submit_task_without_preset_uses_auto_planning` | 프리셋 없이 호출 시 자동 팀 구성 |
| `test_get_pipeline_returns_existing` | 존재하는 pipeline_id로 조회 성공 |
| `test_get_pipeline_returns_none_for_unknown` | 존재하지 않는 ID로 조회 시 None 반환 |
| `test_list_pipelines_returns_all` | 여러 파이프라인 제출 후 전체 목록 반환 |
| `test_cancel_task_returns_true` | 실행 중 태스크 취소 성공 |
| `test_cancel_task_returns_false_for_unknown` | 존재하지 않는 태스크 취소 시 False |
| `test_cancel_task_stops_running_agents` | 취소 시 실행 중 에이전트 중단 확인 |
| `test_resume_task_restarts_failed` | 실패 태스크 재개 시 재실행 |
| `test_get_board_state` | 칸반 보드 상태 딕셔너리 반환 |
| `test_list_agents` | 등록된 에이전트 목록 반환 |
| `test_subscribe_receives_events` | 이벤트 구독 후 이벤트 수신 확인 |
| `test_get_events_filters_by_pipeline_id` | 특정 파이프라인 이벤트만 필터링 |

### 4.2 `tests/unit/core/config/test_schema.py` — OrchestratorConfig [P1]

```
소스: src/orchestrator/core/config/schema.py
Fixture: (없음, 직접 생성)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_default_values` | 기본값 설정 확인 (timeout=300, retries=3 등) |
| `test_env_variable_loading` | 환경변수에서 값 로딩 (monkeypatch) |
| `test_env_prefix` | `ORCHESTRATOR_` 접두사 적용 확인 |
| `test_api_key_alias` | `ANTHROPIC_API_KEY` alias 동작 확인 |
| `test_cli_priority_parsing` | 쉼표 구분 리스트 파싱 |
| `test_dotenv_loading` | .env 파일에서 로딩 (tmp_path) |

### 4.3 `tests/unit/core/executor/test_base_executor.py` — AgentExecutor ABC [P1]

```
소스: src/orchestrator/core/executor/base.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_agent_executor_is_abstract` | ABC 직접 인스턴스화 불가 |
| `test_agent_result_model_validation` | AgentResult 필드 타입 검증 |
| `test_agent_result_serialization` | AgentResult JSON 직렬화/역직렬화 |
| `test_agent_result_default_values` | raw_stdout, raw_stderr 기본값 |

### 4.4 `tests/unit/core/executor/test_cli_executor.py` — CLIAgentExecutor [P1]

```
소스: src/orchestrator/core/executor/cli_executor.py
Fixture: mock_adapter (MockCLIAdapter)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_run_delegates_to_adapter` | run() 호출 시 adapter.execute() 위임 확인 |
| `test_run_returns_agent_result` | 반환값이 AgentResult 타입 |
| `test_run_passes_timeout` | timeout 파라미터 전달 확인 |
| `test_health_check_delegates_to_adapter` | health_check()이 adapter.health_check() 호출 |
| `test_executor_type_is_cli` | executor_type == "cli" 확인 |

### 4.5 `tests/unit/core/executor/test_mcp_executor.py` — MCPAgentExecutor [P3]

```
소스: src/orchestrator/core/executor/mcp_executor.py
Fixture: mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_run_calls_litellm` | LiteLLM completion 호출 확인 |
| `test_run_with_mcp_tools` | MCP 서버 도구 전달 확인 |
| `test_run_timeout` | 타임아웃 시 AgentResult(success=False) 반환 |
| `test_health_check_mcp_connection` | MCP 서버 연결 확인 |
| `test_executor_type_is_mcp` | executor_type == "mcp" 확인 |

### 4.6 `tests/unit/core/queue/test_board.py` — TaskBoard [P1]

```
소스: src/orchestrator/core/queue/board.py
Fixture: sample_task_item, sample_task_items, event_bus
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_add_task` | 태스크 추가 후 보드 상태 확인 |
| `test_add_task_emits_event` | 태스크 추가 시 이벤트 발행 |
| `test_claim_task_assigns_agent` | 태스크 소유권 획득 + assigned_to 설정 |
| `test_claim_task_changes_state_to_in_progress` | claim 시 상태가 IN_PROGRESS로 변경 |
| `test_claim_task_returns_none_when_empty` | 가용 태스크 없을 때 None 반환 |
| `test_complete_task` | 태스크 완료 처리 + result 저장 |
| `test_complete_task_emits_event` | 완료 시 TASK_COMPLETED 이벤트 발행 |
| `test_fail_task` | 태스크 실패 처리 + retry_count 증가 |
| `test_fail_task_emits_event` | 실패 시 TASK_FAILED 이벤트 발행 |
| `test_get_ready_tasks_respects_depends_on` | depends_on 충족된 태스크만 반환 |
| `test_get_ready_tasks_excludes_completed` | 완료된 태스크는 제외 |
| `test_get_state_returns_lanes` | 레인별 태스크 상태 딕셔너리 반환 |
| `test_all_done_when_all_completed` | 전체 완료 시 True |
| `test_all_done_returns_false_when_pending` | 미완료 태스크 있으면 False |
| `test_has_failures` | 실패 태스크 존재 여부 |
| `test_get_retryable_filters_by_max_retries` | retry_count < max_retries인 태스크만 |

### 4.7 `tests/unit/core/queue/test_worker.py` — AgentWorker [P1]

```
소스: src/orchestrator/core/queue/worker.py
Fixture: mock_executor, mock_board, event_bus, sample_task_item
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_process_task_calls_executor_run` | executor.run() 호출 확인 |
| `test_process_task_success_completes_board_task` | 성공 시 board.complete_task() 호출 |
| `test_process_task_failure_fails_board_task` | 실패 시 board.fail_task() 호출 |
| `test_process_task_emits_agent_started_event` | 시작 시 AGENT_STARTED 이벤트 |
| `test_process_task_emits_agent_completed_event` | 완료 시 AGENT_COMPLETED 이벤트 |
| `test_process_task_emits_agent_failed_event` | 실패 시 AGENT_FAILED 이벤트 |
| `test_run_loop_processes_all_ready_tasks` | 루프가 모든 ready 태스크 처리 |
| `test_stop_interrupts_run_loop` | stop() 호출 시 루프 중단 |

### 4.8 `tests/unit/core/presets/test_models.py` — 프리셋 모델 [P2]

```
소스: src/orchestrator/core/presets/models.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_persona_def_creation` | PersonaDef 기본 생성 |
| `test_persona_def_with_constraints` | constraints 리스트 설정 |
| `test_agent_preset_defaults` | AgentPreset 기본값 (execution_mode="cli") |
| `test_agent_preset_with_mcp_servers` | MCP 서버 설정 포함 |
| `test_team_preset_creation` | TeamPreset 생성 + agents/tasks 설정 |
| `test_team_preset_workflow_validation` | workflow 유효값 검증 |
| `test_tool_access_model` | ToolAccess allowed/denied 필드 |
| `test_agent_limits_model` | AgentLimits max_tokens, timeout |

### 4.9 `tests/unit/core/presets/test_registry.py` — PresetRegistry [P2]

```
소스: src/orchestrator/core/presets/registry.py
Fixture: tmp_preset_dir
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_load_all_reads_yaml_files` | YAML 파일 일괄 로드 |
| `test_get_agent_preset_by_name` | 이름으로 에이전트 프리셋 조회 |
| `test_get_agent_preset_returns_none_for_unknown` | 존재하지 않는 프리셋 조회 시 None |
| `test_get_team_preset_by_name` | 이름으로 팀 프리셋 조회 |
| `test_list_agent_presets` | 전체 에이전트 프리셋 목록 |
| `test_list_team_presets` | 전체 팀 프리셋 목록 |
| `test_save_agent_preset_creates_yaml` | 에이전트 프리셋 YAML 파일 생성 |
| `test_save_team_preset_creates_yaml` | 팀 프리셋 YAML 파일 생성 |
| `test_load_invalid_yaml_raises_error` | 잘못된 YAML 파싱 에러 |

### 4.10 `tests/unit/core/planner/test_decomposer.py` — TaskDecomposer [P2]

```
소스: src/orchestrator/core/planner/decomposer.py
Fixture: mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_decompose_returns_task_items` | LLM 호출 → TaskItem 리스트 반환 |
| `test_decompose_with_team_preset` | 팀 프리셋 기반 분해 |
| `test_decompose_without_preset` | 프리셋 없이 자동 분해 |
| `test_build_decomposition_prompt` | 분해 프롬프트 내용 검증 |
| `test_parse_decomposition_valid_json` | LLM JSON 출력 파싱 성공 |
| `test_parse_decomposition_invalid_json` | 잘못된 JSON → DecompositionError |
| `test_decompose_llm_failure` | LLM 호출 실패 → DecompositionError |

### 4.11 `tests/unit/core/planner/test_team_planner.py` — TeamPlanner [P3]

```
소스: src/orchestrator/core/planner/team_planner.py
Fixture: mocker, tmp_preset_dir
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_plan_team_returns_team_preset` | LLM 호출 → TeamPreset 반환 |
| `test_plan_team_uses_available_presets` | 기존 프리셋 목록을 LLM에 전달 |
| `test_plan_team_llm_failure` | LLM 호출 실패 시 에러 처리 |
| `test_parse_team_plan_valid` | LLM 출력 파싱 성공 |

### 4.12 `tests/unit/core/adapters/test_base_adapter.py` — CLIAdapter ABC [P1]

```
소스: src/orchestrator/core/adapters/base.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_cli_adapter_is_abstract` | ABC 직접 인스턴스화 불가 |
| `test_execute_calls_subprocess` | asyncio.create_subprocess_exec 호출 확인 (mock) |
| `test_execute_timeout_kills_process` | 타임아웃 시 proc.kill() 호출 |
| `test_execute_timeout_returns_failure` | 타임아웃 시 AgentResult(success=False) |
| `test_execute_returns_success_on_zero_exit` | exit_code=0 → success=True |
| `test_execute_returns_failure_on_nonzero_exit` | exit_code!=0 → success=False |
| `test_health_check_returns_true_on_success` | CLI --version 성공 → True |
| `test_health_check_returns_false_on_not_found` | FileNotFoundError → False |

### 4.13 `tests/unit/core/adapters/test_claude.py` — ClaudeAdapter [P1]

```
소스: src/orchestrator/core/adapters/claude.py
Fixture: mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_build_command_includes_bare_flag` | `--bare` 플래그 포함 |
| `test_build_command_includes_json_output` | `--output-format json` 포함 |
| `test_build_command_includes_bypass_permissions` | `--permission-mode bypassPermissions` 포함 |
| `test_build_command_includes_prompt` | `-p` + 프롬프트 내용 포함 |
| `test_parse_output_valid_json` | `{"result": "done"}` → `"done"` |
| `test_parse_output_nested_json` | 중첩 JSON 구조 파싱 |
| `test_parse_output_invalid_json_fallback` | 잘못된 JSON → raw stdout 반환 |
| `test_parse_output_empty_string` | 빈 stdout 처리 |
| `test_handle_long_prompt_creates_temp_file` | 7,000자 초과 프롬프트 → 임시 파일 생성 |
| `test_name_is_claude` | adapter.name == "claude" |

### 4.14 `tests/unit/core/adapters/test_codex.py` — CodexAdapter [P2]

```
소스: src/orchestrator/core/adapters/codex.py
Fixture: mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_build_command_includes_exec` | `codex exec` 포함 |
| `test_build_command_includes_json_flag` | `--json` 플래그 포함 |
| `test_build_command_includes_full_auto` | `--full-auto` 플래그 포함 |
| `test_build_command_includes_ephemeral` | `--ephemeral` 플래그 포함 |
| `test_parse_output_valid_json` | Codex JSON 출력 파싱 |
| `test_parse_output_invalid_json_fallback` | raw stdout 폴백 |
| `test_name_is_codex` | adapter.name == "codex" |

### 4.15 `tests/unit/core/adapters/test_gemini.py` — GeminiAdapter [P2]

```
소스: src/orchestrator/core/adapters/gemini.py
Fixture: mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_build_command_includes_yolo` | `--yolo` 플래그 포함 (도구 hang 방지) |
| `test_build_command_includes_stream_json` | `--output-format stream-json` 포함 |
| `test_parse_output_filters_result_events` | stream-json에서 `result` 이벤트만 추출 |
| `test_parse_output_ignores_non_result_events` | `progress`, `log` 등 비-result 이벤트 무시 |
| `test_filter_stream_json_handles_pollution` | stdout 오염 (#21433) 필터링 |
| `test_filter_stream_json_empty_input` | 빈 입력 처리 |
| `test_parse_output_multiple_result_events` | 여러 result 이벤트 결합 |
| `test_name_is_gemini` | adapter.name == "gemini" |

### 4.16 `tests/unit/core/adapters/test_adapter_factory.py` — AdapterFactory [P2]

```
소스: src/orchestrator/core/adapters/factory.py
Fixture: mock_config, mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_create_cli_executor_claude` | "claude" → ClaudeAdapter 기반 CLIAgentExecutor 생성 |
| `test_create_cli_executor_codex` | "codex" → CodexAdapter 기반 CLIAgentExecutor 생성 |
| `test_create_cli_executor_gemini` | "gemini" → GeminiAdapter 기반 CLIAgentExecutor 생성 |
| `test_create_from_preset` | AgentPreset → AgentExecutor 생성 |
| `test_inject_api_key` | 환경변수에 API 키 주입 확인 |
| `test_create_unknown_cli_raises_error` | 미등록 CLI 이름 → CLINotFoundError |

### 4.17 `tests/unit/core/worktree/test_manager.py` — WorktreeManager [P2]

```
소스: src/orchestrator/core/worktree/manager.py
Fixture: tmp_repo, mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_create_worktree` | worktree 생성 + 디렉토리 존재 확인 |
| `test_create_worktree_creates_branch` | 새 브랜치 생성 확인 |
| `test_remove_worktree` | worktree 제거 + 디렉토리 삭제 확인 |
| `test_merge_success` | 두 브랜치 병합 성공 |
| `test_merge_conflict_raises_error` | 충돌 시 MergeConflictError 발생 |
| `test_list_worktrees` | 활성 worktree 목록 반환 |
| `test_cleanup_all` | 전체 worktree 정리 |

### 4.18 `tests/unit/core/worktree/test_collector.py` — FileDiffCollector [P2]

```
소스: src/orchestrator/core/worktree/collector.py
Fixture: tmp_repo
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_snapshot_before_captures_state` | 실행 전 파일 상태 스냅샷 |
| `test_collect_changes_detects_new_file` | 새 파일 추가 감지 |
| `test_collect_changes_detects_modified_file` | 파일 수정 감지 |
| `test_collect_changes_detects_deleted_file` | 파일 삭제 감지 |
| `test_get_diff_returns_git_diff` | Git diff 문자열 반환 |

### 4.19 `tests/unit/core/context/test_artifact_store.py` — ArtifactStore [P2]

```
소스: src/orchestrator/core/context/artifact_store.py
Fixture: tmp_artifact_dir
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_save_creates_file` | 아티팩트 파일 생성 확인 |
| `test_save_returns_path` | 저장 경로 반환 |
| `test_load_reads_content` | 저장된 아티팩트 내용 로드 |
| `test_load_missing_file_raises_error` | 존재하지 않는 파일 → FileNotFoundError |
| `test_list_artifacts` | 파이프라인별 아티팩트 목록 |
| `test_cleanup_removes_directory` | 파이프라인 아티팩트 디렉토리 삭제 |

### 4.20 `tests/unit/core/context/test_prompt_builder.py` — PromptBuilder [P3]

```
소스: src/orchestrator/core/context/prompt_builder.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_build_includes_task_description` | 프롬프트에 태스크 설명 포함 |
| `test_inject_persona_adds_role` | 페르소나 역할 주입 |
| `test_inject_context_adds_prev_results` | 이전 결과 주입 |
| `test_apply_constraints_adds_rules` | 제약 조건 추가 |
| `test_build_full_prompt` | 전체 프롬프트 조립 통합 테스트 |

### 4.21 `tests/unit/core/auth/test_provider.py` — AuthProvider [P1]

```
소스: src/orchestrator/core/auth/provider.py
Fixture: mock_config
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_auth_provider_is_abstract` | ABC 직접 인스턴스화 불가 |
| `test_env_auth_provider_get_key_claude` | "claude" → ANTHROPIC_API_KEY 반환 |
| `test_env_auth_provider_get_key_codex` | "codex" → CODEX_API_KEY 반환 |
| `test_env_auth_provider_get_key_gemini` | "gemini" → GEMINI_API_KEY 반환 |
| `test_env_auth_provider_get_key_unknown` | 미등록 프로바이더 → None |
| `test_validate_returns_status_dict` | 각 프로바이더별 키 유효성 딕셔너리 |
| `test_validate_missing_key` | 키 없는 프로바이더 → False |

### 4.22 `tests/unit/core/auth/test_key_pool.py` — KeyPool [P3]

```
소스: src/orchestrator/core/auth/key_pool.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_acquire_round_robin` | 라운드 로빈 키 분배 |
| `test_acquire_after_exhaustion` | 모든 키 소진 시 에러 |
| `test_release_returns_key_to_pool` | 키 반환 후 재사용 가능 |
| `test_mark_exhausted_removes_key` | 소진된 키 비활성화 |

### 4.23 `tests/unit/core/events/test_bus.py` — EventBus [P1]

```
소스: src/orchestrator/core/events/bus.py
Fixture: event_bus, captured_events
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_subscribe_adds_callback` | 콜백 등록 확인 |
| `test_unsubscribe_removes_callback` | 콜백 해제 확인 |
| `test_emit_calls_all_subscribers` | 이벤트 발행 → 모든 구독자 호출 |
| `test_emit_stores_in_history` | 이벤트 히스토리 저장 |
| `test_get_history_all` | 전체 히스토리 반환 |
| `test_get_history_filtered_by_pipeline` | 파이프라인별 히스토리 필터링 |
| `test_emit_with_no_subscribers` | 구독자 없을 때 에러 없이 동작 |

### 4.24 `tests/unit/core/events/test_types.py` — EventType, Event [P1]

```
소스: src/orchestrator/core/events/types.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_event_type_values` | 각 EventType enum 값 확인 |
| `test_event_creation` | Event 모델 생성 |
| `test_event_serialization` | Event JSON 직렬화 |
| `test_event_timestamp_auto_set` | timestamp 자동 설정 |

### 4.25 `tests/unit/core/events/test_tracker.py` — EventTracker [P2]

```
소스: src/orchestrator/core/events/tracker.py
Fixture: event_bus
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_get_progress_returns_percentages` | 완료율, 실패율 계산 |
| `test_get_progress_empty_pipeline` | 빈 파이프라인 → 0% |
| `test_get_timeline_ordered` | 시간순 이벤트 정렬 |

### 4.26 `tests/unit/core/events/test_synthesizer.py` — Synthesizer [P2]

```
소스: src/orchestrator/core/events/synthesizer.py
Fixture: sample_agent_result, mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_synthesize_narrative_strategy` | narrative 전략 → LLM 호출 → 보고서 |
| `test_synthesize_structured_strategy` | structured 전략 → 구조화된 출력 |
| `test_synthesize_checklist_strategy` | checklist 전략 → 체크리스트 형태 |
| `test_synthesize_empty_results` | 빈 결과 → 빈 보고서 |
| `test_build_synthesis_prompt` | 종합 프롬프트 내용 검증 |
| `test_synthesize_llm_failure` | LLM 호출 실패 시 에러 처리 |

### 4.27 `tests/unit/core/errors/test_exceptions.py` — 에러 계층 [P1]

```
소스: src/orchestrator/core/errors/exceptions.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_orchestrator_error_is_base` | OrchestratorError 기본 예외 |
| `test_cli_error_hierarchy` | CLIError → CLIExecutionError 상속 관계 |
| `test_cli_timeout_error` | CLITimeoutError 생성 + 메시지 |
| `test_cli_parse_error` | CLIParseError 생성 |
| `test_cli_not_found_error` | CLINotFoundError 생성 |
| `test_auth_error` | AuthError 생성 |
| `test_worktree_error` | WorktreeError 생성 |
| `test_merge_conflict_error` | MergeConflictError → WorktreeError 상속 |
| `test_decomposition_error` | DecompositionError 생성 |
| `test_all_providers_failed_error` | AllProvidersFailedError 생성 |
| `test_all_errors_inherit_from_base` | 모든 예외가 OrchestratorError 하위 |

### 4.28 `tests/unit/core/errors/test_retry.py` — RetryPolicy [P3]

```
소스: src/orchestrator/core/errors/retry.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_retry_on_retryable_error` | 지정된 에러 발생 시 재시도 |
| `test_no_retry_on_non_retryable_error` | 비대상 에러는 즉시 전파 |
| `test_max_retries_exceeded` | 최대 재시도 초과 시 최종 에러 전파 |
| `test_exponential_backoff_delays` | 지수 백오프 지연 시간 확인 |
| `test_execute_success_on_retry` | 재시도 후 성공 시 결과 반환 |

### 4.29 `tests/unit/core/errors/test_fallback.py` — FallbackChain [P3]

```
소스: src/orchestrator/core/errors/fallback.py
Fixture: mocker, event_bus
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_execute_uses_first_adapter` | 첫 어댑터 성공 시 즉시 반환 |
| `test_execute_falls_back_on_failure` | 첫 어댑터 실패 → 두 번째 시도 |
| `test_execute_all_fail_raises_error` | 모든 어댑터 실패 → AllProvidersFailedError |
| `test_fallback_emits_event` | 폴백 시 이벤트 발행 |
| `test_fallback_chain_order` | 폴백 순서 (claude → codex → gemini) 확인 |

### 4.30 `tests/unit/core/models/test_schemas.py` — 공통 스키마 [P1]

```
소스: src/orchestrator/core/models/schemas.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_agent_result_creation` | AgentResult 기본 생성 |
| `test_agent_result_serialization` | AgentResult JSON 직렬화/역직렬화 |
| `test_agent_result_defaults` | raw_stdout, raw_stderr 기본값 |
| `test_agent_model` | Agent 모델 생성 + 필드 확인 |

### 4.30b `tests/unit/core/models/test_pipeline.py` — Pipeline 모델 [P1]

```
소스: src/orchestrator/core/models/pipeline.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_pipeline_status_enum_values` | PipelineStatus enum 값 |
| `test_pipeline_creation` | Pipeline 기본 생성 |
| `test_pipeline_serialization` | Pipeline JSON 직렬화 |
| `test_pipeline_defaults` | 기본값 (status, created_at 등) |

### 4.30c `tests/unit/core/queue/test_models.py` — 칸반 큐 모델 [P1]

```
소스: src/orchestrator/core/queue/models.py
Fixture: (없음)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_task_state_enum_values` | TaskState enum 값 (backlog, todo, ...) |
| `test_task_item_creation` | TaskItem 기본 생성 |
| `test_task_item_defaults` | 기본값 (retry_count=0, max_retries=3) |
| `test_task_item_validation_error` | 잘못된 타입 → ValidationError |
| `test_lane_model` | Lane 모델 생성 + 필드 확인 |

### 4.31 `tests/unit/api/test_routes.py` — REST 엔드포인트 유닛 테스트 [P1]

```
소스: src/orchestrator/api/routes.py
Fixture: mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_router_prefix` | 라우터 prefix == "/api" |
| `test_submit_task_handler_calls_engine` | submit_task → engine.submit_task() 호출 |
| `test_get_task_handler_calls_engine` | get_task → engine.get_pipeline() 호출 |

### 4.32 `tests/unit/api/test_ws.py` — WebSocket 유닛 테스트 [P1]

```
소스: src/orchestrator/api/ws.py
Fixture: mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_ws_router_exists` | WebSocket 라우터 존재 확인 |

### 4.33 `tests/unit/api/test_deps.py` — 의존성 주입 유닛 테스트 [P1]

```
소스: src/orchestrator/api/deps.py
Fixture: mock_config
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_get_config_returns_config` | OrchestratorConfig 인스턴스 반환 |
| `test_get_engine_returns_singleton` | 동일 인스턴스 반환 (싱글톤) |

### 4.34 `tests/unit/test_cli.py` — typer CLI 유닛 테스트 [P1]

```
소스: src/orchestrator/cli.py
Fixture: mocker
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_app_exists` | typer app 인스턴스 존재 |
| `test_run_command_exists` | "run" 명령 등록 확인 |
| `test_status_command_exists` | "status" 명령 등록 확인 |
| `test_cancel_command_exists` | "cancel" 명령 등록 확인 |
| `test_serve_command_exists` | "serve" 명령 등록 확인 |

---

## 5. API 테스트 (httpx AsyncClient)

### 5.1 `tests/api/test_task_endpoints.py` [P1]

```
소스: src/orchestrator/api/routes.py (task 관련)
Fixture: async_client, mock_engine_for_api
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_post_tasks_201` | POST /api/tasks → 201 + Pipeline 반환 |
| `test_post_tasks_with_team_preset` | team_preset 파라미터 전달 확인 |
| `test_post_tasks_with_target_repo` | target_repo 파라미터 전달 확인 |
| `test_post_tasks_empty_body_422` | 빈 body → 422 Validation Error |
| `test_get_tasks_200` | GET /api/tasks → 200 + 목록 |
| `test_get_task_200` | GET /api/tasks/{id} → 200 + Pipeline |
| `test_get_task_404` | 존재하지 않는 ID → 404 |
| `test_post_task_resume_200` | POST /api/tasks/{id}/resume → 200 |
| `test_delete_task_200` | DELETE /api/tasks/{id} → 200 |
| `test_delete_task_404` | 존재하지 않는 ID → 404 |

### 5.2 `tests/api/test_health_endpoint.py` [P1]

```
소스: src/orchestrator/api/routes.py (health)
Fixture: async_client
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_health_check_200` | GET /api/health → 200 |
| `test_health_check_response_body` | 응답 body에 status 필드 포함 |

### 5.3 `tests/api/test_board_endpoints.py` [P2]

```
소스: src/orchestrator/api/routes.py (board 관련)
Fixture: async_client, mock_engine_for_api
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_get_board_200` | GET /api/board → 200 |
| `test_get_board_lanes_200` | GET /api/board/lanes → 200 + 레인 목록 |
| `test_get_board_task_200` | GET /api/board/tasks/{id} → 200 |
| `test_get_board_task_404` | 존재하지 않는 ID → 404 |

### 5.4 `tests/api/test_preset_endpoints.py` [P2]

```
소스: src/orchestrator/api/routes.py (preset 관련)
Fixture: async_client, mock_engine_for_api
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_get_agent_presets_200` | GET /api/presets/agents → 200 |
| `test_get_team_presets_200` | GET /api/presets/teams → 200 |
| `test_post_agent_preset_201` | POST /api/presets/agents → 201 |
| `test_post_team_preset_201` | POST /api/presets/teams → 201 |
| `test_post_agent_preset_invalid_422` | 잘못된 body → 422 |

### 5.5 `tests/api/test_agent_endpoints.py` [P2]

```
소스: src/orchestrator/api/routes.py (agent 관련)
Fixture: async_client, mock_engine_for_api
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_get_agents_200` | GET /api/agents → 200 + 에이전트 목록 |
| `test_get_agents_response_format` | 응답 형식 (id, name, status 필드) |

### 5.6 `tests/api/test_event_endpoints.py` [P2]

```
소스: src/orchestrator/api/routes.py (event 관련)
Fixture: async_client, mock_engine_for_api
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_get_events_200` | GET /api/events → 200 |
| `test_get_events_with_pipeline_filter` | query param으로 파이프라인 필터링 |
| `test_get_artifacts_200` | GET /api/artifacts/{task_id} → 200 |

---

## 6. 통합 테스트

### 6.1 `tests/integration/test_claude_adapter.py` [P2]

```
소스: src/orchestrator/core/adapters/claude.py
Fixture: tmp_repo
마커: @pytest.mark.integration, @pytest.mark.integration_claude
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_claude_execute_simple_prompt` | 간단한 프롬프트 실행 → 결과 반환 |
| `test_claude_execute_returns_json` | JSON 출력 파싱 성공 |
| `test_claude_execute_file_creation` | 파일 생성 명령 실행 → 파일 존재 확인 |
| `test_claude_health_check` | health_check → True |
| `test_claude_timeout_handling` | 긴 작업 → 타임아웃 처리 |

### 6.2 `tests/integration/test_codex_adapter.py` [P2]

```
소스: src/orchestrator/core/adapters/codex.py
Fixture: tmp_repo
마커: @pytest.mark.integration, @pytest.mark.integration_codex
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_codex_execute_simple_prompt` | 간단한 프롬프트 실행 → 결과 반환 |
| `test_codex_execute_returns_json` | JSON 출력 파싱 성공 |
| `test_codex_health_check` | health_check → True |

### 6.3 `tests/integration/test_gemini_adapter.py` [P2]

```
소스: src/orchestrator/core/adapters/gemini.py
Fixture: tmp_repo
마커: @pytest.mark.integration, @pytest.mark.integration_gemini
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_gemini_execute_simple_prompt` | 간단한 프롬프트 실행 → 결과 반환 |
| `test_gemini_stream_json_filtering` | stream-json result 이벤트 필터링 |
| `test_gemini_stdout_pollution_handling` | #21433 버그 대응 필터링 |
| `test_gemini_health_check` | health_check → True |

### 6.4 `tests/integration/test_worktree_ops.py` [P2]

```
소스: src/orchestrator/core/worktree/manager.py
Fixture: tmp_repo
마커: (마커 없음, git만 필요)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_create_and_remove_worktree` | worktree 생성 → 작업 → 제거 |
| `test_parallel_worktrees` | 3개 worktree 동시 생성 |
| `test_merge_worktree_to_main` | worktree 변경사항 → main 병합 |
| `test_merge_conflict_detection` | 충돌 감지 및 MergeConflictError |
| `test_cleanup_all_worktrees` | 전체 worktree 정리 |

### 6.5 `tests/integration/test_pipeline_mock.py` [P2]

```
소스: 전체 파이프라인 통합
Fixture: mock_config, event_bus, MockCLIAdapter, MockAgentExecutor
마커: (마커 없음, mock 전용)
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_full_pipeline_with_mock_adapters` | mock 3개 어댑터 → 태스크 분해 → 병렬 실행 → 결과 수집 |
| `test_pipeline_partial_failure` | 1개 어댑터 실패 → 나머지 성공 → 부분 결과 |
| `test_pipeline_retry_on_failure` | 실패 → 재시도 → 성공 |
| `test_pipeline_events_emitted` | 파이프라인 전체 이벤트 발행 순서 확인 |
| `test_pipeline_board_state_transitions` | 보드 상태 전이 (BACKLOG→TODO→IN_PROGRESS→DONE) |

---

## 7. E2E 테스트

### 7.1 `tests/e2e/test_coding_scenario.py` — 코딩 팀 시나리오 [P3]

```
마커: @pytest.mark.e2e
Fixture: e2e_repo, e2e_engine
타임아웃: 300초
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_coding_team_jwt_middleware` | "JWT 인증 미들웨어 구현" → 3개 에이전트 → 설계/구현/리뷰 → merge → 코드 생성 확인 |

**시나리오 상세:**
1. 사용자 입력: `"JWT 인증 미들웨어를 구현해줘"`
2. team_preset: `feature-team` (architect → implementer → reviewer)
3. target_repo: `e2e_repo`
4. 기대 결과:
   - 오케스트레이터가 3개 서브태스크 생성 (설계, 구현, 리뷰)
   - 각 에이전트가 독립 worktree에서 실행
   - 결과가 main 브랜치에 병합
   - Synthesizer가 종합 보고서 생성
5. 검증 항목:
   - `pipeline.status == "completed"`
   - 결과 보고서 내용 존재
   - worktree 정리 완료

### 7.2 `tests/e2e/test_incident_scenario.py` — 장애 분석 시나리오 [P3]

```
마커: @pytest.mark.e2e
Fixture: e2e_engine
타임아웃: 300초
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_incident_analysis_parallel` | "프로덕션 API 500 에러 분석" → 3개 MCP 에이전트 병렬 → 종합 보고서 |

**시나리오 상세:**
1. 사용자 입력: `"프로덕션 API 500 에러 원인 분석"`
2. team_preset: `incident-analysis` (ELK + Grafana + K8s 병렬)
3. 기대 결과:
   - 3개 MCP 에이전트가 병렬 실행
   - 각자 도구 기반 분석 수행
   - Synthesizer가 "narrative" 전략으로 종합 보고서 생성
4. 검증 항목:
   - `pipeline.status == "completed"`
   - 종합 보고서에 3개 에이전트 결과 반영

### 7.3 `tests/e2e/test_failure_scenario.py` — 실패 시나리오 [P3]

```
마커: @pytest.mark.e2e
Fixture: e2e_engine
타임아웃: 300초
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_timeout_retry_fallback` | 첫 에이전트 타임아웃 → retry 3회 → 폴백 → 부분 완료 |

**시나리오 상세:**
1. Claude 어댑터에 의도적 타임아웃 설정 (timeout=5초, 복잡한 태스크)
2. 기대 동작:
   - 1차 실행 → 타임아웃
   - retry 1~3차 → 타임아웃 반복
   - 폴백 → Codex 어댑터로 재시도
   - Codex 성공 시 부분 완료
   - 전체 실패 시 `AllProvidersFailedError` + `PIPELINE_FAILED` 이벤트
3. 검증 항목:
   - retry_count == max_retries (3)
   - 폴백 이벤트 발행 확인
   - 최종 상태: `"completed"` (폴백 성공) 또는 `"failed"` (전체 실패)

### 7.4 `tests/e2e/test_resume_scenario.py` — 중단 + 재개 시나리오 [P3]

```
마커: @pytest.mark.e2e
Fixture: e2e_engine, e2e_repo
타임아웃: 300초
```

| 테스트 함수 | 검증 내용 |
|------------|----------|
| `test_checkpoint_and_resume` | 파이프라인 중단 → 체크포인트 저장 → resume → 이전 상태에서 재개 → 완료 |

**시나리오 상세:**
1. 3개 서브태스크 중 1개 완료 후 cancel_task() 호출
2. 기대 동작:
   - 체크포인트에 현재 상태 저장 (1개 완료, 2개 미완)
   - resume_task() 호출
   - 이미 완료된 태스크 건너뛰기
   - 나머지 2개 태스크만 재실행
   - 전체 완료
3. 검증 항목:
   - resume 후 완료된 태스크 재실행 안 함
   - 전체 3개 태스크 결과 존재
   - `pipeline.status == "completed"`

---

## 8. JSON Fixture 파일

### 8.1 `tests/mocks/fixtures/claude_response.json`

```json
{
  "result": "JWT 인증 미들웨어가 성공적으로 구현되었습니다.\n\n구현된 파일:\n- src/middleware/auth.py\n- tests/test_auth.py",
  "duration_ms": 12500,
  "model": "claude-sonnet-4-20250514",
  "stop_reason": "end_turn"
}
```

### 8.2 `tests/mocks/fixtures/claude_error.json`

```json
{
  "error": {
    "type": "authentication_error",
    "message": "Invalid API key"
  }
}
```

### 8.3 `tests/mocks/fixtures/codex_response.json`

```json
{
  "output": "미들웨어 구현이 완료되었습니다.",
  "files_changed": ["src/middleware/auth.py"],
  "exit_code": 0
}
```

### 8.4 `tests/mocks/fixtures/gemini_response.json`

```json
[
  {"type": "progress", "data": "분석 시작..."},
  {"type": "progress", "data": "코드 생성 중..."},
  {"type": "result", "data": "인증 미들웨어 구현 완료. src/middleware/auth.py 생성."},
  {"type": "done", "data": null}
]
```

### 8.5 `tests/mocks/fixtures/gemini_polluted.json`

```json
[
  {"type": "progress", "data": "분석 시작..."},
  "WARNING: some debug output",
  {"type": "result", "data": "구현 완료."},
  "Another random line",
  {"type": "done", "data": null}
]
```

### 8.6 `tests/mocks/fixtures/decomposition_result.json`

```json
{
  "subtasks": [
    {
      "id": "task-001",
      "title": "인증 모듈 아키텍처 설계",
      "assigned_cli": "claude",
      "lane": "architect",
      "depends_on": []
    },
    {
      "id": "task-002",
      "title": "JWT 미들웨어 구현",
      "assigned_cli": "codex",
      "lane": "implementer",
      "depends_on": ["task-001"]
    },
    {
      "id": "task-003",
      "title": "코드 리뷰 및 테스트 작성",
      "assigned_cli": "gemini",
      "lane": "reviewer",
      "depends_on": ["task-002"]
    }
  ]
}
```

---

## 9. CI 통합

### 9.1 GitHub Actions — 유닛 테스트 (`ci.yml`)

```yaml
name: CI

on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --group dev

      - name: Ruff lint
        run: uv run ruff check .

      - name: Ruff format check
        run: uv run ruff format --check .

      - name: MyPy type check
        run: uv run mypy src/

  test:
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --group dev

      - name: Run unit + API tests
        run: |
          uv run pytest tests/unit/ tests/api/ \
            --cov=src/orchestrator \
            --cov-report=xml \
            --cov-report=term-missing \
            --junitxml=test-results.xml \
            --timeout=30

      - name: Check coverage threshold
        run: |
          uv run coverage report --fail-under=75

      - name: Upload coverage
        if: matrix.python-version == '3.12'
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-${{ matrix.python-version }}
          path: test-results.xml
```

### 9.2 GitHub Actions — 통합 테스트 (`integration.yml`)

```yaml
name: Integration Tests

on:
  workflow_dispatch:
    inputs:
      adapters:
        description: "테스트할 어댑터 (claude,codex,gemini)"
        required: false
        default: "claude"
  schedule:
    - cron: "0 9 * * 1"    # 매주 월요일 09:00 UTC

permissions:
  contents: read

jobs:
  integration:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --group dev

      - name: Install CLI tools
        run: |
          npm install -g @anthropic-ai/claude-code || true
          npm install -g @openai/codex || true

      - name: Run integration tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          CODEX_API_KEY: ${{ secrets.CODEX_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          ADAPTERS="${{ github.event.inputs.adapters || 'claude' }}"
          MARKERS=""
          for adapter in $(echo $ADAPTERS | tr ',' ' '); do
            if [ -n "$MARKERS" ]; then
              MARKERS="$MARKERS or integration_${adapter}"
            else
              MARKERS="integration_${adapter}"
            fi
          done
          uv run pytest tests/integration/ \
            -m "$MARKERS" \
            --timeout=120 \
            -v \
            --junitxml=integration-results.xml

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: integration-results
          path: integration-results.xml
```

---

## 10. 테스트 수 요약

### Phase별 테스트 함수 수

| 카테고리 | Phase 1 | Phase 2 | Phase 3 | 합계 |
|---------|---------|---------|---------|------|
| 유닛 테스트 | 95 | 57 | 28 | **180** |
| API 테스트 | 14 | 14 | 0 | **28** |
| 통합 테스트 | 0 | 25 | 0 | **25** |
| E2E 테스트 | 0 | 0 | 4 | **4** |
| **합계** | **109** | **96** | **32** | **237** |

### 모듈별 테스트 함수 수

| 소스 모듈 | 테스트 파일 | 테스트 함수 수 |
|----------|-----------|-------------|
| `core/engine.py` | `test_engine.py` | 14 |
| `core/config/schema.py` | `test_schema.py` | 6 |
| `core/executor/base.py` | `test_base_executor.py` | 4 |
| `core/executor/cli_executor.py` | `test_cli_executor.py` | 5 |
| `core/executor/mcp_executor.py` | `test_mcp_executor.py` | 5 |
| `core/queue/board.py` | `test_board.py` | 16 |
| `core/queue/worker.py` | `test_worker.py` | 8 |
| `core/presets/models.py` | `test_models.py` | 8 |
| `core/presets/registry.py` | `test_registry.py` | 9 |
| `core/planner/decomposer.py` | `test_decomposer.py` | 7 |
| `core/planner/team_planner.py` | `test_team_planner.py` | 4 |
| `core/adapters/base.py` | `test_base_adapter.py` | 8 |
| `core/adapters/claude.py` | `test_claude.py` | 10 |
| `core/adapters/codex.py` | `test_codex.py` | 7 |
| `core/adapters/gemini.py` | `test_gemini.py` | 8 |
| `core/adapters/factory.py` | `test_adapter_factory.py` | 6 |
| `core/worktree/manager.py` | `test_manager.py` | 7 |
| `core/worktree/collector.py` | `test_collector.py` | 5 |
| `core/context/artifact_store.py` | `test_artifact_store.py` | 6 |
| `core/context/prompt_builder.py` | `test_prompt_builder.py` | 5 |
| `core/auth/provider.py` | `test_provider.py` | 7 |
| `core/auth/key_pool.py` | `test_key_pool.py` | 4 |
| `core/events/bus.py` | `test_bus.py` | 7 |
| `core/events/types.py` | `test_types.py` | 4 |
| `core/events/tracker.py` | `test_tracker.py` | 3 |
| `core/events/synthesizer.py` | `test_synthesizer.py` | 6 |
| `core/errors/exceptions.py` | `test_exceptions.py` | 11 |
| `core/errors/retry.py` | `test_retry.py` | 5 |
| `core/errors/fallback.py` | `test_fallback.py` | 5 |
| `core/models/schemas.py` | `test_schemas.py` | 4 |
| `core/models/pipeline.py` | `test_pipeline.py` | 4 |
| `core/queue/models.py` | `test_models.py` (queue) | 5 |
| `api/routes.py` | `test_routes.py` + API tests | 3 + 25 |
| `api/ws.py` | `test_ws.py` | 1 |
| `api/deps.py` | `test_deps.py` | 2 |
| `cli.py` | `test_cli.py` | 5 |
| (통합) | integration tests | 22 |
| (E2E) | e2e tests | 4 |
| **합계** | | **~237** |
