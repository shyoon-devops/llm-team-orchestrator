# v2 iter20 — CLI Loose Coupling (Engine Direct Import → HTTP Client)

> 작성일: 2026-04-06
> **목표:** CLI가 OrchestratorEngine을 직접 import하는 밀결합(tight coupling)을 제거하고, HTTP 클라이언트로 전환하여 CLI와 서버를 분리한다.

---

## 핵심 결론 (먼저 읽기)

1. **현재 문제**: `cli.py`가 `from orchestrator.core.engine import OrchestratorEngine`으로 엔진을 직접 생성 — CLI와 서버가 동일 프로세스 강제, 원격 서버 연결 불가, 웹 프론트엔드와 상태 공유 불가
2. **해결**: CLI를 `httpx.AsyncClient` 기반 HTTP 클라이언트로 전환. 모든 명령이 `http://{host}:{port}/api/...` REST API를 호출
3. **CLI 기본 서버**: `--server http://localhost:8000` 옵션 (환경 변수 `ORCHESTRATOR_SERVER_URL`로도 설정 가능)
4. **필요한 신규 API 엔드포인트**: `GET /api/config` (설정 조회)
5. **필요한 CRUD 보완 엔드포인트**: `PUT/DELETE /api/presets/agents/{name}`, `PUT/DELETE /api/presets/teams/{name}`
6. **하위 호환성**: 불필요 — 클린 브레이크. `serve` 명령은 서버 시작이므로 변경 없음

---

## 1. 문제 분석

### 1.1 현재 밀결합 지점 (cli.py)

| 위치 | 코드 | 문제 |
|------|------|------|
| L88 | `from orchestrator.core.engine import OrchestratorEngine` | `run` 커맨드 — 엔진 직접 생성 |
| L172 | `from orchestrator.core.engine import OrchestratorEngine` | `status` 커맨드 |
| L192 | `from orchestrator.core.engine import OrchestratorEngine` | `cancel` 커맨드 |
| L212 | `from orchestrator.core.engine import OrchestratorEngine` | `resume` 커맨드 |
| L232 | `from orchestrator.core.config.schema import OrchestratorConfig` | `config` 커맨드 — Config 직접 생성 |
| L252 | `from orchestrator.core.engine import OrchestratorEngine` | `agents` 커맨드 |
| L288 | `from orchestrator.core.engine import OrchestratorEngine` | `subtask` 커맨드 |
| L339 | `from orchestrator.core.engine import OrchestratorEngine` | `presets list` 커맨드 |
| L380 | `from orchestrator.core.engine import OrchestratorEngine` | `presets show` 커맨드 |

### 1.2 밀결합의 부작용

- CLI 실행 시 엔진의 모든 의존성(LangGraph, LiteLLM, MCP 등)이 import됨
- CLI 프로세스에서 별도 엔진을 생성하므로 서버와 상태가 공유되지 않음
- 원격 서버에 연결할 수 없음
- CLI 테스트 시 엔진 전체를 mock해야 함

---

## 2. 해결 설계

### 2.1 CLI → HTTP 매핑

| CLI 명령 | HTTP 요청 | 비고 |
|----------|----------|------|
| `orchestrator run "task" --team-preset t --repo r` | `POST /api/tasks` → poll `GET /api/tasks/{id}` | `--wait`일 때 1초 폴링 + WS 이벤트 |
| `orchestrator status {task_id}` | `GET /api/tasks/{task_id}` | |
| `orchestrator cancel {task_id}` | `DELETE /api/tasks/{task_id}` | |
| `orchestrator resume {task_id}` | `POST /api/tasks/{task_id}/resume` | |
| `orchestrator config` | `GET /api/config` | **신규 엔드포인트** |
| `orchestrator agents` | `GET /api/presets/agents` | |
| `orchestrator subtask {tid}` | `GET /api/tasks/{tid}/subtasks` | 전체 서브태스크 목록 |
| `orchestrator subtask {tid} {sid}` | `GET /api/tasks/{tid}/subtasks/{sid}` | 개별 서브태스크 상세 |
| `orchestrator presets list` | `GET /api/presets/agents` + `GET /api/presets/teams` | 병렬 요청 |
| `orchestrator presets show {name}` | `GET /api/presets/agents/{name}` → 404시 `GET /api/presets/teams/{name}` | |
| `orchestrator serve` | (변경 없음) | 서버 시작, 엔진 직접 사용 유지 |

