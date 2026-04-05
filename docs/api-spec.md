# API 명세서

> v1.0 | 2026-04-05
> 기반: `docs/SPEC.md` v2.0

---

## 목차

1. [개요](#1-개요)
2. [공통 규칙](#2-공통-규칙)
3. [태스크 API](#3-태스크-api)
4. [칸반 보드 API](#4-칸반-보드-api)
5. [에이전트 API](#5-에이전트-api)
6. [프리셋 API](#6-프리셋-api)
7. [아티팩트 API](#7-아티팩트-api)
8. [이벤트 API](#8-이벤트-api)
9. [헬스 체크 API](#9-헬스-체크-api)
10. [WebSocket 프로토콜](#10-websocket-프로토콜)

---

## 1. 개요

### Base URL

```
http://localhost:8000
```

### Content-Type

모든 요청/응답은 `application/json`. 예외: WebSocket (`ws://`), 아티팩트 파일 다운로드 (`application/octet-stream`).

### 인증

v1.0에서는 인증 없음. 모든 엔드포인트는 인증 없이 접근 가능.

> **향후 계획 (v2.0):** Bearer token 기반 인증 추가 예정. `Authorization: Bearer <token>` 헤더 사용. 인증 미통과 시 `401 Unauthorized` 반환.

### Rate Limiting

v1.0에서는 rate limiting 없음.

> **향후 계획 (v2.0):** IP 기반 rate limiting 추가 예정. 제한 초과 시 `429 Too Many Requests` 반환. 응답 헤더에 `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` 포함.

### 페이지네이션

목록 엔드포인트는 `offset`/`limit` 쿼리 파라미터로 페이지네이션.

| 파라미터 | 타입 | 기본값 | 범위 | 설명 |
|----------|------|--------|------|------|
| `offset` | integer | `0` | 0 ~ 10000 | 건너뛸 항목 수 |
| `limit` | integer | `20` | 1 ~ 100 | 반환할 최대 항목 수 |

페이지네이션 응답 공통 형식:

```json
{
  "items": [],
  "total": 42,
  "offset": 0,
  "limit": 20
}
```

---

## 2. 공통 규칙

### 공통 에러 응답 형식

모든 에러 응답은 동일한 JSON 구조를 따른다.

```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "태스크를 찾을 수 없습니다: task-abc123",
    "details": {}
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `error.code` | string | 고유 에러 코드 (상수) |
| `error.message` | string | 사용자 표시용 메시지 (한국어) |
| `error.details` | object | 추가 정보 (선택, 에러별 상이) |

### 공통 HTTP 상태 코드

| 코드 | 의미 | 사용 시점 |
|------|------|----------|
| `200` | OK | 조회/업데이트 성공 |
| `201` | Created | 리소스 생성 성공 |
| `204` | No Content | 삭제 성공 (응답 본문 없음) |
| `400` | Bad Request | 요청 본문 유효성 실패 |
| `404` | Not Found | 리소스 없음 |
| `409` | Conflict | 상태 충돌 (예: 이미 완료된 태스크 resume) |
| `422` | Unprocessable Entity | 요청 구조는 올바르나 비즈니스 규칙 위반 |
| `500` | Internal Server Error | 서버 내부 오류 |

### 타임스탬프 형식

모든 타임스탬프는 ISO 8601 형식 (UTC).

```
2026-04-05T14:30:00Z
```

### ID 형식

모든 ID는 UUID v4 문자열.

```
"550e8400-e29b-41d4-a716-446655440000"
```

---

## 3. 태스크 API

### POST /api/tasks — 태스크 제출

새로운 태스크를 제출하여 파이프라인을 시작한다. 오케스트레이터가 태스크를 분해하고, 팀을 구성하며, 칸반 보드에 서브태스크를 투입한다.

**Request Body:**

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `task` | string | **필수** | — | 수행할 태스크 설명 (자연어) |
| `team_preset` | string \| null | 선택 | `null` | 팀 프리셋 이름. `null`이면 오케스트레이터가 자동 구성 |
| `target_repo` | string \| null | 선택 | `null` | 작업 대상 Git 저장소 절대 경로. `null`이면 코드 변경 없는 분석 태스크로 간주 |
| `config` | object \| null | 선택 | `null` | 파이프라인 실행 설정 오버라이드 |
| `config.timeout` | integer | 선택 | `600` | 전체 파이프라인 타임아웃 (초). 범위: 30 ~ 3600 |
| `config.max_retries` | integer | 선택 | `3` | 서브태스크 최대 재시도 횟수. 범위: 0 ~ 10 |
| `config.synthesis_strategy` | string | 선택 | `"narrative"` | 결과 종합 전략. `"narrative"` \| `"structured"` \| `"checklist"` |
| `config.cli_priority` | array\<string\> | 선택 | `["claude", "codex", "gemini"]` | CLI 폴백 우선순위 |

**Request Body JSON Schema:**

```json
{
  "type": "object",
  "required": ["task"],
  "properties": {
    "task": {
      "type": "string",
      "minLength": 1,
      "maxLength": 10000,
      "description": "수행할 태스크 설명"
    },
    "team_preset": {
      "type": ["string", "null"],
      "description": "팀 프리셋 이름"
    },
    "target_repo": {
      "type": ["string", "null"],
      "description": "Git 저장소 절대 경로"
    },
    "config": {
      "type": ["object", "null"],
      "properties": {
        "timeout": {
          "type": "integer",
          "minimum": 30,
          "maximum": 3600,
          "default": 600
        },
        "max_retries": {
          "type": "integer",
          "minimum": 0,
          "maximum": 10,
          "default": 3
        },
        "synthesis_strategy": {
          "type": "string",
          "enum": ["narrative", "structured", "checklist"],
          "default": "narrative"
        },
        "cli_priority": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["claude", "codex", "gemini"]
          },
          "default": ["claude", "codex", "gemini"]
        }
      }
    }
  }
}
```

**Response (201 Created):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task": "JWT 인증 미들웨어 구현",
  "status": "planning",
  "team_preset": "feature-team",
  "target_repo": "/home/user/my-project",
  "config": {
    "timeout": 600,
    "max_retries": 3,
    "synthesis_strategy": "narrative",
    "cli_priority": ["claude", "codex", "gemini"]
  },
  "subtasks": [],
  "result": null,
  "created_at": "2026-04-05T14:30:00Z",
  "updated_at": "2026-04-05T14:30:00Z"
}
```

**Response Body — Pipeline 스키마:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string (UUID) | 파이프라인 고유 ID |
| `task` | string | 원본 태스크 설명 |
| `status` | string | 파이프라인 상태. `"planning"` \| `"running"` \| `"paused"` \| `"completed"` \| `"failed"` \| `"cancelled"` |
| `team_preset` | string \| null | 사용된 팀 프리셋 이름 |
| `target_repo` | string \| null | 작업 대상 저장소 경로 |
| `config` | object | 적용된 실행 설정 |
| `subtasks` | array\<SubTask\> | 분해된 서브태스크 목록 |
| `result` | string \| null | 최종 종합 결과 (완료 시에만) |
| `created_at` | string (ISO 8601) | 생성 시각 |
| `updated_at` | string (ISO 8601) | 마지막 업데이트 시각 |

**SubTask 스키마:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string (UUID) | 서브태스크 ID |
| `title` | string | 서브태스크 제목 |
| `lane` | string | 칸반 레인 이름 (에이전트 역할) |
| `state` | string | `"backlog"` \| `"todo"` \| `"in_progress"` \| `"done"` \| `"failed"` |
| `depends_on` | array\<string\> | 의존하는 서브태스크 ID 목록 |
| `assigned_to` | string \| null | 할당된 에이전트 이름 |
| `result` | string | 실행 결과 (빈 문자열이면 미완료) |
| `retry_count` | integer | 현재까지 재시도 횟수 |
| `max_retries` | integer | 최대 재시도 횟수 |
| `pipeline_id` | string | 소속 파이프라인 ID |

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `VALIDATION_ERROR` | 400 | `task`가 빈 문자열이거나 누락 |
| `PRESET_NOT_FOUND` | 404 | `team_preset`에 지정된 프리셋이 존재하지 않음 |
| `REPO_NOT_FOUND` | 404 | `target_repo` 경로가 유효한 Git 저장소가 아님 |
| `DECOMPOSITION_FAILED` | 500 | LLM 기반 태스크 분해 실패 |

**예시:**

```bash
# 팀 프리셋 지정
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task": "JWT 인증 미들웨어 구현",
    "team_preset": "feature-team",
    "target_repo": "/home/user/my-project"
  }'
```

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task": "JWT 인증 미들웨어 구현",
  "status": "planning",
  "team_preset": "feature-team",
  "target_repo": "/home/user/my-project",
  "config": {
    "timeout": 600,
    "max_retries": 3,
    "synthesis_strategy": "narrative",
    "cli_priority": ["claude", "codex", "gemini"]
  },
  "subtasks": [],
  "result": null,
  "created_at": "2026-04-05T14:30:00Z",
  "updated_at": "2026-04-05T14:30:00Z"
}
```

```bash
# 자동 팀 구성 + 커스텀 설정
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task": "프로덕션 API 500 에러 원인 분석",
    "config": {
      "timeout": 1800,
      "synthesis_strategy": "structured",
      "cli_priority": ["claude", "gemini"]
    }
  }'
```

```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "task": "프로덕션 API 500 에러 원인 분석",
  "status": "planning",
  "team_preset": null,
  "target_repo": null,
  "config": {
    "timeout": 1800,
    "max_retries": 3,
    "synthesis_strategy": "structured",
    "cli_priority": ["claude", "gemini"]
  },
  "subtasks": [],
  "result": null,
  "created_at": "2026-04-05T14:31:00Z",
  "updated_at": "2026-04-05T14:31:00Z"
}
```

---

### GET /api/tasks — 파이프라인 목록 조회

모든 파이프라인을 최신순으로 조회한다. 페이지네이션 지원.

**Query Parameters:**

| 파라미터 | 타입 | 기본값 | 범위 | 설명 |
|----------|------|--------|------|------|
| `offset` | integer | `0` | 0 ~ 10000 | 건너뛸 항목 수 |
| `limit` | integer | `20` | 1 ~ 100 | 반환할 최대 항목 수 |
| `status` | string | — | `planning` \| `running` \| `paused` \| `completed` \| `failed` \| `cancelled` | 상태 필터 (선택) |

**Response (200 OK):**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "task": "JWT 인증 미들웨어 구현",
      "status": "running",
      "team_preset": "feature-team",
      "target_repo": "/home/user/my-project",
      "config": {
        "timeout": 600,
        "max_retries": 3,
        "synthesis_strategy": "narrative",
        "cli_priority": ["claude", "codex", "gemini"]
      },
      "subtasks": [
        {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "title": "JWT 토큰 생성/검증 모듈 구현",
          "lane": "implementer",
          "state": "in_progress",
          "depends_on": [],
          "assigned_to": "claude-implementer",
          "result": "",
          "retry_count": 0,
          "max_retries": 3,
          "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
        }
      ],
      "result": null,
      "created_at": "2026-04-05T14:30:00Z",
      "updated_at": "2026-04-05T14:30:05Z"
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 20
}
```

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `VALIDATION_ERROR` | 400 | `offset` 또는 `limit` 범위 초과 |

**예시:**

```bash
# 기본 조회
curl http://localhost:8000/api/tasks

# 페이지네이션 + 상태 필터
curl "http://localhost:8000/api/tasks?offset=0&limit=10&status=running"
```

---

### GET /api/tasks/{id} — 파이프라인 상세 조회

특정 파이프라인의 상세 정보를 조회한다. 서브태스크 목록, 결과, 설정 등 전체 정보 포함.

**Path Parameters:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `id` | string (UUID) | 파이프라인 ID |

**Response (200 OK):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task": "JWT 인증 미들웨어 구현",
  "status": "completed",
  "team_preset": "feature-team",
  "target_repo": "/home/user/my-project",
  "config": {
    "timeout": 600,
    "max_retries": 3,
    "synthesis_strategy": "narrative",
    "cli_priority": ["claude", "codex", "gemini"]
  },
  "subtasks": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "JWT 토큰 생성/검증 모듈 구현",
      "lane": "implementer",
      "state": "done",
      "depends_on": [],
      "assigned_to": "claude-implementer",
      "result": "src/middleware/jwt.py 생성 완료. PyJWT 기반 토큰 생성/검증 구현.",
      "retry_count": 0,
      "max_retries": 3,
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "title": "미들웨어 통합 및 라우터 적용",
      "lane": "implementer",
      "state": "done",
      "depends_on": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
      "assigned_to": "codex-implementer",
      "result": "src/middleware/auth.py에 미들웨어 클래스 구현. 라우터 데코레이터 적용.",
      "retry_count": 0,
      "max_retries": 3,
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    {
      "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "title": "코드 리뷰 및 보안 검증",
      "lane": "reviewer",
      "state": "done",
      "depends_on": [
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "b2c3d4e5-f6a7-8901-bcde-f12345678901"
      ],
      "assigned_to": "gemini-reviewer",
      "result": "보안 이슈 없음. 토큰 만료 처리 정상. 타입 힌트 추가 권장.",
      "retry_count": 0,
      "max_retries": 3,
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  ],
  "result": "## JWT 인증 미들웨어 구현 완료\n\n### 구현 내용\n- PyJWT 기반 토큰 생성/검증 모듈\n- FastAPI 미들웨어 클래스\n- 라우터 데코레이터 적용\n\n### 리뷰 결과\n보안 이슈 없음. 타입 힌트 추가 권장.",
  "created_at": "2026-04-05T14:30:00Z",
  "updated_at": "2026-04-05T14:35:00Z"
}
```

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `TASK_NOT_FOUND` | 404 | 해당 ID의 파이프라인이 존재하지 않음 |

**예시:**

```bash
curl http://localhost:8000/api/tasks/550e8400-e29b-41d4-a716-446655440000
```

---

### POST /api/tasks/{id}/resume — 중단 태스크 재개

`paused` 또는 `failed` 상태의 파이프라인을 재개한다. 체크포인트에서 이어서 실행.

**Path Parameters:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `id` | string (UUID) | 파이프라인 ID |

**Request Body:** 없음

**Response (200 OK):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task": "JWT 인증 미들웨어 구현",
  "status": "running",
  "team_preset": "feature-team",
  "target_repo": "/home/user/my-project",
  "config": {
    "timeout": 600,
    "max_retries": 3,
    "synthesis_strategy": "narrative",
    "cli_priority": ["claude", "codex", "gemini"]
  },
  "subtasks": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "JWT 토큰 생성/검증 모듈 구현",
      "lane": "implementer",
      "state": "done",
      "depends_on": [],
      "assigned_to": "claude-implementer",
      "result": "src/middleware/jwt.py 생성 완료.",
      "retry_count": 0,
      "max_retries": 3,
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "title": "미들웨어 통합 및 라우터 적용",
      "lane": "implementer",
      "state": "todo",
      "depends_on": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
      "assigned_to": null,
      "result": "",
      "retry_count": 1,
      "max_retries": 3,
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  ],
  "result": null,
  "created_at": "2026-04-05T14:30:00Z",
  "updated_at": "2026-04-05T14:40:00Z"
}
```

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `TASK_NOT_FOUND` | 404 | 해당 ID의 파이프라인이 존재하지 않음 |
| `TASK_NOT_RESUMABLE` | 409 | 파이프라인 상태가 `paused` 또는 `failed`가 아님 |

**예시:**

```bash
curl -X POST http://localhost:8000/api/tasks/550e8400-e29b-41d4-a716-446655440000/resume
```

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task": "JWT 인증 미들웨어 구현",
  "status": "running",
  "team_preset": "feature-team",
  "target_repo": "/home/user/my-project",
  "config": {
    "timeout": 600,
    "max_retries": 3,
    "synthesis_strategy": "narrative",
    "cli_priority": ["claude", "codex", "gemini"]
  },
  "subtasks": [],
  "result": null,
  "created_at": "2026-04-05T14:30:00Z",
  "updated_at": "2026-04-05T14:40:00Z"
}
```

---

### DELETE /api/tasks/{id} — 태스크 취소

실행 중인 파이프라인을 취소한다. 진행 중인 서브프로세스를 종료하고 worktree를 정리한다.

**Path Parameters:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `id` | string (UUID) | 파이프라인 ID |

**Request Body:** 없음

**Response (204 No Content):** 응답 본문 없음.

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `TASK_NOT_FOUND` | 404 | 해당 ID의 파이프라인이 존재하지 않음 |
| `TASK_ALREADY_TERMINAL` | 409 | 파이프라인이 이미 `completed` 또는 `cancelled` 상태 |

**예시:**

```bash
curl -X DELETE http://localhost:8000/api/tasks/550e8400-e29b-41d4-a716-446655440000
# 응답: 204 No Content
```

에러 시:

```bash
curl -X DELETE http://localhost:8000/api/tasks/nonexistent-id
```

```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "태스크를 찾을 수 없습니다: nonexistent-id",
    "details": {}
  }
}
```

---

## 4. 칸반 보드 API

### GET /api/board — 칸반 보드 전체 상태

모든 레인과 각 레인의 태스크를 칸반 보드 형태로 반환한다.

**Response (200 OK):**

```json
{
  "lanes": {
    "architect": {
      "name": "architect",
      "agent": "claude-architect",
      "tasks": {
        "backlog": [],
        "todo": [],
        "in_progress": [
          {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "title": "시스템 아키텍처 설계",
            "state": "in_progress",
            "depends_on": [],
            "assigned_to": "claude-architect",
            "result": "",
            "retry_count": 0,
            "max_retries": 3,
            "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
          }
        ],
        "done": [],
        "failed": []
      }
    },
    "implementer": {
      "name": "implementer",
      "agent": "codex-implementer",
      "tasks": {
        "backlog": [],
        "todo": [
          {
            "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "title": "JWT 토큰 모듈 구현",
            "state": "todo",
            "depends_on": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
            "assigned_to": null,
            "result": "",
            "retry_count": 0,
            "max_retries": 3,
            "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
          }
        ],
        "in_progress": [],
        "done": [],
        "failed": []
      }
    },
    "reviewer": {
      "name": "reviewer",
      "agent": "gemini-reviewer",
      "tasks": {
        "backlog": [],
        "todo": [],
        "in_progress": [],
        "done": [],
        "failed": []
      }
    }
  },
  "summary": {
    "total_tasks": 2,
    "by_state": {
      "backlog": 0,
      "todo": 1,
      "in_progress": 1,
      "done": 0,
      "failed": 0
    }
  }
}
```

**Response Body 스키마:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `lanes` | object\<string, Lane\> | 레인 이름 → Lane 객체 맵 |
| `lanes.{name}.name` | string | 레인 이름 |
| `lanes.{name}.agent` | string \| null | 할당된 에이전트 이름 |
| `lanes.{name}.tasks` | object\<string, array\<TaskItem\>\> | 상태별 태스크 목록 |
| `summary.total_tasks` | integer | 전체 태스크 수 |
| `summary.by_state` | object\<string, integer\> | 상태별 태스크 수 |

**예시:**

```bash
curl http://localhost:8000/api/board
```

---

### GET /api/board/lanes — 레인 목록

현재 활성 레인 목록만 간략하게 조회한다.

**Response (200 OK):**

```json
{
  "lanes": [
    {
      "name": "architect",
      "agent": "claude-architect",
      "task_count": 1,
      "active_task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    },
    {
      "name": "implementer",
      "agent": "codex-implementer",
      "task_count": 2,
      "active_task_id": null
    },
    {
      "name": "reviewer",
      "agent": "gemini-reviewer",
      "task_count": 0,
      "active_task_id": null
    }
  ]
}
```

**Response Body — LaneSummary 스키마:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string | 레인 이름 |
| `agent` | string \| null | 할당된 에이전트 이름 |
| `task_count` | integer | 레인에 할당된 총 태스크 수 |
| `active_task_id` | string \| null | 현재 `in_progress` 상태인 태스크 ID |

**예시:**

```bash
curl http://localhost:8000/api/board/lanes
```

---

### GET /api/board/tasks/{id} — 보드 태스크 상세

칸반 보드의 특정 태스크 상세 정보를 조회한다. 파이프라인 컨텍스트 포함.

**Path Parameters:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `id` | string (UUID) | 태스크 ID |

**Response (200 OK):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "JWT 토큰 생성/검증 모듈 구현",
  "lane": "implementer",
  "state": "in_progress",
  "depends_on": [],
  "assigned_to": "claude-implementer",
  "result": "",
  "retry_count": 0,
  "max_retries": 3,
  "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
  "pipeline_task": "JWT 인증 미들웨어 구현",
  "events": [
    {
      "id": "evt-001",
      "type": "task_state_changed",
      "timestamp": "2026-04-05T14:30:05Z",
      "data": {
        "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "from_state": "todo",
        "to_state": "in_progress"
      }
    }
  ]
}
```

**Response Body 추가 필드:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `pipeline_task` | string | 소속 파이프라인의 원본 태스크 설명 |
| `events` | array\<Event\> | 해당 태스크 관련 이벤트 목록 (최근 50건) |

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `TASK_NOT_FOUND` | 404 | 해당 ID의 보드 태스크가 존재하지 않음 |

**예시:**

```bash
curl http://localhost:8000/api/board/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 5. 에이전트 API

### GET /api/agents — 에이전트 상태 조회

현재 등록된 모든 에이전트의 상태를 조회한다.

**Response (200 OK):**

```json
{
  "agents": [
    {
      "name": "claude-architect",
      "executor_type": "cli",
      "cli": "claude",
      "persona": {
        "role": "시니어 소프트웨어 아키텍트",
        "goal": "시스템 아키텍처 설계 및 기술 의사결정",
        "backstory": "10년 경력의 분산 시스템 전문가",
        "constraints": ["프레임워크 선택 근거를 반드시 명시"]
      },
      "status": "busy",
      "current_task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "health": true,
      "tasks_completed": 5,
      "tasks_failed": 0,
      "uptime_seconds": 3600
    },
    {
      "name": "codex-implementer",
      "executor_type": "cli",
      "cli": "codex",
      "persona": {
        "role": "풀스택 개발자",
        "goal": "설계를 기반으로 정확한 코드 구현",
        "backstory": "",
        "constraints": []
      },
      "status": "idle",
      "current_task_id": null,
      "health": true,
      "tasks_completed": 3,
      "tasks_failed": 1,
      "uptime_seconds": 3600
    },
    {
      "name": "gemini-reviewer",
      "executor_type": "cli",
      "cli": "gemini",
      "persona": {
        "role": "코드 리뷰어",
        "goal": "코드 품질 검증 및 보안 취약점 탐지",
        "backstory": "",
        "constraints": ["보안 이슈는 반드시 CRITICAL로 분류"]
      },
      "status": "idle",
      "current_task_id": null,
      "health": true,
      "tasks_completed": 2,
      "tasks_failed": 0,
      "uptime_seconds": 3600
    }
  ]
}
```

**Response Body — Agent 스키마:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string | 에이전트 고유 이름 |
| `executor_type` | string | 실행기 유형. `"cli"` \| `"mcp"` \| `"mock"` |
| `cli` | string \| null | CLI 이름 (`executor_type`이 `"cli"`일 때). `"claude"` \| `"codex"` \| `"gemini"` |
| `persona` | PersonaDef | 페르소나 정의 |
| `persona.role` | string | 역할 |
| `persona.goal` | string | 목표 |
| `persona.backstory` | string | 배경 설명 |
| `persona.constraints` | array\<string\> | 행동 제약 목록 |
| `status` | string | 에이전트 상태. `"idle"` \| `"busy"` \| `"error"` \| `"offline"` |
| `current_task_id` | string \| null | 현재 작업 중인 태스크 ID |
| `health` | boolean | 헬스 체크 통과 여부 |
| `tasks_completed` | integer | 완료한 태스크 수 (세션 내) |
| `tasks_failed` | integer | 실패한 태스크 수 (세션 내) |
| `uptime_seconds` | integer | 에이전트 가동 시간 (초) |

**예시:**

```bash
curl http://localhost:8000/api/agents
```

---

## 6. 프리셋 API

### GET /api/presets/agents — 에이전트 프리셋 목록

등록된 모든 에이전트 프리셋을 조회한다.

**Response (200 OK):**

```json
{
  "presets": [
    {
      "name": "architect",
      "persona": {
        "role": "시니어 소프트웨어 아키텍트",
        "goal": "시스템 아키텍처 설계 및 기술 의사결정",
        "backstory": "10년 경력의 분산 시스템 전문가",
        "constraints": ["프레임워크 선택 근거를 반드시 명시"]
      },
      "execution_mode": "cli",
      "preferred_cli": "claude",
      "mcp_servers": {},
      "tools": {
        "allowed": [],
        "disallowed": []
      },
      "limits": {
        "max_tokens": 16384,
        "timeout": 300,
        "max_turns": 10
      },
      "source": "builtin"
    },
    {
      "name": "implementer",
      "persona": {
        "role": "풀스택 개발자",
        "goal": "설계를 기반으로 정확한 코드 구현",
        "backstory": "",
        "constraints": []
      },
      "execution_mode": "cli",
      "preferred_cli": "codex",
      "mcp_servers": {},
      "tools": {
        "allowed": [],
        "disallowed": []
      },
      "limits": {
        "max_tokens": 16384,
        "timeout": 300,
        "max_turns": 10
      },
      "source": "builtin"
    },
    {
      "name": "elk-analyst",
      "persona": {
        "role": "ELK 로그 분석가",
        "goal": "Elasticsearch 로그에서 이상 패턴 탐지 및 근본 원인 분석",
        "backstory": "보안 운영 5년 경력",
        "constraints": ["분석 결과에 타임라인 포함 필수"]
      },
      "execution_mode": "mcp",
      "preferred_cli": "claude",
      "mcp_servers": {
        "elasticsearch": {
          "command": "npx",
          "args": ["@anthropic/mcp-server-elasticsearch"],
          "env": {
            "ES_URL": "${ES_URL}",
            "ES_API_KEY": "${ES_API_KEY}"
          }
        }
      },
      "tools": {
        "allowed": ["search", "get_indices", "get_mappings"],
        "disallowed": []
      },
      "limits": {
        "max_tokens": 32768,
        "timeout": 600,
        "max_turns": 20
      },
      "source": "builtin"
    }
  ]
}
```

**Response Body — AgentPreset 스키마:**

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `name` | string | — | 프리셋 고유 이름 |
| `persona` | PersonaDef | — | 페르소나 정의 |
| `persona.role` | string | — | 역할 |
| `persona.goal` | string | — | 목표 |
| `persona.backstory` | string | `""` | 배경 설명 |
| `persona.constraints` | array\<string\> | `[]` | 행동 제약 |
| `execution_mode` | string | `"cli"` | `"cli"` \| `"mcp"` |
| `preferred_cli` | string | `"claude"` | `"claude"` \| `"codex"` \| `"gemini"` |
| `mcp_servers` | object | `{}` | MCP 서버 설정 맵 |
| `tools` | ToolAccess | `{"allowed": [], "disallowed": []}` | 도구 접근 제어 |
| `tools.allowed` | array\<string\> | `[]` | 허용 도구 (빈 배열 = 모두 허용) |
| `tools.disallowed` | array\<string\> | `[]` | 차단 도구 |
| `limits` | AgentLimits | — | 실행 제한 |
| `limits.max_tokens` | integer | `16384` | 최대 출력 토큰 |
| `limits.timeout` | integer | `300` | 실행 타임아웃 (초) |
| `limits.max_turns` | integer | `10` | 최대 대화 턴 수 |
| `source` | string | — | 프리셋 출처. `"builtin"` \| `"user"` |

**예시:**

```bash
curl http://localhost:8000/api/presets/agents
```

---

### GET /api/presets/teams — 팀 프리셋 목록

등록된 모든 팀 프리셋을 조회한다.

**Response (200 OK):**

```json
{
  "presets": [
    {
      "name": "feature-team",
      "agents": {
        "architect": {
          "preset": "architect",
          "count": 1,
          "cli_override": null
        },
        "implementer": {
          "preset": "implementer",
          "count": 2,
          "cli_override": null
        },
        "reviewer": {
          "preset": "reviewer",
          "count": 1,
          "cli_override": "gemini"
        }
      },
      "tasks": {
        "design": {
          "description": "시스템 설계",
          "agent": "architect",
          "depends_on": []
        },
        "implement": {
          "description": "코드 구현",
          "agent": "implementer",
          "depends_on": ["design"]
        },
        "review": {
          "description": "코드 리뷰",
          "agent": "reviewer",
          "depends_on": ["implement"]
        }
      },
      "workflow": "sequential",
      "synthesis_strategy": "narrative",
      "source": "builtin"
    },
    {
      "name": "incident-analysis",
      "agents": {
        "elk-analyst": {
          "preset": "elk-analyst",
          "count": 1,
          "cli_override": null
        },
        "grafana-analyst": {
          "preset": "grafana-analyst",
          "count": 1,
          "cli_override": null
        },
        "k8s-analyst": {
          "preset": "k8s-analyst",
          "count": 1,
          "cli_override": null
        }
      },
      "tasks": {
        "log-analysis": {
          "description": "ELK 로그 분석",
          "agent": "elk-analyst",
          "depends_on": []
        },
        "metric-analysis": {
          "description": "Grafana 메트릭 분석",
          "agent": "grafana-analyst",
          "depends_on": []
        },
        "infra-analysis": {
          "description": "K8s 인프라 점검",
          "agent": "k8s-analyst",
          "depends_on": []
        }
      },
      "workflow": "parallel",
      "synthesis_strategy": "structured",
      "source": "builtin"
    }
  ]
}
```

**Response Body — TeamPreset 스키마:**

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `name` | string | — | 팀 프리셋 고유 이름 |
| `agents` | object\<string, TeamAgentDef\> | — | 에이전트 역할 → 정의 맵 |
| `agents.{role}.preset` | string | — | 참조할 에이전트 프리셋 이름 |
| `agents.{role}.count` | integer | `1` | 해당 역할의 에이전트 수 |
| `agents.{role}.cli_override` | string \| null | `null` | CLI 오버라이드. `null`이면 프리셋 기본값 사용 |
| `tasks` | object\<string, TeamTaskDef\> | — | 태스크 이름 → 정의 맵 |
| `tasks.{name}.description` | string | — | 태스크 설명 |
| `tasks.{name}.agent` | string | — | 담당 에이전트 역할 (agents 키와 매칭) |
| `tasks.{name}.depends_on` | array\<string\> | `[]` | 의존 태스크 이름 목록 |
| `workflow` | string | `"parallel"` | 워크플로우 유형. `"parallel"` \| `"sequential"` \| `"dag"` |
| `synthesis_strategy` | string | `"narrative"` | 결과 종합 전략. `"narrative"` \| `"structured"` \| `"checklist"` |
| `source` | string | — | 프리셋 출처. `"builtin"` \| `"user"` |

**예시:**

```bash
curl http://localhost:8000/api/presets/teams
```

---

### POST /api/presets/agents — 에이전트 프리셋 생성

새로운 에이전트 프리셋을 생성한다.

**Request Body:**

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `name` | string | **필수** | — | 프리셋 이름 (영문, 하이픈, 언더스코어만 허용). 패턴: `^[a-z][a-z0-9_-]{1,62}$` |
| `persona` | PersonaDef | **필수** | — | 페르소나 정의 |
| `persona.role` | string | **필수** | — | 역할 |
| `persona.goal` | string | **필수** | — | 목표 |
| `persona.backstory` | string | 선택 | `""` | 배경 설명 |
| `persona.constraints` | array\<string\> | 선택 | `[]` | 행동 제약 |
| `execution_mode` | string | 선택 | `"cli"` | `"cli"` \| `"mcp"` |
| `preferred_cli` | string | 선택 | `"claude"` | `"claude"` \| `"codex"` \| `"gemini"` |
| `mcp_servers` | object | 선택 | `{}` | MCP 서버 설정 |
| `tools` | ToolAccess | 선택 | `{"allowed": [], "disallowed": []}` | 도구 접근 제어 |
| `limits` | AgentLimits | 선택 | — | 실행 제한 |
| `limits.max_tokens` | integer | 선택 | `16384` | 범위: 1 ~ 131072 |
| `limits.timeout` | integer | 선택 | `300` | 범위: 10 ~ 3600 |
| `limits.max_turns` | integer | 선택 | `10` | 범위: 1 ~ 100 |

**Response (201 Created):**

```json
{
  "name": "security-auditor",
  "persona": {
    "role": "시니어 보안 감사자",
    "goal": "코드 보안 취약점 탐지 및 OWASP Top 10 검증",
    "backstory": "보안 컨설팅 7년 경력",
    "constraints": [
      "CRITICAL 이슈는 반드시 즉시 보고",
      "CVE 번호 참조 필수"
    ]
  },
  "execution_mode": "cli",
  "preferred_cli": "claude",
  "mcp_servers": {},
  "tools": {
    "allowed": [],
    "disallowed": []
  },
  "limits": {
    "max_tokens": 16384,
    "timeout": 300,
    "max_turns": 10
  },
  "source": "user"
}
```

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `VALIDATION_ERROR` | 400 | 필수 필드 누락 또는 형식 오류 |
| `PRESET_ALREADY_EXISTS` | 409 | 동일 이름의 프리셋이 이미 존재 |

**예시:**

```bash
curl -X POST http://localhost:8000/api/presets/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "security-auditor",
    "persona": {
      "role": "시니어 보안 감사자",
      "goal": "코드 보안 취약점 탐지 및 OWASP Top 10 검증",
      "backstory": "보안 컨설팅 7년 경력",
      "constraints": ["CRITICAL 이슈는 반드시 즉시 보고", "CVE 번호 참조 필수"]
    },
    "preferred_cli": "claude"
  }'
```

```json
{
  "name": "security-auditor",
  "persona": {
    "role": "시니어 보안 감사자",
    "goal": "코드 보안 취약점 탐지 및 OWASP Top 10 검증",
    "backstory": "보안 컨설팅 7년 경력",
    "constraints": ["CRITICAL 이슈는 반드시 즉시 보고", "CVE 번호 참조 필수"]
  },
  "execution_mode": "cli",
  "preferred_cli": "claude",
  "mcp_servers": {},
  "tools": {
    "allowed": [],
    "disallowed": []
  },
  "limits": {
    "max_tokens": 16384,
    "timeout": 300,
    "max_turns": 10
  },
  "source": "user"
}
```

---

### POST /api/presets/teams — 팀 프리셋 생성

새로운 팀 프리셋을 생성한다.

**Request Body:**

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `name` | string | **필수** | — | 팀 프리셋 이름. 패턴: `^[a-z][a-z0-9_-]{1,62}$` |
| `agents` | object\<string, TeamAgentDef\> | **필수** | — | 에이전트 역할 정의 (최소 1개) |
| `agents.{role}.preset` | string | **필수** | — | 참조할 에이전트 프리셋 이름 (존재해야 함) |
| `agents.{role}.count` | integer | 선택 | `1` | 범위: 1 ~ 5 |
| `agents.{role}.cli_override` | string \| null | 선택 | `null` | `"claude"` \| `"codex"` \| `"gemini"` \| `null` |
| `tasks` | object\<string, TeamTaskDef\> | **필수** | — | 태스크 정의 (최소 1개) |
| `tasks.{name}.description` | string | **필수** | — | 태스크 설명 |
| `tasks.{name}.agent` | string | **필수** | — | 담당 에이전트 역할 (agents 키와 매칭해야 함) |
| `tasks.{name}.depends_on` | array\<string\> | 선택 | `[]` | 의존 태스크 이름 (tasks 키와 매칭해야 함, 순환 불가) |
| `workflow` | string | 선택 | `"parallel"` | `"parallel"` \| `"sequential"` \| `"dag"` |
| `synthesis_strategy` | string | 선택 | `"narrative"` | `"narrative"` \| `"structured"` \| `"checklist"` |

**Response (201 Created):**

```json
{
  "name": "security-review-team",
  "agents": {
    "auditor": {
      "preset": "security-auditor",
      "count": 1,
      "cli_override": null
    },
    "implementer": {
      "preset": "implementer",
      "count": 1,
      "cli_override": null
    }
  },
  "tasks": {
    "audit": {
      "description": "보안 감사 수행",
      "agent": "auditor",
      "depends_on": []
    },
    "fix": {
      "description": "발견된 이슈 수정",
      "agent": "implementer",
      "depends_on": ["audit"]
    }
  },
  "workflow": "sequential",
  "synthesis_strategy": "checklist",
  "source": "user"
}
```

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `VALIDATION_ERROR` | 400 | 필수 필드 누락, 형식 오류, 순환 의존성 검출 |
| `PRESET_NOT_FOUND` | 404 | `agents.{role}.preset`이 참조하는 에이전트 프리셋이 없음 |
| `PRESET_ALREADY_EXISTS` | 409 | 동일 이름의 팀 프리셋이 이미 존재 |

**예시:**

```bash
curl -X POST http://localhost:8000/api/presets/teams \
  -H "Content-Type: application/json" \
  -d '{
    "name": "security-review-team",
    "agents": {
      "auditor": { "preset": "security-auditor", "count": 1 },
      "implementer": { "preset": "implementer", "count": 1 }
    },
    "tasks": {
      "audit": { "description": "보안 감사 수행", "agent": "auditor" },
      "fix": { "description": "발견된 이슈 수정", "agent": "implementer", "depends_on": ["audit"] }
    },
    "workflow": "sequential",
    "synthesis_strategy": "checklist"
  }'
