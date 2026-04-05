# 카오스 엔지니어링 명세

> v1.0 | 2026-04-06
> 목적: 시스템의 내결함성을 검증하기 위한 의도적 장애 주입 시나리오 및 기대 동작 정의

---

## 1. 카오스 테스트 원칙

| 원칙 | 설명 |
|------|------|
| **정상 상태 정의** | 테스트 전 "정상"이 무엇인지 먼저 확인 (pipeline COMPLETED, 0 errors) |
| **가설 수립** | "X가 발생하면 시스템은 Y로 복구해야 한다" |
| **최소 폭발 반경** | 한 번에 하나의 장애만 주입, 격리된 환경에서 실행 |
| **자동 복구 확인** | 장애 해소 후 시스템이 정상으로 돌아오는지 확인 |
| **sandbox 필수** | 모든 카오스 테스트는 `cwd=tempdir`에서 실행 |

---

## 2. 장애 주입 카테고리

### 2.1 CLI 장애

| ID | 시나리오 | 주입 방법 | 기대 동작 |
|----|----------|----------|----------|
| C-CLI-01 | Claude CLI 타임아웃 | `AdapterConfig(timeout=3)` (3초) | RetryPolicy 재시도 3회 → FallbackChain → codex 시도 |
| C-CLI-02 | Codex CLI 비정상 종료 | mock adapter `exit_code=1` 반환 | CLIExecutionError → retry → fallback → gemini |
| C-CLI-03 | Gemini CLI stdout 오염 | 유효하지 않은 JSON 반환 | CLIParseError → retry (파싱 실패는 재시도 가능) |
| C-CLI-04 | 모든 CLI 동시 실패 | 3개 CLI 전부 FailingMockAdapter | AllProvidersFailedError → pipeline FAILED |
| C-CLI-05 | CLI 프로세스 좀비 | subprocess.kill() 후 재시도 | 타임아웃 후 프로세스 정리, 다음 시도 정상 |
| C-CLI-06 | CLI 느린 응답 | `asyncio.sleep(60)` mock | heartbeat 이벤트 발행 중, 타임아웃 시 취소 |

### 2.2 TaskBoard 장애

| ID | 시나리오 | 주입 방법 | 기대 동작 |
|----|----------|----------|----------|
| C-BOARD-01 | 태스크 의존성 데드락 | A→B, B→A 순환 depends_on | 유효성 검증에서 에러 (제출 시점에 거부) |
| C-BOARD-02 | 레인에 워커 없음 | 워커 시작하지 않고 태스크 제출 | 태스크 TODO 상태 유지, 타임아웃 후 FAILED |
| C-BOARD-03 | 워커 중간 crash | worker.stop() 강제 호출 | 실행 중 태스크 FAILED → retry → 큐 복귀 |
| C-BOARD-04 | 동시 다수 파이프라인 | 5개 파이프라인 동시 제출 | task_id별 격리, 서로 간섭 없음 |
| C-BOARD-05 | 큐 포화 | maxsize=1 큐에 100개 태스크 | backpressure 동작, submit 대기 |

### 2.3 네트워크/인프라 장애

| ID | 시나리오 | 주입 방법 | 기대 동작 |
|----|----------|----------|----------|
| C-NET-01 | API 서버 재시작 | uvicorn kill → restart | 체크포인트에서 복원, resume 가능 |
| C-NET-02 | WebSocket 끊김 | 클라이언트 WS 연결 종료 | 프론트엔드 자동 재연결 (exponential backoff) |
| C-NET-03 | MCP 서버 응답 없음 | MCP 서버 프로세스 미시작 | CLI가 MCP 도구 사용 불가 → 일반 응답으로 fallback |
| C-NET-04 | 디스크 공간 부족 | tmpdir에 대용량 파일 생성 | ArtifactStore 저장 실패 → 에러 로그, 파이프라인은 계속 |

### 2.4 인증 장애

| ID | 시나리오 | 주입 방법 | 기대 동작 |
|----|----------|----------|----------|
| C-AUTH-01 | API 키 만료 | 잘못된 ANTHROPIC_API_KEY 설정 | AuthError → 즉시 실패 (재시도 없음) → fallback CLI |
| C-AUTH-02 | firstParty 인증 만료 | claude.ai 세션 만료 | is_error=true → CLIExecutionError → fallback |
| C-AUTH-03 | KeyPool 전체 소진 | 모든 키에 mark_exhausted() | AllProvidersFailedError |

### 2.5 데이터 장애

| ID | 시나리오 | 주입 방법 | 기대 동작 |
|----|----------|----------|----------|
| C-DATA-01 | 체크포인트 파일 손상 | checkpoint JSON에 invalid 데이터 삽입 | load 실패 → 새 파이프라인으로 시작 (기존 데이터 무시) |
| C-DATA-02 | 프리셋 YAML 오류 | 문법 오류가 있는 YAML 프리셋 | PresetRegistry 로딩 시 경고 로그, 해당 프리셋만 스킵 |
| C-DATA-03 | worktree 충돌 | 동일 브랜치명으로 worktree 생성 시도 | WorktreeError → 파이프라인 FAILED |
| C-DATA-04 | merge 충돌 | worktree에서 같은 파일 수정 | MergeConflictError → PARTIALLY_COMPLETED |

---

## 3. 카오스 테스트 구현

### 3.1 테스트 파일 구조