### 2.2 CLI 신규 옵션

```python
# 글로벌 콜백으로 모든 명령에 적용
@app.callback()
def main(
    server: str = typer.Option(
        "http://localhost:8000",
        "--server",
        envvar="ORCHESTRATOR_SERVER_URL",
        help="오케스트레이터 서버 URL",
    ),
) -> None:
    """Agent Team Orchestrator CLI"""
    global _server_url
    _server_url = server.rstrip("/")
```

### 2.3 HTTP 클라이언트 헬퍼

```python
import httpx

def _client() -> httpx.AsyncClient:
    """서버 URL 기반 AsyncClient를 생성한다."""
    return httpx.AsyncClient(base_url=_server_url, timeout=30.0)
```

### 2.4 에러 처리

HTTP 에러 → CLI 에러 매핑:

| HTTP 상태 | CLI 동작 |
|-----------|---------|
| 200/201 | 정상 처리 |
| 404 | `[red]Not found[/red]` + `typer.Exit(1)` |
| 409 | `[red]Conflict[/red]` + 에러 메시지 |
| 422 | `[red]Validation error[/red]` |
| 500+ | `[red]Server error[/red]` |
| ConnectionError | `[red]Cannot connect to server at {url}[/red]` |

```python
def _handle_error(resp: httpx.Response) -> None:
    """HTTP 에러를 CLI 에러로 변환한다."""
    if resp.is_success:
        return
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    color = "red"
    if resp.status_code == 404:
        console.print(f"[{color}]Not found:[/{color}] {detail}")
    elif resp.status_code == 409:
        console.print(f"[{color}]Conflict:[/{color}] {detail}")
    elif resp.status_code == 422:
        console.print(f"[{color}]Validation error:[/{color}] {detail}")
    else:
        console.print(f"[{color}]Server error ({resp.status_code}):[/{color}] {detail}")
    raise typer.Exit(code=1)
```

---

## 3. 신규 API 엔드포인트

### 3.1 `GET /api/config`

설정 필드와 값을 JSON으로 반환한다.

**응답 예시:**
```json
{
  "fields": {
    "app_name": {"value": "agent-team-orchestrator", "description": "애플리케이션 이름"},
    "debug": {"value": false, "description": "디버그 모드"},
    "default_timeout": {"value": 300, "description": "기본 에이전트 실행 타임아웃 (초)"},
    ...
  }
}
```

**구현:**
```python
@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """현재 오케스트레이터 설정을 반환한다."""
    engine = get_engine(request)
    config = engine.config
    fields = {}
    for field_name, field_info in OrchestratorConfig.model_fields.items():
        fields[field_name] = {
            "value": getattr(config, field_name),
            "description": field_info.description or "",
        }
    return {"fields": fields}
```

### 3.2 `PUT /api/presets/agents/{name}`

에이전트 프리셋을 업데이트(덮어쓰기)한다. `save_agent_preset(overwrite=True)` 호출.

### 3.3 `DELETE /api/presets/agents/{name}`

에이전트 프리셋을 삭제한다. 레지스트리와 YAML 파일에서 제거.

### 3.4 `PUT /api/presets/teams/{name}`

팀 프리셋을 업데이트(덮어쓰기)한다.

### 3.5 `DELETE /api/presets/teams/{name}`

팀 프리셋을 삭제한다.

> **참고**: DELETE 엔드포인트를 위해 PresetRegistry와 OrchestratorEngine에 `delete_agent_preset(name)`, `delete_team_preset(name)` 메서드 추가가 필요하다.

---

## 4. `run --wait` 폴링 루프

기존 `engine.get_pipeline()` 직접 호출 대신 HTTP 폴링:

```python
async def _run() -> None:
    async with _client() as client:
        # 1. 태스크 제출
        resp = await client.post("/api/tasks", json={
            "task": task,
            "team_preset": team_preset,
            "target_repo": repo,
        })
        _handle_error(resp)
        pipeline = resp.json()
        task_id = pipeline["task_id"]

        if not wait:
            console.print(f"[green]Pipeline created:[/green] {task_id}")
            return

        # 2. 폴링 루프 (Rich Live)
        terminal_states = {"completed", "failed", "partial_failure", "cancelled"}
        elapsed = 0

        with Live(...) as live:
            while elapsed < timeout:
                await asyncio.sleep(1)
                elapsed += 1

                # Board state 조회
                board_resp = await client.get("/api/board")
                board_state = board_resp.json() if board_resp.is_success else {}
                live.update(_build_progress_table(task_id, task, board_state, elapsed))

                # Pipeline 상태 체크
                status_resp = await client.get(f"/api/tasks/{task_id}")
                if status_resp.is_success:
                    current = status_resp.json()
                    if current.get("status") in terminal_states:
                        break
```

---

## 5. 변경 파일 목록

| 파일 | 변경 | 설명 |
|------|------|------|
| `src/orchestrator/cli.py` | **전면 개편** | 엔진 import → httpx HTTP 클라이언트 |
| `src/orchestrator/api/routes.py` | 추가 | `GET /api/config`, `PUT/DELETE /api/presets/{agents,teams}/{name}` |
| `src/orchestrator/core/presets/registry.py` | 추가 | `delete_agent_preset()`, `delete_team_preset()` |
| `src/orchestrator/core/engine.py` | 추가 | `delete_agent_preset()`, `delete_team_preset()` 위임 메서드 |
| `tests/unit/test_cli_progress.py` | (유지) | 테이블 빌드 로직 자체는 변경 없음 |

---

## 6. 제외 사항

- WebSocket 실시간 스트리밍은 이 이터레이션에서 구현하지 않음. 폴링으로 충분.
- `serve` 명령은 서버 시작이므로 엔진 직접 사용 유지.
- 인증/토큰 기반 CLI→서버 인증은 향후 이터레이션.

---

## 7. Dry-Run Trace (시나리오 검증)

### Scenario 1: `orchestrator run "JWT 인증 구현" --team-preset feature-team --repo ./proj --wait`

```
1. Typer 파싱 → task="JWT 인증 구현", team_preset="feature-team", repo="./proj", wait=True, timeout=600
2. _server_url = "http://localhost:8000" (기본값 또는 --server 옵션)
3. async _run() 진입
4. httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) 생성
5. POST /api/tasks  body={"task":"JWT 인증 구현","team_preset":"feature-team","target_repo":"./proj"}
   → 서버: engine.submit_task() → Pipeline 생성 → 201 응답
   → resp.json() = {"task_id":"pipe-abc123","status":"pending","task":"JWT 인증 구현",...}
6. task_id = "pipe-abc123"
7. console.print("[green]Pipeline created:[/green] pipe-abc123")
8. wait=True → 폴링 루프 진입
9. Rich Live 시작 (transient=True)
10. Loop iteration (elapsed=1):
    a. asyncio.sleep(1)
    b. GET /api/board → {"lanes":{"architect":{...},...}}
    c. _build_progress_table("pipe-abc123", "JWT 인증 구현", board_state, 1)
    d. live.update(table)
    e. GET /api/tasks/pipe-abc123 → {"status":"in_progress",...}
    f. "in_progress" not in terminal_states → continue
11. Loop iteration (elapsed=60):
    a. GET /api/board → architect:done, implementer:done, reviewer:done
    b. GET /api/tasks/pipe-abc123 → {"status":"completed","synthesis":"..."}
    c. "completed" in terminal_states → break
12. Live 종료
13. GET /api/board → 최종 board_state
14. console.print(최종 테이블)
15. GET /api/tasks/pipe-abc123 → current
16. console.print("[blue]Final status:[/blue] completed")
17. current["synthesis"] 존재 → console.print("[bold]Synthesis Report:[/bold]\n...")
18. httpx.AsyncClient.__aexit__ → 연결 종료

에러 경로:
- POST /api/tasks → 404 (team_preset 미존재): _handle_error() → "[red]Not found[/red]" → Exit(1)
- POST /api/tasks → ConnectionError (서버 미실행): except httpx.ConnectError → "[red]Cannot connect[/red]" → Exit(1)
- 폴링 timeout (elapsed >= 600): console.print("[yellow]Timeout[/yellow]")
```