```

---

## 7. 아티팩트 API

### GET /api/artifacts/{task_id} — 아티팩트 목록

특정 파이프라인에서 생성된 아티팩트(코드, 로그, 리뷰 결과 등) 목록을 조회한다.

**Path Parameters:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `task_id` | string (UUID) | 파이프라인 ID |

**Response (200 OK):**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "artifacts": [
    {
      "path": "subtask-a1b2c3d4/output.json",
      "type": "agent_output",
      "size_bytes": 2048,
      "agent": "claude-implementer",
      "subtask_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "created_at": "2026-04-05T14:32:00Z"
    },
    {
      "path": "subtask-b2c3d4e5/output.json",
      "type": "agent_output",
      "size_bytes": 1536,
      "agent": "codex-implementer",
      "subtask_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "created_at": "2026-04-05T14:33:00Z"
    },
    {
      "path": "subtask-c3d4e5f6/review.json",
      "type": "review",
      "size_bytes": 1024,
      "agent": "gemini-reviewer",
      "subtask_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "created_at": "2026-04-05T14:34:00Z"
    },
    {
      "path": "synthesis/final-report.md",
      "type": "synthesis",
      "size_bytes": 4096,
      "agent": null,
      "subtask_id": null,
      "created_at": "2026-04-05T14:35:00Z"
    }
  ]
}
```