```
tests/chaos/
├── conftest.py                    # 카오스 전용 fixture (FailingAdapter, SlowAdapter 등)
├── test_cli_chaos.py              # C-CLI-01 ~ C-CLI-06
├── test_board_chaos.py            # C-BOARD-01 ~ C-BOARD-05
├── test_network_chaos.py          # C-NET-01 ~ C-NET-04
├── test_auth_chaos.py             # C-AUTH-01 ~ C-AUTH-03
└── test_data_chaos.py             # C-DATA-01 ~ C-DATA-04
```

### 3.2 카오스 Fixture

```python
# tests/chaos/conftest.py

class TimeoutAdapter(CLIAdapter):
    """항상 타임아웃되는 어댑터."""
    async def run(self, prompt, config, **kw):
        await asyncio.sleep(config.timeout + 10)  # 타임아웃 초과

class SlowAdapter(CLIAdapter):
    """느리지만 결국 응답하는 어댑터. heartbeat 테스트용."""
    def __init__(self, delay_seconds: int = 30):
        self.delay = delay_seconds
    async def run(self, prompt, config, **kw):
        await asyncio.sleep(self.delay)
        return AgentResult(output="slow response", duration_ms=self.delay*1000)

class FailOnceAdapter(CLIAdapter):
    """첫 호출 실패, 두 번째 성공."""
    def __init__(self):
        self._call_count = 0
    async def run(self, prompt, config, **kw):
        self._call_count += 1
        if self._call_count == 1:
            raise CLIExecutionError("first call fails", cli="mock")
        return AgentResult(output="success on retry")

class CorruptOutputAdapter(CLIAdapter):
    """유효하지 않은 출력을 반환."""
    async def run(self, prompt, config, **kw):
        return AgentResult(output="{{invalid json not parsed}}")
```

### 3.3 테스트 패턴

```python
# tests/chaos/test_cli_chaos.py

@pytest.mark.chaos
class TestCLIChaos:
    async def test_c_cli_01_timeout_triggers_retry_and_fallback(self):
        """C-CLI-01: Claude 타임아웃 → retry 3회 → codex fallback."""
        engine = OrchestratorEngine()
        # Claude에 TimeoutAdapter 주입
        # submit_task → 실행 → retry 로그 확인 → fallback 이벤트 확인
        # pipeline 최종 상태: COMPLETED (fallback 성공) 또는 FAILED (전체 실패)

    async def test_c_cli_06_slow_response_heartbeat(self):
        """C-CLI-06: 느린 CLI → heartbeat 이벤트 발행 확인."""
        # SlowAdapter(delay=30) 주입
        # 10초, 20초 시점에 worker.heartbeat 이벤트 수신 확인
        # elapsed_ms 증가 확인
```

### 3.4 pytest 마커

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "chaos: 카오스 엔지니어링 테스트 (장애 주입)",
]
```

```bash
# 카오스 테스트만 실행
uv run pytest tests/chaos/ -v -m chaos

# 일반 테스트에서 제외
uv run pytest tests/ -m "not chaos"
```

---

## 4. 카오스 테스트 실행 절차

```
1. 정상 상태 확인
   $ uv run pytest tests/ -q --tb=no    # 전체 통과 확인

2. 카오스 테스트 실행
   $ uv run pytest tests/chaos/ -v --tb=short -m chaos

3. 결과 분석
   - 모든 테스트 PASSED: 시스템 내결함성 확보
   - FAILED 테스트: 해당 장애 시나리오에 대한 복구 로직 누락

4. 복구 로직 추가 (FAILED 시)
   - 명세 먼저 수정 (docs/)
   - 구현 패치
   - 카오스 테스트 재실행
```

---

## 5. 카오스 테스트 vs 일반 테스트 경계

| 구분 | 일반 테스트 | 카오스 테스트 |
|------|-----------|-------------|
| **목적** | 기능이 명세대로 동작하는가 | 장애 상황에서 시스템이 복구하는가 |
| **장애 주입** | MockAdapter (정상 응답) | TimeoutAdapter, FailOnceAdapter 등 |
| **실행 시점** | 매 커밋 (CI) | 릴리스 전/정기적 (수동) |
| **마커** | `unit`, `e2e` | `chaos` |
| **기대 결과** | 정상 완료 | 장애 → 복구 → 최종 정상 |

---

## 6. 카오스 시나리오별 기대 이벤트 흐름

### C-CLI-01: Claude 타임아웃 → fallback

```
pipeline.created
  → task.submitted (lane=architect)
  → worker.started
  → worker.heartbeat (10s, 20s, ...)
  → task.failed (CLITimeoutError, retry 1/3)
  → task.retried (retry 2/3)
  → task.failed (retry 2/3)
  → task.retried (retry 3/3)
  → task.failed (retry 3/3, max reached)
  → fallback.triggered (from=claude, to=codex)
  → worker.heartbeat (codex 실행 중)
  → task.completed (codex 성공)
  → pipeline.completed
```

### C-NET-01: API 서버 재시작

```
[서버 1]
  pipeline.created → task.submitted → running
  [kill -SIGTERM]
  → engine.shutdown (워커 정리, checkpoint 저장)

[서버 2 - 재시작]
  engine.started
  → checkpoint 복원 (pipeline 상태 로딩)
  → orchestrator resume <task-id>
  → 미완료 태스크만 재실행
  → pipeline.completed
```
