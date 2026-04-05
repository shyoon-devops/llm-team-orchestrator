# WebSocket 프로토콜 명세

> v1.0 | 2026-04-05
> SPEC.md 기준 작성

---

## 1. 연결

### 1.1 URL

```
ws://localhost:9000/ws/events
```

프로덕션 환경에서는 리버스 프록시(nginx, Caddy)를 통해 `wss://` 사용을 권장한다.

### 1.2 핸드셰이크

표준 WebSocket 핸드셰이크를 사용한다. 추가 인증 헤더는 v1.0에서 사용하지 않는다 (v1.0 이후 JWT 토큰 지원 계획).

```
GET /ws/events HTTP/1.1
Host: localhost:9000
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Version: 13
Sec-WebSocket-Key: <random-key>
```

### 1.3 연결 성공 응답

연결 성공 시 서버가 즉시 `connection.established` 메시지를 전송한다:

```json
{
  "type": "connection.established",
  "timestamp": "2026-04-05T14:30:00.000Z",
  "payload": {
    "server_version": "0.1.0",
    "protocol_version": "1",
    "client_id": "ws-01JABC123DEF"
  }
}
```

### 1.4 Ping/Pong

서버는 **30초** 간격으로 WebSocket ping 프레임을 전송한다. 클라이언트가 pong을 **60초** 이내에 반환하지 않으면 서버가 연결을 종료한다.

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| Ping 간격 | 30초 | 서버 → 클라이언트 |
| Pong 타임아웃 | 60초 | 미응답 시 연결 종료 |

### 1.5 재연결 전략

클라이언트는 아래 **지수 백오프** 전략으로 재연결을 시도해야 한다:

| 재시도 | 대기 시간 | 설명 |
|--------|-----------|------|
| 1회 | 1초 | 즉시 재연결 시도 |
| 2회 | 2초 | |
| 3회 | 4초 | |
| 4회 | 8초 | |
| 5회 | 16초 | |
| 6회+ | 30초 | 최대 대기 시간 (cap) |

```
재연결 대기 = min(2^(attempt - 1), 30) 초
```

재연결 성공 시 재시도 카운터를 0으로 리셋한다. 재연결 후 놓친 이벤트는 REST API(`GET /api/events`)로 보충한다.

---

## 2. 메시지 포맷

### 2.1 서버 → 클라이언트 (이벤트)

모든 서버 → 클라이언트 메시지는 아래 공통 포맷을 따른다:

```json
{
  "type": "<event_type>",
  "timestamp": "<ISO 8601>",
  "payload": { ... }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `type` | `str` | **예** | 이벤트 타입 (dot notation: `pipeline.started`) |
| `timestamp` | `str` | **예** | ISO 8601 UTC (`2026-04-05T14:30:00.000Z`) |
| `payload` | `object` | **예** | 이벤트 데이터 (타입별 스키마) |

### 2.2 클라이언트 → 서버 (명령)

클라이언트가 서버에 전송하는 메시지:

```json
{
  "action": "<action_type>",
  "payload": { ... }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `action` | `str` | **예** | 클라이언트 액션 타입 |
| `payload` | `object` | **예** | 액션 데이터 |

---

## 3. 이벤트 타입 전체 목록

### 3.1 Pipeline 이벤트

#### `pipeline.started`

파이프라인 실행이 시작되었을 때 발생한다.

```json
{
  "type": "pipeline.started",
  "timestamp": "2026-04-05T14:30:00.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "task": "JWT 인증 미들웨어 구현",
    "team_preset": "feature-team",
    "target_repo": "/home/user/my-project",
    "agents": ["architect", "implementer"],
    "subtask_count": 3,
    "workflow": "dag"
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 고유 ID (ULID) |
| `task` | `str` | 원본 태스크 설명 |
| `team_preset` | `str \| null` | 사용된 팀 프리셋 이름 (자동 구성 시 `null`) |
| `target_repo` | `str \| null` | 대상 레포지토리 경로 |
| `agents` | `list[str]` | 참여 에이전트 이름 목록 |
| `subtask_count` | `int` | 서브태스크 수 |
| `workflow` | `str` | 워크플로우 유형 (`"parallel"`, `"sequential"`, `"dag"`) |

#### `pipeline.completed`

파이프라인이 성공적으로 완료되었을 때 발생한다.

```json
{
  "type": "pipeline.completed",
  "timestamp": "2026-04-05T14:35:00.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "task": "JWT 인증 미들웨어 구현",
    "duration_ms": 300000,
    "subtasks_completed": 3,
    "subtasks_total": 3,
    "synthesis_result": "## 종합 보고서\n..."
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 ID |
| `task` | `str` | 원본 태스크 설명 |
| `duration_ms` | `int` | 전체 실행 시간 (밀리초) |
| `subtasks_completed` | `int` | 완료된 서브태스크 수 |
| `subtasks_total` | `int` | 전체 서브태스크 수 |
| `synthesis_result` | `str` | Synthesizer 종합 결과 |

#### `pipeline.failed`

파이프라인이 실패했을 때 발생한다.

```json
{
  "type": "pipeline.failed",
  "timestamp": "2026-04-05T14:35:00.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "task": "JWT 인증 미들웨어 구현",
    "duration_ms": 180000,
    "error_type": "AllProvidersFailedError",
    "error_message": "모든 에이전트가 실패했습니다",
    "subtasks_completed": 1,
    "subtasks_failed": 2,
    "subtasks_total": 3,
    "failed_tasks": [
      {
        "task_id": "sub-002",
        "title": "인증 로직 구현",
        "error": "CLITimeoutError: 300초 초과"
      }
    ]
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 ID |
| `task` | `str` | 원본 태스크 설명 |
| `duration_ms` | `int` | 실행 시간 |
| `error_type` | `str` | 에러 클래스 이름 |
| `error_message` | `str` | 에러 메시지 |
| `subtasks_completed` | `int` | 완료된 서브태스크 수 |
| `subtasks_failed` | `int` | 실패한 서브태스크 수 |
| `subtasks_total` | `int` | 전체 서브태스크 수 |
| `failed_tasks` | `list[object]` | 실패한 태스크 상세 |

---

### 3.2 Task 이벤트

#### `task.submitted`

서브태스크가 TaskBoard에 투입되었을 때 발생한다.

```json
{
  "type": "task.submitted",
  "timestamp": "2026-04-05T14:30:01.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "task_id": "sub-001",
    "title": "API 설계",
    "lane": "architect",
    "state": "backlog",
    "depends_on": [],
    "priority": 0
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 소속 파이프라인 ID |
| `task_id` | `str` | 태스크 ID |
| `title` | `str` | 태스크 제목 |
| `lane` | `str` | 할당 레인 (에이전트 이름) |
| `state` | `str` | 초기 상태 (`"backlog"`) |
| `depends_on` | `list[str]` | 의존 태스크 ID 목록 |
| `priority` | `int` | 우선순위 (0 = 최고) |

#### `task.promoted`

태스크가 `backlog` → `todo`로 승격되었을 때 발생한다 (의존 태스크 완료 시 자동).

```json
{
  "type": "task.promoted",
  "timestamp": "2026-04-05T14:30:02.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "task_id": "sub-002",
    "title": "인증 로직 구현",
    "lane": "implementer",
    "previous_state": "backlog",
    "new_state": "todo",
    "reason": "dependency_satisfied",
    "resolved_dependencies": ["sub-001"]
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 ID |
| `task_id` | `str` | 태스크 ID |
| `title` | `str` | 태스크 제목 |
| `lane` | `str` | 할당 레인 |
| `previous_state` | `str` | 이전 상태 |
| `new_state` | `str` | 새 상태 (`"todo"`) |
| `reason` | `str` | 승격 사유 (`"dependency_satisfied"`, `"manual"`) |
| `resolved_dependencies` | `list[str]` | 완료된 의존 태스크 ID |

#### `task.claimed`

Worker가 태스크를 가져갔을 때 (`todo` → `in_progress`) 발생한다.

```json
{
  "type": "task.claimed",
  "timestamp": "2026-04-05T14:30:05.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "task_id": "sub-001",
    "title": "API 설계",
    "lane": "architect",
    "assigned_to": "architect-worker-1",
    "executor_type": "cli",
    "cli_tool": "claude"
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 ID |
| `task_id` | `str` | 태스크 ID |
| `title` | `str` | 태스크 제목 |
| `lane` | `str` | 레인 |
| `assigned_to` | `str` | Worker 인스턴스 이름 |
| `executor_type` | `str` | 실행기 유형 (`"cli"`, `"mcp"`) |
| `cli_tool` | `str \| null` | CLI 도구 이름 (MCP 시 `null`) |

#### `task.completed`

태스크가 성공적으로 완료되었을 때 (`in_progress` → `done`) 발생한다.

```json
{
  "type": "task.completed",
  "timestamp": "2026-04-05T14:32:00.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "task_id": "sub-001",
    "title": "API 설계",
    "lane": "architect",
    "assigned_to": "architect-worker-1",
    "duration_ms": 115000,
    "output_length": 4500,
    "output_preview": "## API 설계\n\n### 1. 엔드포인트 설계\n..."
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 ID |
| `task_id` | `str` | 태스크 ID |
| `title` | `str` | 태스크 제목 |
| `lane` | `str` | 레인 |
| `assigned_to` | `str` | Worker 이름 |
| `duration_ms` | `int` | 실행 시간 (밀리초) |
| `output_length` | `int` | 출력 문자 수 |
| `output_preview` | `str` | 출력 앞 500자 미리보기 |

#### `task.failed`

태스크 실행이 실패했을 때 (`in_progress` → `failed`) 발생한다. 재시도 횟수를 모두 소진한 경우.

```json
{
  "type": "task.failed",
  "timestamp": "2026-04-05T14:35:00.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "task_id": "sub-002",
    "title": "인증 로직 구현",
    "lane": "implementer",
    "assigned_to": "implementer-worker-1",
    "duration_ms": 300000,
    "error_type": "CLITimeoutError",
    "error_message": "CLI 실행이 300초를 초과했습니다",
    "retry_count": 3,
    "max_retries": 3,
    "is_final": true
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 ID |
| `task_id` | `str` | 태스크 ID |
| `title` | `str` | 태스크 제목 |
| `lane` | `str` | 레인 |
| `assigned_to` | `str` | Worker 이름 |
| `duration_ms` | `int` | 실행 시간 |
| `error_type` | `str` | 에러 클래스 이름 |
| `error_message` | `str` | 에러 메시지 |
| `retry_count` | `int` | 재시도 횟수 |
| `max_retries` | `int` | 최대 재시도 횟수 |
| `is_final` | `bool` | 최종 실패 여부 (`true`면 더 이상 재시도 안 함) |

#### `task.retried`

태스크가 재시도될 때 (`failed` → `todo`) 발생한다.

```json
{
  "type": "task.retried",
  "timestamp": "2026-04-05T14:33:00.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "task_id": "sub-002",
    "title": "인증 로직 구현",
    "lane": "implementer",
    "retry_count": 2,
    "max_retries": 3,
    "previous_error": "CLIExecutionError: exit code 1",
    "fallback_cli": null
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 ID |
| `task_id` | `str` | 태스크 ID |
| `title` | `str` | 태스크 제목 |
| `lane` | `str` | 레인 |
| `retry_count` | `int` | 현재 재시도 횟수 |
| `max_retries` | `int` | 최대 재시도 횟수 |
| `previous_error` | `str` | 이전 실패 에러 메시지 |
| `fallback_cli` | `str \| null` | 폴백 CLI 사용 시 이름 |

---

### 3.3 Worker 이벤트

#### `worker.started`

AgentWorker가 시작되었을 때 발생한다.

```json
{
  "type": "worker.started",
  "timestamp": "2026-04-05T14:30:00.000Z",
  "payload": {
    "worker_id": "architect-worker-1",
    "lane": "architect",
    "agent_preset": "architect",
    "executor_type": "cli",
    "cli_tool": "claude"
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `worker_id` | `str` | Worker 인스턴스 ID |
| `lane` | `str` | 담당 레인 |
| `agent_preset` | `str` | 에이전트 프리셋 이름 |
| `executor_type` | `str` | 실행기 유형 |
| `cli_tool` | `str \| null` | CLI 도구 이름 |

#### `worker.stopped`

AgentWorker가 종료되었을 때 발생한다.

```json
{
  "type": "worker.stopped",
  "timestamp": "2026-04-05T14:40:00.000Z",
  "payload": {
    "worker_id": "architect-worker-1",
    "lane": "architect",
    "reason": "shutdown",
    "tasks_processed": 5,
    "tasks_failed": 1,
    "uptime_ms": 600000
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `worker_id` | `str` | Worker 인스턴스 ID |
| `lane` | `str` | 담당 레인 |
| `reason` | `str` | 종료 사유 (`"shutdown"`, `"error"`, `"idle_timeout"`) |
| `tasks_processed` | `int` | 처리한 태스크 수 |
| `tasks_failed` | `int` | 실패한 태스크 수 |
| `uptime_ms` | `int` | 가동 시간 (밀리초) |

---

### 3.4 Agent Health 이벤트

#### `agent.health_check`

에이전트 헬스 체크 결과가 변경되었을 때 발생한다 (available ↔ unavailable).

```json
{
  "type": "agent.health_check",
  "timestamp": "2026-04-05T14:31:00.000Z",
  "payload": {
    "agent_name": "gemini",
    "executor_type": "cli",
    "previous_status": "available",
    "current_status": "unavailable",
    "error": "CLI not found in PATH",
    "check_duration_ms": 150
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `agent_name` | `str` | 에이전트 이름 |
| `executor_type` | `str` | 실행기 유형 |
| `previous_status` | `str` | 이전 상태 (`"available"`, `"unavailable"`, `"unknown"`) |
| `current_status` | `str` | 현재 상태 |
| `error` | `str \| null` | 에러 메시지 (unavailable 시) |
| `check_duration_ms` | `int` | 체크 소요 시간 |

> **참고:** 상태 변경이 없으면 이 이벤트를 전송하지 않는다. 주기적 헬스 체크 결과는 REST API(`GET /api/health`)로 확인한다.

---

### 3.5 Synthesis 이벤트

#### `synthesis.started`

Synthesizer가 결과 종합을 시작했을 때 발생한다.

```json
{
  "type": "synthesis.started",
  "timestamp": "2026-04-05T14:34:00.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "strategy": "structured",
    "input_count": 3,
    "model": "claude-sonnet-4-20250514"
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 ID |
| `strategy` | `str` | 종합 전략 (`"narrative"`, `"structured"`, `"checklist"`) |
| `input_count` | `int` | 입력 결과 수 |
| `model` | `str` | 사용 LLM 모델 |

#### `synthesis.completed`

Synthesizer가 결과 종합을 완료했을 때 발생한다.

```json
{
  "type": "synthesis.completed",
  "timestamp": "2026-04-05T14:34:30.000Z",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "strategy": "structured",
    "duration_ms": 30000,
    "output_length": 3500,
    "output_preview": "## 종합 보고서\n\n### 1. 요약\n..."
  }
}
```

| Payload 필드 | 타입 | 설명 |
|-------------|------|------|
| `pipeline_id` | `str` | 파이프라인 ID |
| `strategy` | `str` | 종합 전략 |
| `duration_ms` | `int` | 소요 시간 (밀리초) |
| `output_length` | `int` | 출력 문자 수 |
| `output_preview` | `str` | 출력 앞 500자 미리보기 |

---

### 3.6 Connection 이벤트

#### `connection.established`

WebSocket 연결 성공 시 서버가 전송한다 (섹션 1.3 참조).

#### `connection.shutdown`

서버 종료 시 모든 클라이언트에 전송한다.

```json
{
  "type": "connection.shutdown",
  "timestamp": "2026-04-05T15:00:00.000Z",
  "payload": {
    "reason": "server_shutdown",
    "message": "서버가 종료됩니다. 재연결을 시도하세요."
  }
}
```

#### `connection.error`

서버 측 에러 발생 시 클라이언트에 전송한다.

```json
{
  "type": "connection.error",
  "timestamp": "2026-04-05T14:31:00.000Z",
  "payload": {
    "code": "INVALID_ACTION",
    "message": "알 수 없는 action: 'subscribe_all'"
  }
}
```

---

### 3.7 이벤트 타입 요약 테이블

| 이벤트 타입 | 방향 | 발생 조건 |
|-------------|------|-----------|
| `connection.established` | S→C | WebSocket 연결 성공 |
| `connection.shutdown` | S→C | 서버 종료 |
| `connection.error` | S→C | 클라이언트 요청 에러 |
| `pipeline.started` | S→C | 파이프라인 실행 시작 |
| `pipeline.completed` | S→C | 파이프라인 성공 완료 |
| `pipeline.failed` | S→C | 파이프라인 실패 |
| `task.submitted` | S→C | 서브태스크 보드 투입 |
| `task.promoted` | S→C | 태스크 backlog→todo 승격 |
| `task.claimed` | S→C | Worker가 태스크 가져감 |
| `task.completed` | S→C | 태스크 성공 완료 |
| `task.failed` | S→C | 태스크 실패 (최종) |
| `task.retried` | S→C | 태스크 재시도 |
| `worker.started` | S→C | Worker 시작 |
| `worker.stopped` | S→C | Worker 종료 |
| `agent.health_check` | S→C | 에이전트 상태 변경 |
| `synthesis.started` | S→C | Synthesizer 시작 |
| `synthesis.completed` | S→C | Synthesizer 완료 |

---

## 4. 클라이언트 구독

### 4.1 구독 필터

클라이언트는 연결 후 `subscribe` 액션으로 관심 있는 이벤트만 수신할 수 있다.

#### 전체 이벤트 구독 (기본)

연결 시 기본적으로 **모든 이벤트**를 수신한다. 별도 구독 요청 불필요.

#### Pipeline ID별 필터링

```json
{
  "action": "subscribe",
  "payload": {
    "pipeline_id": "01JABC123DEF"
  }
}
```

서버 응답:

```json
{
  "type": "subscription.confirmed",
  "timestamp": "2026-04-05T14:30:00.500Z",
  "payload": {
    "filter": {
      "pipeline_id": "01JABC123DEF"
    },
    "message": "해당 파이프라인 이벤트만 수신합니다"
  }
}
```

이후 `pipeline_id`가 `01JABC123DEF`인 이벤트만 수신한다. (connection 이벤트는 항상 수신)

#### 이벤트 타입별 필터링

```json
{
  "action": "subscribe",
  "payload": {
    "event_types": ["pipeline.started", "pipeline.completed", "pipeline.failed"]
  }
}
```

#### 복합 필터

```json
{
  "action": "subscribe",
  "payload": {
    "pipeline_id": "01JABC123DEF",
    "event_types": ["task.completed", "task.failed"]
  }
}
```

#### 구독 해제 (전체 수신 복원)

```json
{
  "action": "unsubscribe",
  "payload": {}
}
```

### 4.2 클라이언트 액션 전체 목록

| Action | Payload | 설명 |
|--------|---------|------|
| `subscribe` | `{ pipeline_id?, event_types? }` | 이벤트 필터 설정 |
| `unsubscribe` | `{}` | 필터 해제 (전체 수신) |
| `ping` | `{}` | 애플리케이션 레벨 ping (WebSocket ping과 별도) |

### 4.3 서버 응답 (클라이언트 액션에 대한)

| 응답 타입 | 발생 조건 |
|-----------|-----------|
| `subscription.confirmed` | `subscribe` 성공 |
| `subscription.cleared` | `unsubscribe` 성공 |
| `pong` | `ping` 응답 |
| `connection.error` | 잘못된 action 또는 payload |

---

## 5. 에러 처리

### 5.1 연결 끊김

| 상황 | 서버 동작 | 클라이언트 동작 |
|------|-----------|-----------------|
| 클라이언트 정상 종료 | 구독 해제, 리소스 정리 | close 프레임 전송 |
| 클라이언트 비정상 종료 | pong 타임아웃 후 정리 | 재연결 시도 |
| 네트워크 단절 | pong 타임아웃 후 정리 | 재연결 시도 (지수 백오프) |

### 5.2 서버 재시작

서버가 재시작되면:

1. 모든 WebSocket 연결이 끊어진다
2. 클라이언트는 재연결을 시도한다
3. 재연결 성공 시 새 `connection.established` 수신
4. 놓친 이벤트는 REST API로 보충:

```
GET /api/events?since=2026-04-05T14:30:00Z&pipeline_id=01JABC123DEF
```

### 5.3 메시지 파싱 에러

서버가 클라이언트 메시지를 파싱할 수 없을 때:

```json
{
  "type": "connection.error",
  "timestamp": "2026-04-05T14:30:01.000Z",
  "payload": {
    "code": "PARSE_ERROR",
    "message": "Invalid JSON: Expecting ',' delimiter"
  }
}
```

### 5.4 에러 코드

| 코드 | 설명 |
|------|------|
| `PARSE_ERROR` | JSON 파싱 실패 |
| `INVALID_ACTION` | 알 수 없는 action 타입 |
| `INVALID_PAYLOAD` | payload 스키마 불일치 |
| `PIPELINE_NOT_FOUND` | 존재하지 않는 pipeline_id |
| `INTERNAL_ERROR` | 서버 내부 에러 |

### 5.5 WebSocket Close 코드

| Close Code | 의미 | 재연결 |
|------------|------|--------|
| `1000` | 정상 종료 | 불필요 |
| `1001` | Going Away (서버 종료) | 재연결 시도 |
| `1006` | 비정상 종료 | 재연결 시도 |
| `1011` | 서버 에러 | 재연결 시도 (백오프) |
| `1012` | 서버 재시작 | 즉시 재연결 |
| `4000` | 인증 실패 (v1.0 이후) | 인증 후 재연결 |

---

## 6. 프론트엔드 통합

### 6.1 React `useWebSocket` Hook 스펙

```typescript
// types.ts
interface WebSocketEvent {
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

interface UseWebSocketOptions {
  url: string;
  pipelineId?: string;
  eventTypes?: string[];
  onEvent?: (event: WebSocketEvent) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnect?: boolean;
  reconnectMaxRetries?: number;
}

interface UseWebSocketReturn {
  connected: boolean;
  lastEvent: WebSocketEvent | null;
  events: WebSocketEvent[];
  subscribe: (filter: { pipelineId?: string; eventTypes?: string[] }) => void;
  unsubscribe: () => void;
  send: (action: string, payload: Record<string, unknown>) => void;
}
```

### 6.2 Hook 구현 사양

```typescript
// useWebSocket.ts
import { useCallback, useEffect, useRef, useState } from "react";

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    pipelineId,
    eventTypes,
    onEvent,
    onConnect,
    onDisconnect,
    onError,
    reconnect = true,
    reconnectMaxRetries = 10,
  } = options;

  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WebSocketEvent | null>(null);
  const [events, setEvents] = useState<WebSocketEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<NodeJS.Timeout>();

  // 연결 로직
  const connect = useCallback(() => {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setConnected(true);
      retryCountRef.current = 0;
      onConnect?.();

      // 초기 구독 설정
      if (pipelineId || eventTypes) {
        ws.send(
          JSON.stringify({
            action: "subscribe",
            payload: {
              ...(pipelineId && { pipeline_id: pipelineId }),
              ...(eventTypes && { event_types: eventTypes }),
            },
          })
        );
      }
    };

    ws.onmessage = (msgEvent) => {
      const event: WebSocketEvent = JSON.parse(msgEvent.data);
      setLastEvent(event);
      setEvents((prev) => [...prev, event]);
      onEvent?.(event);
    };

    ws.onclose = () => {
      setConnected(false);
      onDisconnect?.();

      // 재연결
      if (reconnect && retryCountRef.current < reconnectMaxRetries) {
        const delay = Math.min(
          Math.pow(2, retryCountRef.current) * 1000,
          30000
        );
        retryCountRef.current += 1;
        retryTimerRef.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = (err) => {
      onError?.(err);
    };

    wsRef.current = ws;
  }, [url, pipelineId, eventTypes, reconnect, reconnectMaxRetries]);

  // 구독 변경
  const subscribe = useCallback(
    (filter: { pipelineId?: string; eventTypes?: string[] }) => {
      wsRef.current?.send(
        JSON.stringify({
          action: "subscribe",
          payload: {
            ...(filter.pipelineId && { pipeline_id: filter.pipelineId }),
            ...(filter.eventTypes && { event_types: filter.eventTypes }),
          },
        })
      );
    },
    []
  );

  const unsubscribe = useCallback(() => {
    wsRef.current?.send(
      JSON.stringify({ action: "unsubscribe", payload: {} })
    );
  }, []);

  const send = useCallback(
    (action: string, payload: Record<string, unknown>) => {
      wsRef.current?.send(JSON.stringify({ action, payload }));
    },
    []
  );

  // 라이프사이클
  useEffect(() => {
    connect();
    return () => {
      clearTimeout(retryTimerRef.current);
      wsRef.current?.close(1000);
    };
  }, [connect]);

  return { connected, lastEvent, events, subscribe, unsubscribe, send };
}
```

### 6.3 사용 예시

```typescript
// PipelineView.tsx
import { useWebSocket } from "./hooks/useWebSocket";

function PipelineView({ pipelineId }: { pipelineId: string }) {
  const { connected, events } = useWebSocket({
    url: "ws://localhost:9000/ws/events",
    pipelineId,
    eventTypes: [
      "task.submitted",
      "task.claimed",
      "task.completed",
      "task.failed",
      "pipeline.completed",
      "pipeline.failed",
    ],
    onEvent: (event) => {
      if (event.type === "pipeline.completed") {
        showNotification("파이프라인 완료!");
      }
    },
  });

  return (
    <div>
      <StatusBadge connected={connected} />
      <EventTimeline events={events} />
    </div>
  );
}
```

### 6.4 칸반 보드 실시간 업데이트

```typescript
// KanbanBoard.tsx
function KanbanBoard({ pipelineId }: { pipelineId: string }) {
  const [board, setBoard] = useState<BoardState>(initialBoard);

  useWebSocket({
    url: "ws://localhost:9000/ws/events",
    pipelineId,
    eventTypes: [
      "task.submitted",
      "task.promoted",
      "task.claimed",
      "task.completed",
      "task.failed",
      "task.retried",
    ],
    onEvent: (event) => {
      switch (event.type) {
        case "task.submitted":
          setBoard((prev) => addTask(prev, event.payload, "backlog"));
          break;
        case "task.promoted":
          setBoard((prev) =>
            moveTask(prev, event.payload.task_id, "todo")
          );
          break;
        case "task.claimed":
          setBoard((prev) =>
            moveTask(prev, event.payload.task_id, "in_progress")
          );
          break;
        case "task.completed":
          setBoard((prev) =>
            moveTask(prev, event.payload.task_id, "done")
          );
          break;
        case "task.failed":
          setBoard((prev) =>
            moveTask(prev, event.payload.task_id, "failed")
          );
          break;
        case "task.retried":
          setBoard((prev) =>
            moveTask(prev, event.payload.task_id, "todo")
          );
          break;
      }
    },
  });

  return (
    <div className="kanban-board">
      <Column title="Backlog" tasks={board.backlog} />
      <Column title="Todo" tasks={board.todo} />
      <Column title="In Progress" tasks={board.in_progress} />
      <Column title="Done" tasks={board.done} />
      <Column title="Failed" tasks={board.failed} />
    </div>
  );
}
```