**Response Body — Artifact 스키마:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `path` | string | 아티팩트 스토어 내 상대 경로 |
| `type` | string | 아티팩트 유형. `"agent_output"` \| `"review"` \| `"synthesis"` \| `"diff"` \| `"log"` |
| `size_bytes` | integer | 파일 크기 (바이트) |
| `agent` | string \| null | 생성한 에이전트 이름. synthesis 등은 `null` |
| `subtask_id` | string \| null | 관련 서브태스크 ID |
| `created_at` | string (ISO 8601) | 생성 시각 |

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `TASK_NOT_FOUND` | 404 | 해당 ID의 파이프라인이 존재하지 않음 |

**예시:**

```bash
curl http://localhost:8000/api/artifacts/550e8400-e29b-41d4-a716-446655440000
```

---

### GET /api/artifacts/{task_id}/{path} — 아티팩트 파일 다운로드

특정 아티팩트 파일의 내용을 다운로드한다.

**Path Parameters:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `task_id` | string (UUID) | 파이프라인 ID |
| `path` | string | 아티팩트 상대 경로 (URL 인코딩 필요) |

**Response (200 OK):**

- **Content-Type**: 파일 확장자에 따라 자동 결정
  - `.json` → `application/json`
  - `.md` → `text/markdown`
  - `.py`, `.ts`, `.js` → `text/plain`
  - 기타 → `application/octet-stream`