### Scenario 2: `orchestrator presets show feature-team`

```
1. Typer 파싱 → name="feature-team"
2. _server_url = "http://localhost:8000"
3. httpx.AsyncClient 생성
4. GET /api/presets/agents/feature-team
   → 404 (에이전트 프리셋 아님)
5. GET /api/presets/teams/feature-team
   → 200 {"name":"feature-team","description":"...","workflow":"dag","agents":{...},"tasks":{...}}
6. data = resp.json()
7. console.print("[bold]Team Preset:[/bold] feature-team")
8. console.print("[blue]Description:[/blue] ...")
9. console.print("[blue]Workflow:[/blue] dag")
10. console.print("[blue]Synthesis:[/blue] narrative")
11. agents 순회 → "architect: preset=architect", "implementer: preset=implementer", ...
12. tasks 순회 → "design: agent=architect", "implement: agent=implementer [depends: design]", ...
13. httpx.AsyncClient.__aexit__

에러 경로:
- 두 GET 모두 404: "[red]Preset not found:[/red] feature-team" → Exit(1)
- ConnectionError: "[red]Cannot connect to server[/red]" → Exit(1)
```

### Scenario 3: `orchestrator config` (서버 미실행 상태)

```
1. Typer 파싱 → config_show() 호출
2. _server_url = "http://localhost:8000"
3. async _config() 진입
4. httpx.AsyncClient 생성
5. GET /api/config
   → httpx.ConnectError 발생 (서버 미실행)
6. except httpx.ConnectError:
   console.print("[red]Cannot connect to server at http://localhost:8000[/red]")
   console.print("[dim]Hint: Start the server with 'orchestrator serve'[/dim]")
   raise typer.Exit(code=1)

정상 경로:
5. GET /api/config → 200
   {"fields":{"app_name":{"value":"agent-team-orchestrator","description":"..."},...}}
6. data = resp.json()
7. Rich Table 생성 (title="Orchestrator Configuration")
8. fields 순회:
   table.add_row("app_name", "agent-team-orchestrator", "애플리케이션 이름")
   table.add_row("debug", "False", "디버그 모드")
   ...
9. console.print(table)
```

---

## 8. 교차 검증 매트릭스

| CLI 명령 | API 엔드포인트 | 엔드포인트 존재 | 응답→표시 매핑 검증 |
|----------|---------------|:-:|:-:|
| `run` | `POST /api/tasks` | O | O (task_id, status 표시) |
| `run --wait` | `GET /api/tasks/{id}` + `GET /api/board` | O | O (폴링→Live 테이블) |
| `status` | `GET /api/tasks/{id}` | O | O (task, status 표시) |
| `cancel` | `DELETE /api/tasks/{id}` | O | O (204→성공, 404→실패) |
| `resume` | `POST /api/tasks/{id}/resume` | O | O (task_id, status 표시) |
| `config` | `GET /api/config` | **신규** | O (fields 순회→테이블) |
| `agents` | `GET /api/presets/agents` | O | O (presets→에이전트 테이블) |
| `subtask {tid}` | `GET /api/tasks/{tid}/subtasks` | O | O (subtasks→목록 테이블) |
| `subtask {tid} {sid}` | `GET /api/tasks/{tid}/subtasks/{sid}` | O | O (상세→Markdown) |
| `presets list` | `GET /api/presets/agents` + `GET /api/presets/teams` | O | O (병렬 조회→2테이블) |
| `presets show {n}` | `GET /api/presets/agents/{n}` / `teams/{n}` | O | O (폴백 조회→상세 표시) |
| `serve` | (변경 없음) | - | - |
