# 함수 명세서

> v1.0 | 2026-04-05
> 기반: `docs/SPEC.md` v2.0, `docs/data-models.md` v1.0

---

## 목차

1. [OrchestratorEngine](#1-orchestratorengine)
2. [TaskBoard](#2-taskboard)
3. [AgentWorker](#3-agentworker)
4. [PresetRegistry](#4-presetregistry)
5. [TeamPlanner](#5-teamplanner)
6. [Synthesizer](#6-synthesizer)
7. [WorktreeManager](#7-worktreemanager)
8. [FileDiffCollector](#8-filediffcollector)
9. [AdapterFactory](#9-adapterfactory)
10. [CLIAdapter 서브클래스](#10-cliadapter-서브클래스)

---

## 1. OrchestratorEngine

> 모듈: `core/engine.py`

Core 계층의 단일 진입점. API 계층은 이 클래스만 의존한다.
모든 하위 컴포넌트(TaskBoard, PresetRegistry, EventBus 등)를 조합하고, 태스크 생명주기를 관리한다.

### 1.1 `__init__`

```python
def __init__(
    self,
    config: OrchestratorConfig | None = None,
) -> None:
```

**목적:** OrchestratorEngine 인스턴스를 초기화한다. 설정이 없으면 환경 변수에서 자동 로딩한다.

**Args:**
- `config` (`OrchestratorConfig | None`): 시스템 설정. `None`이면 `OrchestratorConfig()`로 자동 생성 (환경 변수/.env에서 로딩).

**Side effects:**
- `PresetRegistry` 생성 및 프리셋 디렉토리 스캔
- `TaskBoard` 생성
- `EventBus` 생성
- `AuthProvider` (`EnvAuthProvider`) 생성
- `AdapterFactory` 생성
- `WorktreeManager` 생성
- `TeamPlanner` 생성
- `Synthesizer` 생성
- 내부 상태: `_pipelines: dict[str, Pipeline]` 초기화
- 내부 상태: `_workers: dict[str, AgentWorker]` 초기화

**Async/Sync:** Sync

---

### 1.2 `submit_task`

```python
async def submit_task(
    self,
    task: str,
    *,
    team_preset: str | None = None,
    target_repo: str | None = None,
) -> Pipeline:
```

**목적:** 사용자 태스크를 제출하고 파이프라인을 생성하여 실행을 시작한다.

**Args:**
- `task` (`str`): 사용자가 입력한 태스크 설명. 예: `"JWT 인증 미들웨어 구현"`.
- `team_preset` (`str | None`): 사용할 TeamPreset 이름. `None`이면 TeamPlanner가 자동 구성.
- `target_repo` (`str | None`): 대상 리포지토리 경로. 코딩 태스크에서 worktree 생성에 사용.

**Returns:**
- `Pipeline`: 생성된 파이프라인 (초기 상태: `PENDING`).

**Raises:**
- `ValueError`: `task`가 빈 문자열인 경우.
- `KeyError`: `team_preset`이 지정되었지만 존재하지 않는 경우.
- `DecompositionError`: TeamPlanner의 태스크 분해 실패.

**Pre-conditions:**
- `task`는 비어있지 않은 문자열이어야 한다.
- `team_preset`이 지정된 경우, `PresetRegistry`에 존재해야 한다.
- `target_repo`가 지정된 경우, 유효한 디렉토리 경로여야 한다.

**Post-conditions:**
- `Pipeline`이 `_pipelines`에 저장된다.
- `PIPELINE_CREATED` 이벤트가 발행된다.
- 백그라운드에서 `_execute_pipeline()` 코루틴이 시작된다.

**Side effects:**
- `EventBus.emit()` 호출 (PIPELINE_CREATED)
- 백그라운드 태스크 생성 (`asyncio.create_task`)
- `_pipelines` dict 변경

**실행 흐름:**
1. UUID4로 `task_id` 생성
2. `Pipeline` 인스턴스 생성 (status=PENDING)
3. `PIPELINE_CREATED` 이벤트 발행
4. `asyncio.create_task(self._execute_pipeline(pipeline))` 시작
5. 즉시 `Pipeline` 반환 (비동기 실행)

**Async/Sync:** Async

**사용 예시:**

```python
engine = OrchestratorEngine()
pipeline = await engine.submit_task(
    "JWT 인증 미들웨어 구현",
    team_preset="feature-team",
    target_repo="./my-project",
)
print(pipeline.task_id)  # "pipeline-550e8400"
print(pipeline.status)   # PipelineStatus.PENDING
```

---

### 1.3 `get_pipeline`

```python
async def get_pipeline(
    self,
    task_id: str,
) -> Pipeline | None:
```

**목적:** 파이프라인 ID로 파이프라인을 조회한다.

**Args:**
- `task_id` (`str`): 파이프라인 ID.

**Returns:**
- `Pipeline | None`: 파이프라인 인스턴스. 존재하지 않으면 `None`.

**Pre-conditions:** 없음.

**Post-conditions:** 상태 변경 없음 (읽기 전용).

**Side effects:** 없음.

**Async/Sync:** Async

**사용 예시:**

```python
pipeline = await engine.get_pipeline("pipeline-550e8400")
if pipeline:
    print(pipeline.status)  # PipelineStatus.RUNNING
```

---

### 1.4 `list_pipelines`

```python
async def list_pipelines(self) -> list[Pipeline]:
```

**목적:** 모든 파이프라인 목록을 반환한다.

**Args:** 없음.

**Returns:**
- `list[Pipeline]`: 파이프라인 목록 (생성 시간 역순).

**Pre-conditions:** 없음.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Async

---

### 1.5 `cancel_task`

```python
async def cancel_task(
    self,
    task_id: str,
) -> bool:
```

**목적:** 실행 중인 파이프라인을 취소한다.

**Args:**
- `task_id` (`str`): 취소할 파이프라인 ID.

**Returns:**
- `bool`: 취소 성공 시 `True`. 파이프라인이 없거나 이미 완료된 경우 `False`.

**Raises:** 없음 (실패 시 `False` 반환).

**Pre-conditions:**
- 파이프라인이 `PENDING`, `PLANNING`, `RUNNING` 상태여야 취소 가능.

**Post-conditions:**
- 파이프라인 status가 `CANCELLED`로 변경된다.
- 진행 중인 서브태스크가 중단된다.
- `PIPELINE_CANCELLED` 이벤트가 발행된다.

**Side effects:**
- 진행 중인 CLI subprocess kill
- worktree cleanup (해당되는 경우)
- `EventBus.emit()` 호출

**Async/Sync:** Async

---

### 1.6 `resume_task`

```python
async def resume_task(
    self,
    task_id: str,
) -> Pipeline:
```

**목적:** 중단된 파이프라인을 재개한다 (체크포인트 기반).

**Args:**
- `task_id` (`str`): 재개할 파이프라인 ID.

**Returns:**
- `Pipeline`: 재개된 파이프라인.

**Raises:**
- `KeyError`: 파이프라인이 존재하지 않는 경우.
- `ValueError`: 재개할 수 없는 상태인 경우 (이미 COMPLETED 등).

**Pre-conditions:**
- 파이프라인이 `FAILED` 또는 `PARTIAL_FAILURE` 상태여야 한다.
- 체크포인트가 존재해야 한다 (checkpoint_enabled=True).

**Post-conditions:**
- 실패한 서브태스크만 재실행된다.
- 파이프라인 status가 `RUNNING`으로 변경된다.

**Side effects:**
- LangGraph 체크포인트에서 상태 복원
- 백그라운드 태스크 재생성

**Async/Sync:** Async

---

### 1.7 `list_agent_presets`

```python
def list_agent_presets(self) -> list[AgentPreset]:
```

**목적:** 등록된 모든 에이전트 프리셋을 반환한다.

**Args:** 없음.

**Returns:**
- `list[AgentPreset]`: 에이전트 프리셋 목록 (이름 순).

**Pre-conditions:** 없음.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Sync

---

### 1.8 `list_team_presets`

```python
def list_team_presets(self) -> list[TeamPreset]:
```

**목적:** 등록된 모든 팀 프리셋을 반환한다.

**Args:** 없음.

**Returns:**
- `list[TeamPreset]`: 팀 프리셋 목록 (이름 순).

**Pre-conditions:** 없음.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Sync

---

### 1.9 `save_agent_preset`

```python
def save_agent_preset(
    self,
    preset: AgentPreset,
) -> None:
```

**목적:** 에이전트 프리셋을 저장한다.

**Args:**
- `preset` (`AgentPreset`): 저장할 에이전트 프리셋.

**Raises:**
- `ValueError`: 프리셋 유효성 검증 실패.

**Pre-conditions:**
- `preset.name`이 유효한 kebab-case 문자열이어야 한다.

**Post-conditions:**
- 프리셋이 `PresetRegistry`에 등록된다.
- YAML 파일로 디스크에 저장된다 (`preset_dirs[0]/agents/{name}.yaml`).

**Side effects:**
- 파일 I/O (YAML 쓰기)

**Async/Sync:** Sync

---

### 1.10 `save_team_preset`

```python
def save_team_preset(
    self,
    preset: TeamPreset,
) -> None:
```

**목적:** 팀 프리셋을 저장한다.

**Args:**
- `preset` (`TeamPreset`): 저장할 팀 프리셋.

**Raises:**
- `ValueError`: 프리셋 유효성 검증 실패 (에이전트 참조 불일치 등).

**Pre-conditions:**
- `preset`의 모든 `TeamAgentDef.preset`이 `PresetRegistry`에 존재해야 한다.

**Post-conditions:**
- 프리셋이 `PresetRegistry`에 등록된다.
- YAML 파일로 디스크에 저장된다 (`preset_dirs[0]/teams/{name}.yaml`).

**Side effects:**
- 파일 I/O (YAML 쓰기)

**Async/Sync:** Sync

---

### 1.11 `get_board_state`

```python
def get_board_state(self) -> dict[str, Any]:
```

**목적:** 칸반 보드의 현재 상태를 반환한다.

**Args:** 없음.

**Returns:**
- `dict[str, Any]`: 칸반 보드 상태. 구조:
  ```python
  {
      "lanes": {
          "implementer": {
              "backlog": [TaskItem, ...],
              "todo": [TaskItem, ...],
              "in_progress": [TaskItem, ...],
              "done": [TaskItem, ...],
              "failed": [TaskItem, ...],
          },
          ...
      },
      "summary": {
          "total": int,
          "by_state": {"backlog": int, "todo": int, ...},
      },
  }
  ```

**Pre-conditions:** 없음.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Sync

---

### 1.12 `list_agents`

```python
def list_agents(self) -> list[dict[str, Any]]:
```

**목적:** 현재 활성화된 에이전트 워커 상태를 반환한다.

**Args:** 없음.

**Returns:**
- `list[dict[str, Any]]`: 에이전트 워커 상태 목록. 각 항목 구조:
  ```python
  {
      "worker_id": str,
      "lane": str,
      "status": str,          # "idle" | "busy" | "stopped"
      "current_task": str | None,
      "tasks_completed": int,
  }
  ```

**Pre-conditions:** 없음.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Sync

---

### 1.13 `subscribe`

```python
def subscribe(
    self,
    callback: Callable[[OrchestratorEvent], Awaitable[None] | None],
) -> None:
```

**목적:** 이벤트 구독자를 등록한다.

**Args:**
- `callback` (`Callable[[OrchestratorEvent], Awaitable[None] | None]`): 이벤트 수신 콜백. sync 또는 async 함수 모두 가능.

**Pre-conditions:** 없음.

**Post-conditions:**
- 콜백이 `EventBus`의 구독자 목록에 추가된다.
- 이후 모든 이벤트가 콜백에 전달된다.

**Side effects:**
- `EventBus` 내부 구독자 리스트 변경

**Async/Sync:** Sync

**사용 예시:**

```python
async def on_event(event: OrchestratorEvent):
    print(f"[{event.type}] {event.data}")

engine.subscribe(on_event)
```

---

### 1.14 `get_events`

```python
def get_events(
    self,
    task_id: str | None = None,
) -> list[OrchestratorEvent]:
```

**목적:** 이벤트 히스토리를 조회한다.

**Args:**
- `task_id` (`str | None`): 특정 파이프라인의 이벤트만 필터링. `None`이면 전체.

**Returns:**
- `list[OrchestratorEvent]`: 이벤트 목록 (시간순).

**Pre-conditions:** 없음.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Sync

---

### 1.15 `_execute_pipeline` (private)

```python
async def _execute_pipeline(
    self,
    pipeline: Pipeline,
) -> None:
```

**목적:** 파이프라인의 전체 생명주기를 실행하는 내부 코루틴.

**실행 흐름:**

```
1. PENDING → PLANNING
   - TeamPlanner.plan_team()으로 태스크 분해
   - team_preset이 있으면 프리셋 기반, 없으면 LLM 자동 구성
   - SubTask[] 생성

2. PLANNING → RUNNING
   - SubTask[] → TaskItem[]로 변환
   - TaskBoard.submit()으로 칸반 보드에 투입
   - target_repo가 있으면 WorktreeManager.create()
   - 필요한 AgentWorker 시작

3. RUNNING (대기)
   - AgentWorker가 TaskItem을 소비
   - 완료/실패 이벤트 감시
   - 부분 실패 처리

4. RUNNING → SYNTHESIZING
   - 모든 서브태스크 완료 (또는 부분 실패 허용)
   - WorkerResult[] 수집

5. SYNTHESIZING → COMPLETED
   - Synthesizer.synthesize()로 종합 보고서 생성
   - auto_merge=True면 WorktreeManager.merge_to_target()
   - worktree cleanup
```

**Side effects:**
- `EventBus.emit()` 다수 호출
- Pipeline 상태 변경
- 파일 I/O (worktree)
- 네트워크 I/O (LLM API)
- CLI subprocess 실행

**Async/Sync:** Async

---

## 2. TaskBoard

> 모듈: `core/queue/board.py`

칸반 보드 방식의 태스크 큐. 레인별로 태스크를 관리하고, 의존성 기반 상태 전이를 처리한다.

### 2.1 `__init__`

```python
def __init__(
    self,
    max_retries: int = 3,
) -> None:
```

**목적:** TaskBoard 인스턴스를 초기화한다.

**Args:**
- `max_retries` (`int`): 기본 최대 재시도 횟수. 기본값 `3`.

**Side effects:**
- `_tasks: dict[str, TaskItem]` 초기화
- `_lanes: dict[str, list[str]]` 초기화 (레인 이름 → task ID 목록)
- `_lock: asyncio.Lock` 생성 (동시성 제어)

**Async/Sync:** Sync

---

### 2.2 `submit`

```python
async def submit(
    self,
    task: TaskItem,
) -> str:
```

**목적:** 새 태스크를 보드에 추가한다.

**Args:**
- `task` (`TaskItem`): 추가할 태스크. `state`는 무시되고 `BACKLOG`로 설정됨.

**Returns:**
- `str`: 태스크 ID.

**Raises:**
- `ValueError`: 동일한 ID의 태스크가 이미 존재하는 경우.

**Pre-conditions:**
- `task.id`가 유니크해야 한다.
- `task.lane`이 비어있지 않아야 한다.

**Post-conditions:**
- 태스크가 `BACKLOG` 상태로 보드에 추가된다.
- 레인이 없으면 자동 생성된다.
- 의존성이 없으면 즉시 `TODO`로 전이된다.

**Side effects:**
- `_tasks`, `_lanes` 변경
- `asyncio.Lock` 획득/해제

**Async/Sync:** Async

**사용 예시:**

```python
board = TaskBoard()
task = TaskItem(
    id="task-001",
    title="JWT 구현",
    description="JWT 미들웨어를 구현하라",
    lane="implementer",
    depends_on=[],
)
task_id = await board.submit(task)
# task.state == TaskState.TODO (의존성 없으므로 즉시 전이)
```

---

### 2.3 `claim`

```python
async def claim(
    self,
    lane: str,
    worker_id: str,
) -> TaskItem | None:
```

**목적:** 지정 레인에서 우선순위가 가장 높은 `TODO` 태스크를 가져와 `IN_PROGRESS`로 전이한다.

**Args:**
- `lane` (`str`): 태스크를 가져올 레인 이름.
- `worker_id` (`str`): 요청하는 워커 ID.

**Returns:**
- `TaskItem | None`: 할당된 태스크. 가용 태스크가 없으면 `None`.

**Pre-conditions:**
- 레인에 `TODO` 상태의 태스크가 있어야 한다.

**Post-conditions:**
- 태스크 state가 `IN_PROGRESS`로 변경된다.
- `assigned_to`가 `worker_id`로 설정된다.
- `started_at`이 현재 시각으로 설정된다.

**Side effects:**
- `_tasks` 변경
- `asyncio.Lock` 획득/해제

**Async/Sync:** Async

**사용 예시:**

```python
task = await board.claim("implementer", "worker-1")
if task:
    print(f"태스크 획득: {task.title}")
```

---

### 2.4 `complete`

```python
async def complete(
    self,
    task_id: str,
    result: str,
) -> None:
```

**목적:** 태스크를 성공 완료 처리한다.

**Args:**
- `task_id` (`str`): 완료할 태스크 ID.
- `result` (`str`): 실행 결과 텍스트.

**Raises:**
- `KeyError`: 태스크 ID가 존재하지 않는 경우.
- `ValueError`: 태스크가 `IN_PROGRESS` 상태가 아닌 경우.

**Pre-conditions:**
- 태스크가 `IN_PROGRESS` 상태여야 한다.

**Post-conditions:**
- 태스크 state가 `DONE`으로 변경된다.
- `result`에 결과 텍스트가 저장된다.
- `completed_at`이 현재 시각으로 설정된다.
- 이 태스크에 의존하는 다른 태스크들의 의존성이 재평가된다.
  - 모든 의존성이 `DONE`이면 → `BACKLOG` → `TODO`로 전이.

**Side effects:**
- `_tasks` 변경
- 의존 태스크 상태 전이 트리거

**Async/Sync:** Async

---

### 2.5 `fail`

```python
async def fail(
    self,
    task_id: str,
    error: str,
) -> None:
```

**목적:** 태스크를 실패 처리한다. 재시도 가능하면 `TODO`로 되돌린다.

**Args:**
- `task_id` (`str`): 실패할 태스크 ID.
- `error` (`str`): 에러 메시지.

**Raises:**
- `KeyError`: 태스크 ID가 존재하지 않는 경우.
- `ValueError`: 태스크가 `IN_PROGRESS` 상태가 아닌 경우.

**Pre-conditions:**
- 태스크가 `IN_PROGRESS` 상태여야 한다.

**Post-conditions:**
- `retry_count < max_retries`인 경우:
  - `retry_count` 증가
  - state가 `TODO`로 변경 (재시도)
  - `assigned_to`가 `None`으로 리셋
- `retry_count >= max_retries`인 경우:
  - state가 `FAILED`로 변경
  - `error`에 에러 메시지 저장
  - `completed_at`이 현재 시각으로 설정

**Side effects:**
- `_tasks` 변경

**Async/Sync:** Async

---

### 2.6 `get_board_state`

```python
def get_board_state(self) -> dict[str, Any]:
```

**목적:** 칸반 보드의 전체 상태를 반환한다.

**Args:** 없음.

**Returns:**
- `dict[str, Any]`: 레인별 태스크 상태. 구조는 `OrchestratorEngine.get_board_state()`와 동일.

**Pre-conditions:** 없음.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Sync

---

### 2.7 `add_lane`

```python
def add_lane(
    self,
    lane: str,
) -> None:
```

**목적:** 새 레인을 추가한다.

**Args:**
- `lane` (`str`): 레인 이름.

**Raises:**
- `ValueError`: 이미 존재하는 레인 이름인 경우.

**Pre-conditions:**
- 레인 이름이 유니크해야 한다.

**Post-conditions:**
- 빈 레인이 보드에 추가된다.

**Side effects:**
- `_lanes` 변경

**Async/Sync:** Sync

---

### 2.8 `get_task`

```python
def get_task(
    self,
    task_id: str,
) -> TaskItem | None:
```

**목적:** ID로 태스크를 조회한다.

**Args:**
- `task_id` (`str`): 태스크 ID.

**Returns:**
- `TaskItem | None`: 태스크 인스턴스. 없으면 `None`.

**Async/Sync:** Sync

---

### 2.9 `get_lane_tasks`

```python
def get_lane_tasks(
    self,
    lane: str,
    state: TaskState | None = None,
) -> list[TaskItem]:
```

**목적:** 특정 레인의 태스크 목록을 반환한다.

**Args:**
- `lane` (`str`): 레인 이름.
- `state` (`TaskState | None`): 상태 필터. `None`이면 전체.

**Returns:**
- `list[TaskItem]`: 태스크 목록 (우선순위 내림차순).

**Async/Sync:** Sync

---

### 2.10 `is_all_done`

```python
def is_all_done(
    self,
    pipeline_id: str,
) -> bool:
```

**목적:** 특정 파이프라인의 모든 태스크가 완료(DONE 또는 FAILED)되었는지 확인한다.

**Args:**
- `pipeline_id` (`str`): 파이프라인 ID.

**Returns:**
- `bool`: 모든 태스크가 터미널 상태(DONE/FAILED)이면 `True`.

**Async/Sync:** Sync

---

### 2.11 `get_results`

```python
def get_results(
    self,
    pipeline_id: str,
) -> list[TaskItem]:
```

**목적:** 특정 파이프라인의 완료된 태스크(DONE)를 반환한다.

**Args:**
- `pipeline_id` (`str`): 파이프라인 ID.

**Returns:**
- `list[TaskItem]`: DONE 상태의 태스크 목록.

**Async/Sync:** Sync

---

## 3. AgentWorker

> 모듈: `core/queue/worker.py`

특정 레인을 담당하는 워커. 폴링 루프로 TaskBoard에서 태스크를 소비하고 에이전트를 실행한다.

### 3.1 `__init__`

```python
def __init__(
    self,
    worker_id: str,
    lane: str,
    board: TaskBoard,
    executor: AgentExecutor,
    event_bus: EventBus,
    *,
    poll_interval: float = 1.0,
    diff_collector: FileDiffCollector | None = None,
) -> None:
```

**목적:** AgentWorker 인스턴스를 초기화한다.

**Args:**
- `worker_id` (`str`): 워커 고유 ID.
- `lane` (`str`): 담당 레인 이름.
- `board` (`TaskBoard`): 태스크 보드 참조.
- `executor` (`CLIAgentExecutor`): CLI 기반 에이전트 실행기. 모든 에이전트는 CLI를 통해 실행된다.
- `event_bus` (`EventBus`): 이벤트 발행기.
- `poll_interval` (`float`): 태스크 폴링 간격 (초). 기본값 `1.0`.
- `diff_collector` (`FileDiffCollector | None`): 파일 변경 수집기. CLI executor에서 사용.

**Side effects:**
- `_running: bool = False` 초기화
- `_task: asyncio.Task | None = None` 초기화
- `_tasks_completed: int = 0` 초기화

**Async/Sync:** Sync

---

### 3.2 `start`

```python
async def start(self) -> None:
```

**목적:** 워커를 시작한다. 백그라운드 폴링 루프를 생성한다.

**Args:** 없음.

**Returns:** 없음.

**Raises:**
- `RuntimeError`: 이미 실행 중인 경우.

**Pre-conditions:**
- 워커가 정지 상태여야 한다 (`_running == False`).

**Post-conditions:**
- `_running`이 `True`로 설정된다.
- 백그라운드 `_run_loop()` 코루틴이 시작된다.
- `WORKER_STARTED` 이벤트가 발행된다.

**Side effects:**
- `asyncio.create_task()` 호출
- `EventBus.emit()` 호출

**Async/Sync:** Async

---

### 3.3 `stop`

```python
async def stop(self) -> None:
```

**목적:** 워커를 정지한다. 현재 실행 중인 태스크가 있으면 완료를 기다린다.

**Args:** 없음.

**Returns:** 없음.

**Pre-conditions:**
- 워커가 실행 중이어야 한다 (`_running == True`).

**Post-conditions:**
- `_running`이 `False`로 설정된다.
- 현재 실행 중인 태스크가 완료된 후 루프가 종료된다.
- `WORKER_STOPPED` 이벤트가 발행된다.

**Side effects:**
- `EventBus.emit()` 호출
- 백그라운드 태스크 취소/대기

**Async/Sync:** Async

---

### 3.4 `_run_loop` (private)

```python
async def _run_loop(self) -> None:
```

**목적:** 워커의 메인 폴링 루프. 태스크를 claim하고 실행한다.

**실행 흐름:**

```
while _running:
    1. board.claim(lane, worker_id)로 태스크 획득
    2. 태스크가 없으면 poll_interval만큼 대기 후 재시도
    3. 태스크 획득 시:
       a. AGENT_EXECUTING 이벤트 발행
       b. logger.info("task_executing", worker_id=..., task_id=..., lane=..., title=...)
       c. diff_collector.snapshot() (있으면)
       d. executor.run()과 heartbeat를 동시 실행:
          - asyncio.create_task(executor.run(...)) → 실행 태스크
          - 10초 간격 heartbeat 루프 시작:
            while 실행 태스크 미완료:
              WORKER_HEARTBEAT 이벤트 발행 {
                worker_id, lane, task_id, state="executing",
                elapsed_ms=(현재-시작)*1000,
                timeout_ms=preset.limits.timeout*1000
              }
              await asyncio.sleep(10)
          - 실행 태스크 완료 대기 (await)
       e. diff_collector.collect_changes() (있으면)
       f. 성공 시: board.complete(task_id, result)
          - TASK_COMPLETED 이벤트 발행
       g. 실패 시: board.fail(task_id, error)
          - TASK_FAILED / TASK_RETRYING 이벤트 발행
       h. _tasks_completed 증가
```

**Side effects:**
- `board.claim()`, `board.complete()`, `board.fail()` 호출
- `executor.run()` 호출 (CLI subprocess / LLM API)
- `EventBus.emit()` 다수 호출
- 파일 I/O (diff_collector)

**Async/Sync:** Async

---

## 4. PresetRegistry

> 모듈: `core/presets/registry.py`

에이전트/팀 프리셋의 로딩, 검색, 저장을 담당한다. YAML 파일 기반.

### 4.1 `__init__`

```python
def __init__(
    self,
    preset_dirs: list[str] | None = None,
) -> None:
```

**목적:** PresetRegistry를 초기화하고 프리셋 디렉토리를 스캔한다.

**Args:**
- `preset_dirs` (`list[str] | None`): 프리셋 YAML 검색 디렉토리 목록. `None`이면 `["./presets"]`.

**Side effects:**
- `_agent_presets: dict[str, AgentPreset]` 초기화
- `_team_presets: dict[str, TeamPreset]` 초기화
- 디렉토리 스캔 및 YAML 파싱 (파일 I/O)

**Async/Sync:** Sync

---

### 4.2 `load_agent_preset`

```python
def load_agent_preset(
    self,
    name: str,
) -> AgentPreset:
```

**목적:** 이름으로 에이전트 프리셋을 조회한다.

**Args:**
- `name` (`str`): 프리셋 이름.

**Returns:**
- `AgentPreset`: 프리셋 인스턴스.

**Raises:**
- `KeyError`: 프리셋이 존재하지 않는 경우.

**Pre-conditions:**
- 프리셋이 `_agent_presets`에 등록되어 있어야 한다.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Sync

**사용 예시:**

```python
registry = PresetRegistry(["./presets"])
preset = registry.load_agent_preset("implementer")
print(preset.persona.role)  # "시니어 백엔드 개발자"
```

---

### 4.3 `load_team_preset`

```python
def load_team_preset(
    self,
    name: str,
) -> TeamPreset:
```

**목적:** 이름으로 팀 프리셋을 조회한다.

**Args:**
- `name` (`str`): 팀 프리셋 이름.

**Returns:**
- `TeamPreset`: 팀 프리셋 인스턴스.

**Raises:**
- `KeyError`: 프리셋이 존재하지 않는 경우.

**Pre-conditions:**
- 프리셋이 `_team_presets`에 등록되어 있어야 한다.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Sync

---

### 4.4 `list_agent_presets`

```python
def list_agent_presets(self) -> list[AgentPreset]:
```

**목적:** 등록된 모든 에이전트 프리셋을 반환한다.

**Args:** 없음.

**Returns:**
- `list[AgentPreset]`: 에이전트 프리셋 목록 (이름 순).

**Async/Sync:** Sync

---

### 4.5 `list_team_presets`

```python
def list_team_presets(self) -> list[TeamPreset]:
```

**목적:** 등록된 모든 팀 프리셋을 반환한다.

**Args:** 없음.

**Returns:**
- `list[TeamPreset]`: 팀 프리셋 목록 (이름 순).

**Async/Sync:** Sync

---

### 4.6 `save_agent_preset`

```python
def save_agent_preset(
    self,
    preset: AgentPreset,
    *,
    overwrite: bool = True,
) -> None:
```

**목적:** 에이전트 프리셋을 레지스트리에 등록하고 YAML 파일로 저장한다.

**Args:**
- `preset` (`AgentPreset`): 저장할 프리셋.
- `overwrite` (`bool`): 기존 프리셋 덮어쓰기 여부. 기본값 `True`.

**Raises:**
- `ValueError`: `overwrite=False`이고 이미 존재하는 경우.

**Post-conditions:**
- `_agent_presets`에 등록된다.
- `{preset_dirs[0]}/agents/{name}.yaml` 파일이 생성/갱신된다.

**Side effects:**
- 파일 I/O (YAML 쓰기)

**Async/Sync:** Sync

---

### 4.7 `save_team_preset`

```python
def save_team_preset(
    self,
    preset: TeamPreset,
    *,
    overwrite: bool = True,
) -> None:
```

**목적:** 팀 프리셋을 레지스트리에 등록하고 YAML 파일로 저장한다.

**Args:**
- `preset` (`TeamPreset`): 저장할 프리셋.
- `overwrite` (`bool`): 기존 프리셋 덮어쓰기 여부. 기본값 `True`.

**Raises:**
- `ValueError`: `overwrite=False`이고 이미 존재하는 경우.

**Post-conditions:**
- `_team_presets`에 등록된다.
- `{preset_dirs[0]}/teams/{name}.yaml` 파일이 생성/갱신된다.

**Side effects:**
- 파일 I/O (YAML 쓰기)

**Async/Sync:** Sync

---

### 4.8 `merge_preset_with_overrides`

```python
def merge_preset_with_overrides(
    self,
    preset_name: str,
    overrides: dict[str, Any],
) -> AgentPreset:
```

**목적:** 기존 AgentPreset에 오버라이드를 deep merge하여 새 인스턴스를 반환한다.

**Args:**
- `preset_name` (`str`): 기반 AgentPreset 이름.
- `overrides` (`dict[str, Any]`): 오버라이드할 필드. 중첩 딕셔너리는 deep merge.

**Returns:**
- `AgentPreset`: 오버라이드가 적용된 새 인스턴스 (원본 불변).

**Raises:**
- `KeyError`: `preset_name`이 존재하지 않는 경우.
- `ValidationError`: 오버라이드 후 유효성 검증 실패.

**Pre-conditions:**
- `preset_name`이 `_agent_presets`에 존재해야 한다.

**Post-conditions:**
- 원본 프리셋은 변경되지 않는다.
- 반환된 인스턴스는 별도의 객체이다.

**Side effects:** 없음.

**Async/Sync:** Sync

**사용 예시:**

```python
# TeamAgentDef의 overrides 적용
merged = registry.merge_preset_with_overrides(
    "implementer",
    {"model": "o3-mini", "limits": {"timeout": 600}},
)
print(merged.model)          # "o3-mini"
print(merged.limits.timeout)  # 600
print(merged.persona.role)    # "시니어 백엔드 개발자" (원본 유지)
```

**Deep merge 규칙:**
- 스칼라 값: 오버라이드가 원본을 대체
- dict: 재귀적으로 merge (원본 키 유지, 오버라이드 키 추가/대체)
- list: 오버라이드가 원본을 대체 (merge 안 함)

---

## 5. TeamPlanner

> 모듈: `core/planner/planner.py`

LLM 기반 태스크 분해기. 사용자 태스크를 서브태스크 + 팀 구성으로 분해한다.

### 5.1 `__init__`

```python
def __init__(
    self,
    model: str = "claude-sonnet-4-20250514",
    preset_registry: PresetRegistry | None = None,
) -> None:
```

**목적:** TeamPlanner를 초기화한다.

**Args:**
- `model` (`str`): 분해에 사용할 LLM 모델. 기본값 `"claude-sonnet-4-20250514"`.
- `preset_registry` (`PresetRegistry | None`): 프리셋 레지스트리. 자동 팀 구성 시 사용 가능한 프리셋을 참조.

**Side effects:**
- LiteLLM 클라이언트 초기화

**Async/Sync:** Sync

---

### 5.2 `plan_team`

```python
async def plan_team(
    self,
    task: str,
    *,
    team_preset: TeamPreset | None = None,
    target_repo: str | None = None,
) -> tuple[list[SubTask], TeamPreset]:
```

**목적:** 사용자 태스크를 서브태스크로 분해하고, 팀을 구성한다.

**Args:**
- `task` (`str`): 사용자 태스크 설명.
- `team_preset` (`TeamPreset | None`): 사전 정의된 팀 프리셋. `None`이면 LLM이 자동 구성.
- `target_repo` (`str | None`): 대상 리포지토리 경로. 코드 분석 컨텍스트 제공.

**Returns:**
- `tuple[list[SubTask], TeamPreset]`: (서브태스크 목록, 사용된/생성된 팀 프리셋).

**Raises:**
- `DecompositionError`: LLM 응답 파싱 실패 또는 유효하지 않은 분해 결과.

**실행 흐름:**

```
team_preset이 있는 경우:
    1. TeamPreset.tasks를 순회
    2. 각 TeamTaskDef → SubTask로 변환
    3. depends_on 매핑 (태스크 이름 → SubTask ID)
    4. assigned_preset = TeamTaskDef.agent (키 이름)
    5. assigned_cli = AgentPreset.preferred_cli

team_preset이 없는 경우 (자동 구성):
    1. 사용 가능한 AgentPreset 목록을 컨텍스트로 제공
    2. LLM에 태스크 분해 요청 (structured output)
    3. 응답에서 서브태스크 + 에이전트 할당 추출
    4. 동적 TeamPreset 생성
    5. SubTask[] 생성
```

**Pre-conditions:**
- `task`가 비어있지 않아야 한다.
- `team_preset`이 `None`인 경우, `preset_registry`가 설정되어 있어야 한다.

**Post-conditions:**
- 반환된 `SubTask[]`의 `depends_on`이 유효한 DAG을 형성한다.
- 각 `SubTask.assigned_preset`이 유효한 AgentPreset 이름이다.

**Side effects:**
- 네트워크 I/O (LLM API 호출, 자동 구성 시에만)
- 파일 I/O (target_repo 코드 분석, 있는 경우)

**Async/Sync:** Async

**사용 예시:**

```python
planner = TeamPlanner(model="claude-sonnet-4-20250514", preset_registry=registry)

# 프리셋 기반
subtasks, preset = await planner.plan_team(
    "JWT 인증 미들웨어 구현",
    team_preset=registry.load_team_preset("feature-team"),
)

# 자동 구성
subtasks, preset = await planner.plan_team(
    "사용자 인증 시스템 보안 감사",
)
```

---

## 6. Synthesizer

> 모듈: `core/events/synthesizer.py`

복수 에이전트의 실행 결과를 종합하여 보고서를 생성한다.

### 6.1 `__init__`

```python
def __init__(
    self,
    model: str = "claude-sonnet-4-20250514",
    strategy: str = "narrative",
) -> None:
```

**목적:** Synthesizer를 초기화한다.

**Args:**
- `model` (`str`): 종합에 사용할 LLM 모델. 기본값 `"claude-sonnet-4-20250514"`.
- `strategy` (`str`): 종합 전략. `"narrative"` | `"structured"` | `"checklist"`. 기본값 `"narrative"`.

**Side effects:**
- LiteLLM 클라이언트 초기화

**Async/Sync:** Sync

---

### 6.2 `synthesize`

```python
async def synthesize(
    self,
    results: list[WorkerResult],
    task: str,
    *,
    strategy: str | None = None,
) -> str:
```

**목적:** 복수 에이전트의 실행 결과를 종합하여 보고서를 생성한다.

**Args:**
- `results` (`list[WorkerResult]`): 서브태스크 실행 결과 목록.
- `task` (`str`): 원본 사용자 태스크 설명.
- `strategy` (`str | None`): 종합 전략 오버라이드. `None`이면 초기화 시 설정된 값 사용.

**Returns:**
- `str`: 종합 보고서 텍스트 (마크다운 형식).

**Raises:**
- `ValueError`: `results`가 비어있는 경우.

**Pre-conditions:**
- `results`에 최소 하나 이상의 결과가 있어야 한다.

**Post-conditions:**
- 반환된 문자열은 마크다운 형식이다.

**Side effects:**
- 네트워크 I/O (LLM API 호출)

**전략별 프롬프트:**

| 전략 | 출력 형태 |
|------|-----------|
| `narrative` | 자연어 종합 보고서. 배경→분석→결론 구조 |
| `structured` | 구조화된 보고서. 섹션별 정리 + 요약 표 |
| `checklist` | 체크리스트 형태. 각 항목의 완료/실패 상태 |

**Async/Sync:** Async

**사용 예시:**

```python
synthesizer = Synthesizer(strategy="narrative")
report = await synthesizer.synthesize(
    results=worker_results,
    task="프로덕션 API 500 에러 원인 분석",
)
print(report)
# # 프로덕션 API 500 에러 원인 분석 보고서
# ## 요약
# ...
```

---

## 7. WorktreeManager

> 모듈: `core/worktree/manager.py`

Git worktree를 사용하여 에이전트별 격리된 작업 환경을 제공한다.

### 7.1 `__init__`

```python
def __init__(
    self,
    base_dir: str = "/tmp/orchestrator-worktrees",
) -> None:
```

**목적:** WorktreeManager를 초기화한다.

**Args:**
- `base_dir` (`str`): worktree 생성 기본 디렉토리. 기본값 `"/tmp/orchestrator-worktrees"`.

**Side effects:**
- `base_dir` 디렉토리 존재 확인 (없으면 생성)
- `_worktrees: dict[str, dict]` 초기화 (branch → worktree 정보)

**Async/Sync:** Sync

---

### 7.2 `create`

```python
async def create(
    self,
    repo_path: str,
    branch_name: str,
    *,
    base_branch: str = "main",
) -> str:
```

**목적:** 새 Git worktree를 생성한다.

**Args:**
- `repo_path` (`str`): 원본 리포지토리 경로.
- `branch_name` (`str`): worktree 브랜치 이름.
- `base_branch` (`str`): 기반 브랜치. 기본값 `"main"`.

**Returns:**
- `str`: 생성된 worktree 디렉토리 경로.

**Raises:**
- `WorktreeError`: Git 명령 실패.
- `FileNotFoundError`: `repo_path`가 존재하지 않는 경우.

**Pre-conditions:**
- `repo_path`가 유효한 Git 리포지토리여야 한다.
- `branch_name`이 기존 브랜치와 충돌하지 않아야 한다.

**Post-conditions:**
- `{base_dir}/{branch_name}` 디렉토리에 worktree가 생성된다.
- `base_branch`에서 새 브랜치가 생성된다.
- `_worktrees`에 등록된다.

**Side effects:**
- 파일 I/O (디렉토리 생성)
- Git subprocess 실행 (`git worktree add -b {branch} {path} {base_branch}`)

**Async/Sync:** Async

**사용 예시:**

```python
manager = WorktreeManager("/tmp/worktrees")
worktree_path = await manager.create(
    "/home/user/my-project",
    "agent-implementer-task001",
    base_branch="main",
)
# worktree_path == "/tmp/worktrees/agent-implementer-task001"
```

---

### 7.3 `cleanup`

```python
async def cleanup(
    self,
    branch_name: str,
) -> None:
```

**목적:** worktree를 정리한다 (제거).

**Args:**
- `branch_name` (`str`): 정리할 worktree 브랜치 이름.

**Raises:**
- `KeyError`: 등록되지 않은 브랜치 이름.
- `WorktreeError`: Git 명령 실패.

**Pre-conditions:**
- 브랜치가 `_worktrees`에 등록되어 있어야 한다.

**Post-conditions:**
- worktree 디렉토리가 삭제된다.
- Git worktree가 제거된다 (`git worktree remove`).
- 브랜치가 삭제된다 (`git branch -D`).
- `_worktrees`에서 제거된다.

**Side effects:**
- 파일 I/O (디렉토리 삭제)
- Git subprocess 실행

**Async/Sync:** Async

---

### 7.4 `merge_to_target`

```python
async def merge_to_target(
    self,
    branch_name: str,
    target_branch: str = "main",
) -> bool:
```

**목적:** worktree 브랜치의 변경사항을 대상 브랜치에 merge한다.

**Args:**
- `branch_name` (`str`): merge할 worktree 브랜치 이름.
- `target_branch` (`str`): merge 대상 브랜치. 기본값 `"main"`.

**Returns:**
- `bool`: merge 성공 시 `True`.

**Raises:**
- `MergeConflictError`: merge conflict 발생 시. `conflicting_files` 속성에 충돌 파일 목록 포함.
- `WorktreeError`: Git 명령 실패.

**Pre-conditions:**
- 브랜치가 `_worktrees`에 등록되어 있어야 한다.
- worktree에 commit된 변경사항이 있어야 한다.

**Post-conditions:**
- `target_branch`에 변경사항이 merge된다.
- merge commit이 생성된다.

**Side effects:**
- Git subprocess 실행 (`git checkout {target}`, `git merge {branch}`)
- 파일 I/O (merge 결과 반영)

**Async/Sync:** Async

---

### 7.5 `list_worktrees`

```python
def list_worktrees(self) -> list[dict[str, str]]:
```

**목적:** 현재 관리 중인 worktree 목록을 반환한다.

**Args:** 없음.

**Returns:**
- `list[dict[str, str]]`: worktree 정보 목록. 각 항목 구조:
  ```python
  {
      "branch": str,
      "path": str,
      "repo": str,
      "base_branch": str,
  }
  ```

**Pre-conditions:** 없음.

**Post-conditions:** 상태 변경 없음.

**Side effects:** 없음.

**Async/Sync:** Sync

---

## 8. FileDiffCollector

> 모듈: `core/worktree/diff.py`

에이전트 실행 전후의 파일 변경사항을 수집한다. worktree 기반.

### 8.1 `__init__`

```python
def __init__(
    self,
    worktree_path: str,
) -> None:
```

**목적:** FileDiffCollector를 초기화한다.

**Args:**
- `worktree_path` (`str`): 감시할 worktree 디렉토리 경로.

**Side effects:**
- `_worktree_path` 저장
- `_snapshot: dict[str, str] | None = None` 초기화

**Async/Sync:** Sync

---

### 8.2 `snapshot`

```python
async def snapshot(self) -> None:
```

**목적:** 현재 worktree의 파일 상태를 스냅샷으로 저장한다. 에이전트 실행 직전에 호출한다.

**Args:** 없음.

**Returns:** 없음.

**Pre-conditions:**
- `_worktree_path`가 유효한 디렉토리여야 한다.

**Post-conditions:**
- `_snapshot`에 현재 파일 상태가 저장된다.
  - 키: 파일 상대 경로
  - 값: 파일 해시(SHA-256) 또는 내용

**Side effects:**
- 파일 I/O (디렉토리 스캔, 파일 읽기)

**Async/Sync:** Async

---

### 8.3 `diff`

```python
async def diff(self) -> list[FileChange]:
```

**목적:** 마지막 snapshot 이후 변경된 파일 목록을 반환한다.

**Args:** 없음.

**Returns:**
- `list[FileChange]`: 변경된 파일 목록.

**Raises:**
- `RuntimeError`: `snapshot()`이 호출되지 않은 경우.

**Pre-conditions:**
- `snapshot()`이 먼저 호출되어야 한다 (`_snapshot is not None`).

**Post-conditions:**
- `_snapshot`은 변경되지 않는다.

**Side effects:**
- 파일 I/O (디렉토리 스캔, 파일 읽기)
- Git subprocess 실행 (`git diff --name-status`) 가능

**Async/Sync:** Async

---

### 8.4 `collect_changes`

```python
async def collect_changes(self) -> list[FileChange]:
```

**목적:** `snapshot()` + `diff()`의 편의 메서드. 현재 변경사항을 수집하고 스냅샷을 갱신한다.

**Args:** 없음.

**Returns:**
- `list[FileChange]`: 변경된 파일 목록.

**Raises:**
- `RuntimeError`: 초기 `snapshot()`이 호출되지 않은 경우.

**Pre-conditions:**
- 최초 `snapshot()`이 호출되어야 한다.

**Post-conditions:**
- 변경사항이 반환된다.
- 내부 스냅샷이 현재 상태로 갱신된다.

**Side effects:**
- 파일 I/O

**실행 흐름:**
1. `diff()`로 변경사항 수집
2. `snapshot()`으로 스냅샷 갱신
3. 변경사항 반환

**Async/Sync:** Async

**사용 예시:**

```python
collector = FileDiffCollector("/tmp/worktrees/agent-impl-001")
await collector.snapshot()  # 에이전트 실행 전

# ... 에이전트 실행 ...

changes = await collector.collect_changes()
for change in changes:
    print(f"{change.change_type}: {change.path}")
    # added: src/middleware/auth.ts
    # modified: src/app.ts
```

---

## 9. AdapterFactory

> 모듈: `core/adapters/factory.py`

AgentPreset + AuthProvider로부터 CLIAgentExecutor 인스턴스를 생성하는 팩토리. 모든 에이전트는 CLI를 통해 실행되며, MCP 서버와 Skills는 CLI별 방식으로 주입된다.

### 9.1 `__init__`

```python
def __init__(
    self,
    auth_provider: AuthProvider,
    config: OrchestratorConfig,
) -> None:
```

**목적:** AdapterFactory를 초기화한다.

**Args:**
- `auth_provider` (`AuthProvider`): API 키 제공자.
- `config` (`OrchestratorConfig`): 시스템 설정 (default_timeout, cli_priority 등).

**Side effects:**
- `_auth_provider`, `_config` 저장
- CLI 이름 → 프로바이더 매핑 초기화:
  ```python
  _cli_provider_map = {
      "claude": "anthropic",
      "codex": "openai",
      "gemini": "google",
  }
  ```

**Async/Sync:** Sync

---

### 9.2 `create`

```python
def create(
    self,
    preset: AgentPreset,
    *,
    working_dir: str | None = None,
) -> CLIAgentExecutor:
```

**목적:** AgentPreset으로부터 CLIAgentExecutor를 생성한다. 모든 에이전트는 CLI를 통해 실행되며, MCP 서버와 Skills는 CLI 플래그/설정으로 주입된다.

**Args:**
- `preset` (`AgentPreset`): 에이전트 프리셋.
- `working_dir` (`str | None`): CLI 실행 작업 디렉토리. worktree 경로가 주로 사용됨.

**Returns:**
- `CLIAgentExecutor`: 생성된 실행기. 페르소나, MCP, Skills 설정이 포함된 CLIAdapter 래퍼.

**Raises:**
- `AuthError`: API 키를 찾을 수 없는 경우.
- `CLINotFoundError`: CLI 바이너리가 설치되지 않은 경우.

**Pre-conditions:**
- `preferred_cli`에 해당하는 API 키가 있어야 한다.
- `mcp_servers`가 있으면 해당 서버 설정이 유효해야 한다.

**Post-conditions:**
- 반환된 `CLIAgentExecutor`는 즉시 사용 가능하다.
- MCP 서버/Skills 설정이 CLI별 방식으로 주입된 상태이다.

**Side effects:**
- `AuthProvider.get_key()` 호출
- CLI 바이너리 존재 여부 확인 (which 명령)
- Codex: `CODEX_HOME` 임시 디렉토리에 `config.toml` 생성 (MCP 설정)
- Gemini: `working_dir/.gemini/settings.json` + `.gemini/GEMINI.md` 생성

**실행 흐름:**

```
1. preferred_cli에서 CLI 이름 결정
2. _cli_provider_map으로 프로바이더 이름 조회
3. auth_provider.get_key(provider)로 API 키 조회
4. persona.to_system_prompt()로 페르소나 프롬프트 생성
5. mcp_servers가 있으면 CLI별 MCP 설정 준비:
   - Claude:  --mcp-config JSON 플래그 생성
   - Codex:   CODEX_HOME 임시 디렉토리에 config.toml 작성
   - Gemini:  .gemini/settings.json 작성
6. skills가 있으면 skill 명령 목록 구성
7. AdapterConfig 생성 (api_key, timeout, model, working_dir,
                        mcp_config, persona_prompt, skills)
8. CLIAdapter 서브클래스 생성 (ClaudeAdapter/CodexAdapter/GeminiAdapter)
9. CLIAgentExecutor(adapter, config) 반환
```

**Async/Sync:** Sync

**사용 예시:**

```python
factory = AdapterFactory(auth_provider, config)

# 코딩 에이전트 (CLI only)
preset = registry.load_agent_preset("implementer")
executor = factory.create(preset, working_dir="/tmp/worktrees/impl-001")
# → CLIAgentExecutor(adapter=CodexAdapter, ...)

# ELK 분석 에이전트 (CLI + MCP servers)
preset = registry.load_agent_preset("elk-analyst")
executor = factory.create(preset, working_dir="/tmp/worktrees/elk-001")
# → CLIAgentExecutor(adapter=ClaudeAdapter,
#       mcp_config={"mcpServers": {"elasticsearch": {...}}})
# Claude CLI가 --mcp-config 플래그로 MCP 서버에 접근
```

---

## 10. CLIAdapter 서브클래스

> 모듈: `core/adapters/claude.py`, `core/adapters/codex.py`, `core/adapters/gemini.py`
> 기반: `core/adapters/base.py`

### 10.1 CLIAdapter (ABC)

```python
from abc import ABC, abstractmethod


class CLIAdapter(ABC):
    """CLI subprocess 실행 추상 기반 클래스.

    각 CLI 도구(Claude Code, Codex CLI, Gemini CLI)의 headless 실행을 캡슐화한다.
    """

    @property
    @abstractmethod
    def cli_name(self) -> str:
        """CLI 이름 ("claude", "codex", "gemini")."""
        ...

    @abstractmethod
    async def run(
        self,
        prompt: str,
        config: AdapterConfig,
    ) -> AgentResult:
        """CLI를 headless 모드로 실행하고 결과를 반환한다.

        Args:
            prompt: 에이전트에 전달할 프롬프트.
            config: 실행 설정.

        Returns:
            AgentResult: 파싱된 실행 결과.

        Raises:
            CLIExecutionError: 프로세스 실행 실패.
            CLITimeoutError: 타임아웃 초과.
            CLIParseError: 출력 파싱 실패.
        """
        ...

    @abstractmethod
    async def health_check(
        self,
        config: AdapterConfig,
    ) -> bool:
        """CLI 가용성을 확인한다.

        Args:
            config: 실행 설정 (API 키 포함).

        Returns:
            bool: 가용하면 True.
        """
        ...
```

---

### 10.2 ClaudeAdapter

```python
class ClaudeAdapter(CLIAdapter):
    """Claude Code CLI 어댑터.

    headless 명령:
        claude -p "{prompt}" --output-format json --permission-mode bypassPermissions

    페르소나 주입:
        --system-prompt "{persona_prompt}"

    MCP 서버 주입:
        --mcp-config '{"mcpServers": {"server-name": {"command": "...", "args": [...]}}}'

    Known issues:
        - stdin >7,000 chars → empty output. 긴 프롬프트는 temp file 사용
        - `--bare` 플래그 사용 금지 — firstParty 인증(claude.ai)과 충돌하여 "Not logged in" 에러 발생
        - `is_error` 필드: exit_code=0이지만 `is_error=true`일 수 있음 → 반드시 체크
        - ANTHROPIC_API_KEY가 없으면 firstParty 인증 사용 (환경변수 미설정)

    인증 모드:
        - firstParty (기본): ANTHROPIC_API_KEY 미설정 시 claude.ai 로그인 인증 사용
        - API key: ANTHROPIC_API_KEY 설정 시 해당 키 사용
    """

    @property
    def cli_name(self) -> str:
        return "claude"

    async def run(
        self,
        prompt: str,
        config: AdapterConfig,
    ) -> AgentResult:
        """Claude Code CLI를 실행한다.

        실행 흐름:
            1. 프롬프트 길이 확인 (>7000 chars → temp file로 전환)
            2. subprocess 명령어 구성:
               - claude -p "{prompt}" --output-format json
                 --permission-mode bypassPermissions
               - model 지정 시: --model {model}
               - persona 주입 시: --system-prompt "{persona_prompt}"
               - MCP 서버 주입 시: --mcp-config '{json}'
               - `--bare` 플래그 절대 사용하지 않음
            3. 환경 변수 설정: ANTHROPIC_API_KEY (있는 경우만)
               - 없으면 firstParty 인증 (claude.ai 로그인) 자동 사용
            4. stdin=DEVNULL (stdin 파이프 금지)
            5. working_dir에서 subprocess 실행 (asyncio.create_subprocess_exec)
            6. stdout JSON 파싱
            7. `is_error` 필드 체크: true이면 CLIExecutionError 발생
            8. AgentResult 생성:
               - output: JSON의 `result` 필드
               - exit_code: subprocess return code
               - duration_ms: JSON의 `duration_ms` 필드
               - tokens_used: JSON의 `usage.input_tokens + usage.output_tokens`
               - raw: 전체 JSON 응답

        MCP config 생성 예시:
            config.mcp_servers = {
                "elasticsearch": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-elasticsearch"],
                    "env": {"ELASTICSEARCH_URL": "..."}
                }
            }
            → --mcp-config '{"mcpServers": {"elasticsearch": {...}}}'

        Raises:
            CLIExecutionError: exit_code != 0
            CLITimeoutError: timeout 초과
            CLIParseError: JSON 파싱 실패
        """
        ...

    async def health_check(
        self,
        config: AdapterConfig,
    ) -> bool:
        """'claude --version' 실행으로 가용성 확인."""
        ...
```

---

### 10.3 CodexAdapter

```python
class CodexAdapter(CLIAdapter):
    """Codex CLI 어댑터.

    headless 명령:
        codex exec --json --ephemeral --full-auto "{prompt}"

    페르소나 주입:
        CODEX_HOME 디렉토리의 instructions 파일에 persona prompt 작성.

    MCP 서버 주입:
        CODEX_HOME 디렉토리의 config.toml에 mcp_servers 섹션 작성.
        Codex는 inline --mcp-config 플래그를 지원하지 않으므로,
        에이전트별 격리된 CODEX_HOME 디렉토리를 생성한다.

        예시 config.toml:
            [mcp_servers.elasticsearch]
            command = "npx"
            args = ["-y", "@modelcontextprotocol/server-elasticsearch"]
            [mcp_servers.elasticsearch.env]
            ELASTICSEARCH_URL = "..."

    Known issue:
        inline MCP injection 불가 → CODEX_HOME 격리 사용.
    """

    @property
    def cli_name(self) -> str:
        return "codex"

    async def run(
        self,
        prompt: str,
        config: AdapterConfig,
    ) -> AgentResult:
        """Codex CLI를 실행한다.

        실행 흐름:
            1. MCP 서버가 있으면 CODEX_HOME 임시 디렉토리 설정:
               a. 임시 디렉토리 생성 (/tmp/codex-home-{worker_id}/)
               b. config.toml 작성 (mcp_servers 섹션)
               c. instructions 파일에 persona prompt 작성
            2. subprocess 명령어 구성:
               - codex exec --json --ephemeral --full-auto "{prompt}"
               - model 지정 시: --model {model}
            3. 환경 변수 설정: OPENAI_API_KEY, CODEX_HOME (MCP 사용 시)
            4. working_dir에서 subprocess 실행
            5. stdout JSON 파싱 (NDJSON 형식 처리)
            6. AgentResult 생성:
               - output: 마지막 message의 text
               - raw: 전체 JSON 이벤트 배열

        Raises:
            CLIExecutionError: exit_code != 0
            CLITimeoutError: timeout 초과
            CLIParseError: JSON 파싱 실패
        """
        ...

    async def health_check(
        self,
        config: AdapterConfig,
    ) -> bool:
        """'codex --version' 실행으로 가용성 확인."""
        ...
```

---

### 10.4 GeminiAdapter

```python
class GeminiAdapter(CLIAdapter):
    """Gemini CLI 어댑터.

    headless 명령:
        gemini -p "{prompt}" --output-format stream-json --yolo

    페르소나 주입:
        working_dir/.gemini/GEMINI.md 파일에 persona prompt 작성.

    MCP 서버 주입:
        working_dir/.gemini/settings.json에 mcpServers 섹션 작성.

        예시 settings.json:
            {
              "mcpServers": {
                "elasticsearch": {
                  "command": "npx",
                  "args": ["-y", "@modelcontextprotocol/server-elasticsearch"],
                  "env": {"ELASTICSEARCH_URL": "..."}
                }
              }
            }

    Known issues:
        - stdout pollution bug (#21433) → stream-json에서 result 이벤트만 필터링
        - Tool hang in headless (#19774) → --yolo 필수
    """

    @property
    def cli_name(self) -> str:
        return "gemini"

    async def run(
        self,
        prompt: str,
        config: AdapterConfig,
    ) -> AgentResult:
        """Gemini CLI를 실행한다.

        실행 흐름:
            1. MCP 서버/페르소나가 있으면 .gemini/ 디렉토리 설정:
               a. working_dir/.gemini/ 디렉토리 생성
               b. settings.json 작성 (mcpServers 섹션)
               c. GEMINI.md 작성 (persona prompt)
            2. subprocess 명령어 구성:
               - gemini -p "{prompt}" --output-format stream-json --yolo
               - model 지정 시: --model {model}
            3. 환경 변수 설정: GOOGLE_API_KEY (또는 GEMINI_API_KEY)
            4. working_dir에서 subprocess 실행
            5. stdout stream-json 파싱:
               - 각 줄을 JSON으로 파싱
               - type=="result" 이벤트만 필터링 (stdout pollution 대응)
            6. AgentResult 생성:
               - output: result 이벤트의 text
               - raw: 전체 필터링된 이벤트 배열

        Raises:
            CLIExecutionError: exit_code != 0
            CLITimeoutError: timeout 초과
            CLIParseError: JSON 파싱 실패 또는 result 이벤트 없음
        """
        ...

    async def health_check(
        self,
        config: AdapterConfig,
    ) -> bool:
        """'gemini --version' 실행으로 가용성 확인."""
        ...
```

---

## 부록: CLI 실행 명령 요약

| CLI | Headless 명령 | 환경 변수 | 출력 형식 |
|-----|--------------|-----------|-----------|
| Claude Code | `claude -p "{prompt}" --output-format json --permission-mode bypassPermissions` | `ANTHROPIC_API_KEY` (없으면 firstParty 인증 사용) | JSON (단일 객체) |
| Codex CLI | `codex exec --json --ephemeral --full-auto "{prompt}"` | `OPENAI_API_KEY` | NDJSON (이벤트 스트림) |
| Gemini CLI | `gemini -p "{prompt}" --output-format stream-json --yolo` | `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Stream-JSON (이벤트 스트림, `result`만 필터) |

## 부록: CLI별 MCP/페르소나 주입 방법

| CLI | 페르소나 주입 | MCP 서버 주입 |
|-----|--------------|---------------|
| Claude Code | `--system-prompt "{persona}"` | `--mcp-config '{"mcpServers":{...}}'` |
| Codex CLI | `CODEX_HOME/instructions` 파일 | `CODEX_HOME/config.toml`의 `[mcp_servers]` 섹션 |
| Gemini CLI | `.gemini/GEMINI.md` 파일 | `.gemini/settings.json`의 `mcpServers` 필드 |

## 부록: 에러 계층 구조

```python
class OrchestratorError(Exception):
    """오케스트레이터 기반 예외."""
    pass

class CLIError(OrchestratorError):
    """CLI 관련 예외 기반 클래스."""
    cli: str  # "claude" | "codex" | "gemini"

class CLIExecutionError(CLIError):
    """CLI 프로세스 실행 실패."""
    exit_code: int
    stderr: str

class CLITimeoutError(CLIError):
    """CLI 실행 타임아웃."""
    timeout: int

class CLIParseError(CLIError):
    """CLI 출력 파싱 실패."""
    raw_output: str

class CLINotFoundError(CLIError):
    """CLI 바이너리를 찾을 수 없음."""
    pass

class AuthError(OrchestratorError):
    """인증 관련 예외."""
    provider: str

class WorktreeError(OrchestratorError):
    """Git worktree 관련 예외."""
    pass

class MergeConflictError(WorktreeError):
    """Git merge conflict 발생."""
    conflicting_files: list[str]

class DecompositionError(OrchestratorError):
    """태스크 분해 실패."""
    pass

class AllProvidersFailedError(OrchestratorError):
    """모든 CLI 프로바이더가 실패."""
    errors: dict[str, str]  # cli_name → error_message
```

---

## 11. API 계층

> 모듈: `api/app.py`, `api/deps.py`, `api/routes.py`, `api/ws.py`

### 11.1 `create_app`

```python
def create_app() -> FastAPI:
```

**목적:** FastAPI 앱 인스턴스를 생성한다. lifespan 컨텍스트 매니저를 등록한다.

**실행 흐름:**
```
1. FastAPI(title="Agent Team Orchestrator", version="1.0.0", lifespan=lifespan) 생성
2. CORS 미들웨어 추가
3. 라우터 등록 (routes.py)
4. WebSocket 엔드포인트 등록 (ws.py)
5. app 반환
```

### 11.2 `lifespan` (async context manager)

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
```

**목적:** 서버 시작/종료 시 Engine lifecycle을 관리한다.

**실행 흐름:**
```
startup:
  1. OrchestratorEngine 인스턴스 생성
  2. await engine.start() 호출
  3. app.state.engine = engine 저장

shutdown:
  1. await engine.shutdown() 호출 (워커 정지, 백그라운드 태스크 취소)
```

**주의:** 이 함수가 engine.start()/shutdown()을 호출하지 않으면 서버 모드에서 워커가 정리되지 않는다.

### 11.3 `get_engine` (deps.py)

```python
def get_engine(request: Request) -> OrchestratorEngine:
```

**목적:** FastAPI 의존성 주입. app.state.engine을 반환한다.

### 11.4 라우트 함수

api-spec.md에 정의된 18개 엔드포인트에 대응하는 라우트 함수. 각 함수는 `engine = Depends(get_engine)`으로 Engine을 주입받는다.

상세 요청/응답 스키마는 [api-spec.md](api-spec.md) 참조.

### 11.5 WebSocket 매니저 (ws.py)

```python
class WebSocketManager:
    async def connect(self, ws: WebSocket) -> None
    def disconnect(self, ws: WebSocket) -> None
    async def broadcast(self, event: OrchestratorEvent) -> None
```

**목적:** WebSocket 연결 관리 + EventBus 이벤트를 클라이언트에 브로드캐스트.

**통합:** engine.subscribe(ws_manager.broadcast)로 EventBus와 연결.

---

## 12. CLI (Interface 계층)

> 모듈: `cli.py`
> 아키텍처 원칙: CLI는 Engine을 직접 사용한다 (서버 없이 단독 실행 가능).
> 서버 모드 시에는 `orchestrator serve`로 API 서버를 띄우고 웹/외부 클라이언트가 API를 호출한다.

### 12.1 `run`

```python
def run(
    task: str,                                          # 태스크 설명 (필수)
    repo: str | None = None,                            # --repo, -r: 대상 Git 저장소
    team_preset: str | None = None,                     # --team-preset, -t: 팀 프리셋
    timeout: int = 600,                                 # --timeout: 전체 타임아웃(초)
    wait: bool = True,                                  # --wait/--no-wait: 완료 대기
) -> None:
```

**목적:** 태스크를 실행하고 완료까지 대기한다.

**실행 흐름:**

```
1. OrchestratorEngine 생성 + start()
2. engine.submit_task(task, team_preset, target_repo) 호출
3. --wait=True (기본):
   a. engine.get_pipeline(task_id) 폴링 (0.5초 간격)
   b. 상태 변경 시 터미널 출력 (PENDING→PLANNING→RUNNING→SYNTHESIZING→COMPLETED)
   c. 터미널 상태 도달 시 결과 출력 + 종료
   d. timeout 초과 시 engine.cancel_task() + 종료
4. --wait=False:
   a. Pipeline ID만 출력하고 즉시 반환
5. finally: engine.shutdown() (워커 정리, 백그라운드 태스크 취소)
```

**주의:**
- `asyncio.run()` 안에서 실행됨
- submit_task가 background `asyncio.create_task`로 파이프라인을 실행함
- wait 폴링 루프가 이벤트 루프를 유지하여 background task가 실행될 수 있도록 함
- shutdown()이 호출되지 않으면 subprocess 좀비 프로세스 발생

### 12.2 `status`

```python
def status(
    task_id: str | None = None,                         # 선택: 특정 파이프라인 ID
) -> None:
```

**목적:** 파이프라인 상태를 조회한다.
- `task_id` 없으면: 전체 파이프라인 목록 (테이블)
- `task_id` 있으면: 해당 파이프라인 상세 (task, status, subtasks, error)

### 12.3 `cancel`

```python
def cancel(
    task_id: str,                                       # 필수: 취소할 파이프라인 ID
) -> None:
```

**목적:** 실행 중인 파이프라인을 취소한다. `engine.cancel_task()` 호출.

### 12.4 `resume`

```python
def resume(
    task_id: str,                                       # 필수: 재개할 파이프라인 ID
) -> None:
```

**목적:** 중단된 파이프라인을 재개한다. `engine.start()` → `engine.resume_task()` → `engine.shutdown()`.

### 12.5 `presets list`

```python
def presets_list() -> None:
```

**목적:** 모든 에이전트/팀 프리셋 목록을 출력한다. `engine.list_agent_presets()` + `engine.list_team_presets()`.

### 12.6 `presets show`

```python
def presets_show(
    name: str,                                          # 필수: 프리셋 이름
) -> None:
```

**목적:** 프리셋 상세를 출력한다. 에이전트 프리셋 먼저 검색, 없으면 팀 프리셋 검색.

### 12.7 `serve`

```python
def serve(
    host: str = "0.0.0.0",                             # --host
    port: int = 9000,                                   # --port (기본: 9000)
    reload: bool = False,                               # --reload
) -> None:
```

**목적:** API 서버를 실행한다. `uvicorn.run()` 호출.

---

## 13. OrchestratorEngine Lifecycle

> Engine은 `start()`/`shutdown()` lifecycle 메서드를 가진다.

### 13.1 `start`

```python
async def start(self) -> None:
```

**목적:** 엔진을 시작한다. 현재는 로그만 출력하지만, 향후 체크포인트 복원 등 초기화 로직 배치.

**Side effects:**
- `logger.info("engine_started")` 출력

### 13.2 `shutdown`

```python
async def shutdown(self) -> None:
```

**목적:** 모든 워커를 정지하고 백그라운드 태스크를 취소한다.

**실행 흐름:**

```
1. self._workers의 모든 워커에 대해 worker.stop() 호출
2. self._bg_tasks의 모든 태스크에 대해 task.cancel() 호출
3. _workers, _bg_tasks 딕셔너리 초기화
4. logger.info("engine_shutdown") 출력
```

**Pre-conditions:** 없음 (시작하지 않은 상태에서 호출해도 안전).
**Post-conditions:** 모든 워커 정지, 모든 백그라운드 태스크 취소.