- **Body**: 파일 원본 내용

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `TASK_NOT_FOUND` | 404 | 파이프라인이 존재하지 않음 |
| `ARTIFACT_NOT_FOUND` | 404 | 해당 경로의 아티팩트 파일이 없음 |

**예시:**

```bash
# JSON 아티팩트
curl http://localhost:8000/api/artifacts/550e8400-e29b-41d4-a716-446655440000/subtask-a1b2c3d4/output.json

# 종합 보고서
curl http://localhost:8000/api/artifacts/550e8400-e29b-41d4-a716-446655440000/synthesis/final-report.md
```

---

## 8. 이벤트 API

### GET /api/events — 이벤트 히스토리

시스템 이벤트를 시간순으로 조회한다.

**Query Parameters:**

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `task_id` | string \| null | `null` | 특정 파이프라인의 이벤트만 필터 (선택) |
| `limit` | integer | `50` | 반환할 최대 이벤트 수. 범위: 1 ~ 500 |
| `offset` | integer | `0` | 건너뛸 이벤트 수. 범위: 0 ~ 10000 |
| `type` | string \| null | `null` | 이벤트 유형 필터 (선택) |

**Response (200 OK):**

```json
{
  "items": [
    {
      "id": "evt-20260405-143000-001",
      "type": "pipeline_started",
      "timestamp": "2026-04-05T14:30:00Z",
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
      "data": {
        "task": "JWT 인증 미들웨어 구현",
        "team_preset": "feature-team"
      }
    },
    {
      "id": "evt-20260405-143002-002",
      "type": "decomposition_completed",
      "timestamp": "2026-04-05T14:30:02Z",
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
      "data": {
        "subtask_count": 3,
        "subtask_ids": [
          "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "b2c3d4e5-f6a7-8901-bcde-f12345678901",
          "c3d4e5f6-a7b8-9012-cdef-123456789012"
        ]
      }
    },
    {
      "id": "evt-20260405-143005-003",
      "type": "task_state_changed",
      "timestamp": "2026-04-05T14:30:05Z",
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
      "data": {
        "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "from_state": "todo",
        "to_state": "in_progress",
        "agent": "claude-implementer"
      }
    },
    {
      "id": "evt-20260405-143200-004",
      "type": "agent_output",
      "timestamp": "2026-04-05T14:32:00Z",
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
      "data": {
        "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "agent": "claude-implementer",
        "output_preview": "src/middleware/jwt.py 생성 완료...",
        "artifact_path": "subtask-a1b2c3d4/output.json"
      }
    },
    {
      "id": "evt-20260405-143205-005",
      "type": "task_state_changed",
      "timestamp": "2026-04-05T14:32:05Z",
      "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
      "data": {
        "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "from_state": "in_progress",
        "to_state": "done",
        "agent": "claude-implementer"
      }
    }
  ],
  "total": 5,
  "offset": 0,
  "limit": 50
}
```

**Response Body — Event 스키마:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 이벤트 고유 ID |
| `type` | string | 이벤트 유형 (아래 표 참조) |
| `timestamp` | string (ISO 8601) | 이벤트 발생 시각 |
| `pipeline_id` | string \| null | 관련 파이프라인 ID |
| `data` | object | 이벤트별 페이로드 (유형마다 다름) |

**이벤트 유형 목록:**

| type | 설명 | data 필드 |
|------|------|-----------|
| `pipeline_started` | 파이프라인 시작 | `task`, `team_preset` |
| `pipeline_completed` | 파이프라인 완료 | `result_preview`, `duration_seconds` |
| `pipeline_failed` | 파이프라인 실패 | `error_code`, `error_message` |
| `pipeline_cancelled` | 파이프라인 취소 | — |
| `pipeline_resumed` | 파이프라인 재개 | — |
| `decomposition_completed` | 태스크 분해 완료 | `subtask_count`, `subtask_ids` |
| `team_composed` | 팀 구성 완료 | `agents`, `lanes` |
| `task_state_changed` | 서브태스크 상태 변경 | `task_id`, `from_state`, `to_state`, `agent` |
| `agent_output` | 에이전트 출력 생성 | `task_id`, `agent`, `output_preview`, `artifact_path` |
| `agent_error` | 에이전트 실행 에러 | `task_id`, `agent`, `error_code`, `error_message`, `retry_count` |
| `agent_fallback` | 에이전트 폴백 발생 | `task_id`, `from_cli`, `to_cli`, `reason` |
| `synthesis_started` | 결과 종합 시작 | `strategy`, `input_count` |
| `synthesis_completed` | 결과 종합 완료 | `result_preview` |
| `worktree_created` | Git worktree 생성 | `task_id`, `branch`, `path` |
| `worktree_merged` | Git worktree 병합 | `task_id`, `branch`, `merge_result` |
| `health_check` | 에이전트 헬스 체크 | `agent`, `healthy`, `latency_ms` |

**에러 응답:**

| 코드 | 상태 | 원인 |
|------|------|------|
| `VALIDATION_ERROR` | 400 | `limit` 범위 초과 |

**예시:**

```bash
# 전체 이벤트 (최근 50건)
curl http://localhost:8000/api/events

# 특정 파이프라인 이벤트
curl "http://localhost:8000/api/events?task_id=550e8400-e29b-41d4-a716-446655440000&limit=100"

# 특정 유형만 필터
curl "http://localhost:8000/api/events?type=agent_error&limit=20"
```

---

## 9. 헬스 체크 API

### GET /api/health — 헬스 체크

서버 및 핵심 컴포넌트 상태를 확인한다.

**Response (200 OK):**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 7200,
  "components": {
    "engine": {
      "status": "healthy",
      "active_pipelines": 1,
      "total_pipelines": 5
    },
    "task_board": {
      "status": "healthy",
      "total_tasks": 3,
      "active_lanes": 2
    },
    "cli_adapters": {
      "claude": {
        "status": "healthy",
        "available": true,
        "version": "1.0.34"
      },
      "codex": {
        "status": "healthy",
        "available": true,
        "version": "0.1.2"
      },
      "gemini": {
        "status": "degraded",
        "available": true,
        "version": "0.3.1",
        "warning": "높은 지연 감지 (평균 15초)"
      }
    },
    "event_bus": {
      "status": "healthy",
      "subscribers": 3,
      "events_emitted": 142
    }
  },
  "timestamp": "2026-04-05T14:30:00Z"
}
```

**Response Body 스키마:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `status` | string | 전체 상태. `"healthy"` \| `"degraded"` \| `"unhealthy"` |
| `version` | string | 서버 버전 |
| `uptime_seconds` | integer | 서버 가동 시간 (초) |
| `components` | object | 컴포넌트별 상태 |
| `components.engine.status` | string | `"healthy"` \| `"unhealthy"` |
| `components.engine.active_pipelines` | integer | 현재 실행 중인 파이프라인 수 |
| `components.engine.total_pipelines` | integer | 전체 파이프라인 수 (세션 내) |
| `components.task_board.status` | string | `"healthy"` \| `"unhealthy"` |
| `components.task_board.total_tasks` | integer | 보드 내 전체 태스크 수 |
| `components.task_board.active_lanes` | integer | 활성 레인 수 |
| `components.cli_adapters.{cli}.status` | string | `"healthy"` \| `"degraded"` \| `"unhealthy"` |
| `components.cli_adapters.{cli}.available` | boolean | CLI 바이너리 존재 여부 |
| `components.cli_adapters.{cli}.version` | string \| null | CLI 버전 |
| `components.cli_adapters.{cli}.warning` | string \| null | 경고 메시지 (degraded 시) |
| `components.event_bus.status` | string | `"healthy"` \| `"unhealthy"` |
| `components.event_bus.subscribers` | integer | WebSocket 구독자 수 |
| `components.event_bus.events_emitted` | integer | 발행된 이벤트 총 수 |
| `timestamp` | string (ISO 8601) | 체크 시각 |

**`status` 결정 규칙:**

- `"healthy"`: 모든 컴포넌트 정상
- `"degraded"`: 일부 컴포넌트 경고 (서비스는 계속 가능)
- `"unhealthy"`: 핵심 컴포넌트 장애 (Engine 또는 TaskBoard)

**예시:**

```bash
curl http://localhost:8000/api/health
```

---

## 10. WebSocket 프로토콜

### 연결

```
ws://localhost:8000/ws/events
```

#### 연결 예시 (JavaScript)

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/events");

ws.onopen = () => {
  console.log("Connected");
  // 선택: 특정 파이프라인만 구독
  ws.send(JSON.stringify({
    type: "subscribe",
    pipeline_id: "550e8400-e29b-41d4-a716-446655440000"
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Event:", data);
};

ws.onclose = (event) => {
  console.log("Disconnected:", event.code, event.reason);
};
```

#### 연결 예시 (Python)

```python
import asyncio
import websockets
import json

async def listen():
    async with websockets.connect("ws://localhost:8000/ws/events") as ws:
        # 선택: 특정 파이프라인만 구독
        await ws.send(json.dumps({
            "type": "subscribe",
            "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
        }))

        async for message in ws:
            event = json.loads(message)
            print(f"[{event['type']}] {event['data']}")

asyncio.run(listen())
```

### 클라이언트 → 서버 메시지

클라이언트가 서버로 보낼 수 있는 메시지 유형.

#### subscribe — 파이프라인 구독

특정 파이프라인의 이벤트만 수신하도록 필터를 설정한다. 여러 번 호출하면 마지막 설정이 적용된다.

```json
{
  "type": "subscribe",
  "pipeline_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `type` | string | **필수** | `"subscribe"` |
| `pipeline_id` | string (UUID) | **필수** | 구독할 파이프라인 ID |

#### unsubscribe — 구독 해제

파이프라인 필터를 해제하고 모든 이벤트를 수신한다.

```json
{
  "type": "unsubscribe"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `type` | string | **필수** | `"unsubscribe"` |

#### ping — 연결 유지

서버에 ping을 보내 연결 유지를 확인한다.

```json
{
  "type": "ping"
}
```

### 서버 → 클라이언트 메시지

서버가 클라이언트에게 보내는 메시지 유형.

#### event — 시스템 이벤트

REST API의 이벤트와 동일한 구조. 실시간으로 푸시된다.

```json
{
  "type": "event",
  "event": {
    "id": "evt-20260405-143005-003",
    "type": "task_state_changed",
    "timestamp": "2026-04-05T14:30:05Z",
    "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
    "data": {
      "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "from_state": "todo",
      "to_state": "in_progress",
      "agent": "claude-implementer"
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `type` | string | `"event"` |
| `event` | Event | 이벤트 객체 (GET /api/events 응답과 동일 구조) |

#### pong — ping 응답

```json
{
  "type": "pong",
  "timestamp": "2026-04-05T14:30:00Z"
}
```

#### error — 프로토콜 에러

잘못된 메시지 형식이나 존재하지 않는 파이프라인 구독 시도 시 반환.

```json
{
  "type": "error",
  "code": "INVALID_MESSAGE",
  "message": "알 수 없는 메시지 유형입니다: foobar"
}
```

| 에러 코드 | 설명 |
|----------|------|
| `INVALID_MESSAGE` | 메시지 JSON 파싱 실패 또는 `type` 필드 누락 |
| `UNKNOWN_MESSAGE_TYPE` | 알 수 없는 메시지 유형 |
| `PIPELINE_NOT_FOUND` | subscribe 시 파이프라인 ID가 존재하지 않음 |

### 연결 생명주기

1. **연결**: 클라이언트가 `ws://localhost:8000/ws/events`에 연결
2. **초기 상태**: 모든 이벤트 수신 (필터 없음)
3. **구독 설정** (선택): `subscribe` 메시지로 특정 파이프라인 필터 설정
4. **이벤트 수신**: 서버가 `event` 메시지를 실시간 푸시
5. **연결 유지**: 클라이언트가 30초마다 `ping` 전송 권장
6. **타임아웃**: 서버는 60초 동안 클라이언트 메시지가 없으면 연결 종료
7. **종료**: 클라이언트 또는 서버가 WebSocket close frame 전송

### 재연결 전략

클라이언트는 연결 끊김 시 지수 백오프로 재연결해야 한다.

```
재연결 대기: min(1초 * 2^attempt + random(0~0.5초), 30초)
최대 시도: 무제한 (백그라운드 재연결)
```

재연결 후 마지막 수신 이벤트 ID 이후의 이벤트를 REST API (`GET /api/events`)로 보완 조회.

---

## 부록: 전체 엔드포인트 요약

| Method | Path | 상태 코드 | 설명 |
|--------|------|----------|------|
| POST | `/api/tasks` | 201, 400, 404, 500 | 태스크 제출 |
| GET | `/api/tasks` | 200, 400 | 파이프라인 목록 |
| GET | `/api/tasks/{id}` | 200, 404 | 파이프라인 상세 |
| POST | `/api/tasks/{id}/resume` | 200, 404, 409 | 태스크 재개 |
| DELETE | `/api/tasks/{id}` | 204, 404, 409 | 태스크 취소 |
| GET | `/api/board` | 200 | 칸반 보드 전체 |
| GET | `/api/board/lanes` | 200 | 레인 목록 |
| GET | `/api/board/tasks/{id}` | 200, 404 | 보드 태스크 상세 |
| GET | `/api/agents` | 200 | 에이전트 상태 |
| GET | `/api/presets/agents` | 200 | 에이전트 프리셋 목록 |
| GET | `/api/presets/teams` | 200 | 팀 프리셋 목록 |
| POST | `/api/presets/agents` | 201, 400, 409 | 에이전트 프리셋 생성 |
| POST | `/api/presets/teams` | 201, 400, 404, 409 | 팀 프리셋 생성 |
| GET | `/api/artifacts/{task_id}` | 200, 404 | 아티팩트 목록 |
| GET | `/api/artifacts/{task_id}/{path}` | 200, 404 | 아티팩트 다운로드 |
| GET | `/api/events` | 200, 400 | 이벤트 히스토리 |
| GET | `/api/health` | 200 | 헬스 체크 |
| WS | `/ws/events` | — | 실시간 이벤트 스트림 |
