# 에러 명세서

> v1.0 | 2026-04-05
> 기반: `docs/SPEC.md` v2.0, `research/part6-error-handling.md`

---

## 목차

1. [예외 계층 구조](#1-예외-계층-구조)
2. [예외 클래스 상세](#2-예외-클래스-상세)
3. [에러 코드 레지스트리](#3-에러-코드-레지스트리)
4. [복구 전략](#4-복구-전략)
5. [API 에러 응답 형식](#5-api-에러-응답-형식)
6. [로깅 명세](#6-로깅-명세)
7. [사용자 표시 메시지](#7-사용자-표시-메시지)
8. [에러 흐름 다이어그램](#8-에러-흐름-다이어그램)

---

## 1. 예외 계층 구조

### 클래스 다이어그램

```
Exception (Python 내장)
 └── OrchestratorError (모든 커스텀 예외의 루트)
      │
      ├── CLIError (CLI 서브프로세스 실행 관련)
      │    ├── CLIExecutionError (프로세스 비정상 종료)
      │    ├── CLITimeoutError (실행 타임아웃)
      │    ├── CLIParseError (출력 파싱 실패)
      │    └── CLINotFoundError (CLI 바이너리 없음)
      │
      ├── AuthError (인증/인가 관련)
      │    ├── AuthMissingKeyError (API 키 미설정)
      │    ├── AuthInvalidKeyError (API 키 무효)
      │    └── AuthQuotaExceededError (할당량 초과)
      │
      ├── WorktreeError (Git worktree 관련)
      │    ├── WorktreeCreateError (생성 실패)
      │    └── WorktreeCleanupError (정리 실패)
      │
      ├── MergeConflictError (Git 병합 충돌)
      │
      ├── DecompositionError (태스크 분해 실패)
      │
      ├── PresetError (프리셋 관련)
      │    ├── PresetNotFoundError (프리셋 없음)
      │    ├── PresetValidationError (프리셋 형식 오류)
      │    └── PresetAlreadyExistsError (중복 이름)
      │
      ├── BoardError (TaskBoard 관련)
      │    ├── TaskNotFoundError (태스크 없음)
      │    ├── TaskNotResumableError (재개 불가 상태)
      │    ├── TaskAlreadyTerminalError (이미 종단 상태)
      │    └── CyclicDependencyError (순환 의존성)
      │
      ├── SynthesisError (결과 종합 실패)
      │
      ├── AllProvidersFailedError (모든 CLI 폴백 실패)
      │
      └── ValidationError (요청 검증 실패)
```

### 설계 원칙

| 원칙 | 설명 |
|------|------|
| **단일 루트** | 모든 커스텀 예외는 `OrchestratorError`를 상속. `except OrchestratorError`로 전체 포착 가능 |
| **에러 코드** | 모든 예외는 고유한 `error_code` 문자열 속성을 가짐 |
| **HTTP 매핑** | 모든 예외는 `http_status` 속성으로 API 계층에서 HTTP 상태 코드로 변환 |
| **재시도 가능 표시** | `retryable: bool` 속성으로 자동 재시도 판단 |
| **한국어 메시지** | `user_message` 속성으로 사용자 표시용 한국어 메시지 제공 |

---

## 2. 예외 클래스 상세

### OrchestratorError (루트)

```python
class OrchestratorError(Exception):
    """모든 오케스트레이터 예외의 기본 클래스."""

    error_code: str = "ORCHESTRATOR_ERROR"
    http_status: int = 500
    retryable: bool = False
    user_message: str = "오케스트레이터 내부 오류가 발생했습니다."

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `error_code` | str | 고유 에러 코드 (상수) |
| `http_status` | int | HTTP 상태 코드 매핑 |
| `retryable` | bool | 자동 재시도 가능 여부 |
| `user_message` | str | 사용자 표시용 메시지 (한국어) |
| `message` | str | 개발자용 상세 메시지 (영어) |
| `details` | dict | 추가 컨텍스트 정보 |

---

### CLIError 계열

#### CLIError (부모)

```python
class CLIError(OrchestratorError):
    """CLI 서브프로세스 실행 관련 에러의 부모 클래스."""

    error_code: str = "CLI_ERROR"
    http_status: int = 502
    retryable: bool = True
    user_message: str = "CLI 에이전트 실행 중 오류가 발생했습니다."

    def __init__(
        self,
        message: str,
        *,
        cli: str,                              # "claude" | "codex" | "gemini"
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.cli = cli
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `cli` | str | 실패한 CLI 이름 |
| `exit_code` | int \| None | 프로세스 종료 코드 (`None`이면 프로세스 종료 전 에러) |
| `stdout` | str | 표준 출력 (잘린 마지막 2000자) |
| `stderr` | str | 표준 에러 (잘린 마지막 2000자) |

---

#### CLIExecutionError

| 항목 | 값 |
|------|-----|
| **클래스** | `CLIExecutionError(CLIError)` |
| **error_code** | `"CLI_EXECUTION_ERROR"` |
| **http_status** | `502` |
| **retryable** | `True` (exit code 137/139는 `False`) |
| **user_message** | `"CLI 에이전트가 비정상 종료되었습니다."` |
| **발생 시점** | CLI subprocess가 비-0 exit code로 종료 |
| **추가 속성** | 없음 (부모 CLIError 속성 사용) |

```python
class CLIExecutionError(CLIError):
    error_code = "CLI_EXECUTION_ERROR"
    user_message = "CLI 에이전트가 비정상 종료되었습니다."

    @property
    def retryable(self) -> bool:
        # OOM(137), segfault(139)는 재시도 불가
        if self.exit_code in (137, 139):
            return False
        return True
```

**발생 예시:**
- Claude Code가 exit code 1로 종료 (일시적 내부 에러)
- Codex CLI가 exit code 137로 종료 (OOM kill)
- Gemini CLI가 비정상 exit code로 종료

---

#### CLITimeoutError

| 항목 | 값 |
|------|-----|
| **클래스** | `CLITimeoutError(CLIError)` |
| **error_code** | `"CLI_TIMEOUT"` |
| **http_status** | `504` |
| **retryable** | `True` |
| **user_message** | `"CLI 에이전트 실행 시간이 초과되었습니다."` |
| **발생 시점** | subprocess가 지정된 timeout 내에 완료되지 않음 |

```python
class CLITimeoutError(CLIError):
    error_code = "CLI_TIMEOUT"
    http_status = 504
    retryable = True
    user_message = "CLI 에이전트 실행 시간이 초과되었습니다."

    def __init__(
        self,
        message: str,
        *,
        cli: str,
        timeout_seconds: int,
        **kwargs,
    ):
        super().__init__(message, cli=cli, **kwargs)
        self.timeout_seconds = timeout_seconds
```

| 추가 속성 | 타입 | 설명 |
|----------|------|------|
| `timeout_seconds` | int | 설정된 타임아웃 값 (초) |

**발생 예시:**
- Gemini CLI 도구 행 걸림 (issue #19774)
- Claude Code가 대용량 프롬프트 처리 중 300초 초과

---

#### CLIParseError

| 항목 | 값 |
|------|-----|
| **클래스** | `CLIParseError(CLIError)` |
| **error_code** | `"CLI_PARSE_ERROR"` |
| **http_status** | `502` |
| **retryable** | `True` |
| **user_message** | `"CLI 에이전트 출력을 해석할 수 없습니다."` |
| **발생 시점** | CLI stdout이 예상 JSON 형식이 아닌 경우 |

```python
class CLIParseError(CLIError):
    error_code = "CLI_PARSE_ERROR"
    retryable = True
    user_message = "CLI 에이전트 출력을 해석할 수 없습니다."

    def __init__(
        self,
        message: str,
        *,
        cli: str,
        raw_output: str,
        expected_format: str = "json",
        **kwargs,
    ):
        super().__init__(message, cli=cli, **kwargs)
        self.raw_output = raw_output[:2000]  # 잘라서 저장
        self.expected_format = expected_format
```

| 추가 속성 | 타입 | 설명 |
|----------|------|------|
| `raw_output` | str | 파싱 실패한 원본 출력 (최대 2000자) |
| `expected_format` | str | 기대 형식 (`"json"` \| `"stream-json"`) |

**발생 예시:**
- Gemini CLI stdout 오염 (issue #21433: non-result 이벤트 혼입)
- Claude Code가 빈 출력 반환 (stdin >7,000자)
- JSON 불완전 (프로세스 중간 종료)

---

#### CLINotFoundError

| 항목 | 값 |
|------|-----|
| **클래스** | `CLINotFoundError(CLIError)` |
| **error_code** | `"CLI_NOT_FOUND"` |
| **http_status** | `503` |
| **retryable** | `False` |
| **user_message** | `"CLI 도구를 찾을 수 없습니다. 설치 여부를 확인하세요."` |
| **발생 시점** | CLI 바이너리가 PATH에 없음 |

```python
class CLINotFoundError(CLIError):
    error_code = "CLI_NOT_FOUND"
    http_status = 503
    retryable = False
    user_message = "CLI 도구를 찾을 수 없습니다. 설치 여부를 확인하세요."
```

**발생 예시:**
- `claude` 명령어가 설치되지 않음
- `codex` 명령어의 PATH가 잘못 설정됨

---

### AuthError 계열

#### AuthError (부모)

```python
class AuthError(OrchestratorError):
    """인증/인가 관련 에러의 부모 클래스."""

    error_code: str = "AUTH_ERROR"
    http_status: int = 401
    retryable: bool = False
    user_message: str = "인증 오류가 발생했습니다."

    def __init__(
        self,
        message: str,
        *,
        provider: str,                         # "anthropic" | "openai" | "google"
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.provider = provider
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `provider` | str | 인증 실패한 프로바이더 이름 |

---

#### AuthMissingKeyError

| 항목 | 값 |
|------|-----|
| **클래스** | `AuthMissingKeyError(AuthError)` |
| **error_code** | `"AUTH_MISSING_KEY"` |
| **http_status** | `503` |
| **retryable** | `False` |
| **user_message** | `"API 키가 설정되지 않았습니다. 환경변수를 확인하세요."` |
| **발생 시점** | 환경변수에 API 키가 없는 상태에서 해당 프로바이더 CLI 실행 시도 |

```python
class AuthMissingKeyError(AuthError):
    error_code = "AUTH_MISSING_KEY"
    http_status = 503
    retryable = False
    user_message = "API 키가 설정되지 않았습니다. 환경변수를 확인하세요."

    def __init__(self, *, provider: str, env_var: str):
        super().__init__(
            f"API key not set for {provider}: {env_var}",
            provider=provider,
        )
        self.env_var = env_var
```

| 추가 속성 | 타입 | 설명 |
|----------|------|------|
| `env_var` | str | 필요한 환경변수 이름 (예: `"ANTHROPIC_API_KEY"`) |

---

#### AuthInvalidKeyError

| 항목 | 값 |
|------|-----|
| **클래스** | `AuthInvalidKeyError(AuthError)` |
| **error_code** | `"AUTH_INVALID_KEY"` |
| **http_status** | `401` |
| **retryable** | `False` |
| **user_message** | `"API 키가 유효하지 않습니다. 키를 확인하세요."` |
| **발생 시점** | CLI 실행 시 프로바이더가 401 반환 |

```python
class AuthInvalidKeyError(AuthError):
    error_code = "AUTH_INVALID_KEY"
    http_status = 401
    retryable = False
    user_message = "API 키가 유효하지 않습니다. 키를 확인하세요."
```

---

#### AuthQuotaExceededError

| 항목 | 값 |
|------|-----|
| **클래스** | `AuthQuotaExceededError(AuthError)` |
| **error_code** | `"AUTH_QUOTA_EXCEEDED"` |
| **http_status** | `429` |
| **retryable** | `False` (폴백으로 다른 프로바이더 시도) |
| **user_message** | `"API 할당량이 초과되었습니다."` |
| **발생 시점** | CLI stderr에서 quota exceeded 메시지 감지 |

```python
class AuthQuotaExceededError(AuthError):
    error_code = "AUTH_QUOTA_EXCEEDED"
    http_status = 429
    retryable = False  # 재시도 대신 폴백
    user_message = "API 할당량이 초과되었습니다."
```

---

### WorktreeError 계열

#### WorktreeError (부모)

```python
class WorktreeError(OrchestratorError):
    """Git worktree 관련 에러."""

    error_code: str = "WORKTREE_ERROR"
    http_status: int = 500
    retryable: bool = False
    user_message: str = "Git worktree 작업 중 오류가 발생했습니다."

    def __init__(
        self,
        message: str,
        *,
        repo_path: str,
        branch: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.repo_path = repo_path
        self.branch = branch
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `repo_path` | str | 대상 저장소 경로 |
| `branch` | str \| None | 관련 브랜치 이름 |

---

#### WorktreeCreateError

| 항목 | 값 |
|------|-----|
| **클래스** | `WorktreeCreateError(WorktreeError)` |
| **error_code** | `"WORKTREE_CREATE_FAILED"` |
| **http_status** | `500` |
| **retryable** | `True` (디스크 일시 문제 가능) |
| **user_message** | `"Git worktree 생성에 실패했습니다."` |
| **발생 시점** | `git worktree add` 명령 실패 |

```python
class WorktreeCreateError(WorktreeError):
    error_code = "WORKTREE_CREATE_FAILED"
    retryable = True
    user_message = "Git worktree 생성에 실패했습니다."
```

---

#### WorktreeCleanupError

| 항목 | 값 |
|------|-----|
| **클래스** | `WorktreeCleanupError(WorktreeError)` |
| **error_code** | `"WORKTREE_CLEANUP_FAILED"` |
| **http_status** | `500` |
| **retryable** | `False` |
| **user_message** | `"Git worktree 정리에 실패했습니다. 수동 확인이 필요합니다."` |
| **발생 시점** | `git worktree remove` 명령 실패 (파일 잠금 등) |

```python
class WorktreeCleanupError(WorktreeError):
    error_code = "WORKTREE_CLEANUP_FAILED"
    retryable = False
    user_message = "Git worktree 정리에 실패했습니다. 수동 확인이 필요합니다."
```

---

### MergeConflictError

| 항목 | 값 |
|------|-----|
| **클래스** | `MergeConflictError(OrchestratorError)` |
| **error_code** | `"MERGE_CONFLICT"` |
| **http_status** | `409` |
| **retryable** | `False` |
| **user_message** | `"Git 병합 충돌이 발생했습니다. 수동 해결이 필요합니다."` |
| **발생 시점** | 에이전트 worktree를 메인 브랜치에 병합할 때 충돌 |

```python
class MergeConflictError(OrchestratorError):
    error_code = "MERGE_CONFLICT"
    http_status = 409
    retryable = False
    user_message = "Git 병합 충돌이 발생했습니다. 수동 해결이 필요합니다."

    def __init__(
        self,
        message: str,
        *,
        source_branch: str,
        target_branch: str,
        conflicting_files: list[str],
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.source_branch = source_branch
        self.target_branch = target_branch
        self.conflicting_files = conflicting_files
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `source_branch` | str | 소스 브랜치 (에이전트 worktree) |
| `target_branch` | str | 대상 브랜치 (메인) |
| `conflicting_files` | list[str] | 충돌 파일 목록 |

---

### DecompositionError

| 항목 | 값 |
|------|-----|
| **클래스** | `DecompositionError(OrchestratorError)` |
| **error_code** | `"DECOMPOSITION_FAILED"` |
| **http_status** | `500` |
| **retryable** | `True` (LLM 일시 에러 가능) |
| **user_message** | `"태스크 분해에 실패했습니다. 태스크 설명을 더 구체적으로 작성해 보세요."` |
| **발생 시점** | LLM 기반 태스크 분해 시 유효한 서브태스크 생성 실패 |

```python
class DecompositionError(OrchestratorError):
    error_code = "DECOMPOSITION_FAILED"
    http_status = 500
    retryable = True
    user_message = "태스크 분해에 실패했습니다. 태스크 설명을 더 구체적으로 작성해 보세요."

    def __init__(
        self,
        message: str,
        *,
        task: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.task = task
        self.reason = reason
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `task` | str | 분해 대상 원본 태스크 |
| `reason` | str | 실패 사유 (`"llm_error"` \| `"invalid_output"` \| `"empty_result"`) |

---

### PresetError 계열

#### PresetNotFoundError

| 항목 | 값 |
|------|-----|
| **클래스** | `PresetNotFoundError(OrchestratorError)` |
| **error_code** | `"PRESET_NOT_FOUND"` |
| **http_status** | `404` |
| **retryable** | `False` |
| **user_message** | `"프리셋을 찾을 수 없습니다."` |
| **발생 시점** | 존재하지 않는 프리셋 이름 참조 |

```python
class PresetNotFoundError(OrchestratorError):
    error_code = "PRESET_NOT_FOUND"
    http_status = 404
    retryable = False
    user_message = "프리셋을 찾을 수 없습니다."

    def __init__(self, *, preset_name: str, preset_type: str = "agent"):
        super().__init__(
            f"{preset_type} preset not found: {preset_name}",
        )
        self.preset_name = preset_name
        self.preset_type = preset_type  # "agent" | "team"
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `preset_name` | str | 요청된 프리셋 이름 |
| `preset_type` | str | 프리셋 유형 (`"agent"` \| `"team"`) |

---

#### PresetValidationError

| 항목 | 값 |
|------|-----|
| **클래스** | `PresetValidationError(OrchestratorError)` |
| **error_code** | `"PRESET_VALIDATION_ERROR"` |
| **http_status** | `400` |
| **retryable** | `False` |
| **user_message** | `"프리셋 형식이 올바르지 않습니다."` |
| **발생 시점** | YAML 파싱 실패, 필수 필드 누락, 타입 불일치 |

```python
class PresetValidationError(OrchestratorError):
    error_code = "PRESET_VALIDATION_ERROR"
    http_status = 400
    retryable = False
    user_message = "프리셋 형식이 올바르지 않습니다."

    def __init__(self, *, preset_name: str, errors: list[dict[str, str]]):
        super().__init__(
            f"Preset validation failed: {preset_name}",
            details={"validation_errors": errors},
        )
        self.preset_name = preset_name
        self.errors = errors
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `preset_name` | str | 검증 실패한 프리셋 이름 |
| `errors` | list[dict] | 검증 에러 목록. 각 항목: `{"field": "persona.role", "message": "필수 필드입니다"}` |

---

#### PresetAlreadyExistsError

| 항목 | 값 |
|------|-----|
| **클래스** | `PresetAlreadyExistsError(OrchestratorError)` |
| **error_code** | `"PRESET_ALREADY_EXISTS"` |
| **http_status** | `409` |
| **retryable** | `False` |
| **user_message** | `"동일한 이름의 프리셋이 이미 존재합니다."` |
| **발생 시점** | 이미 존재하는 이름으로 프리셋 생성 시도 |

```python
class PresetAlreadyExistsError(OrchestratorError):
    error_code = "PRESET_ALREADY_EXISTS"
    http_status = 409
    retryable = False
    user_message = "동일한 이름의 프리셋이 이미 존재합니다."

    def __init__(self, *, preset_name: str, preset_type: str = "agent"):
        super().__init__(
            f"{preset_type} preset already exists: {preset_name}",
        )
        self.preset_name = preset_name
        self.preset_type = preset_type
```

---

### BoardError 계열

#### TaskNotFoundError

| 항목 | 값 |
|------|-----|
| **클래스** | `TaskNotFoundError(OrchestratorError)` |
| **error_code** | `"TASK_NOT_FOUND"` |
| **http_status** | `404` |
| **retryable** | `False` |
| **user_message** | `"태스크를 찾을 수 없습니다."` |
| **발생 시점** | 존재하지 않는 태스크/파이프라인 ID 참조 |

```python
class TaskNotFoundError(OrchestratorError):
    error_code = "TASK_NOT_FOUND"
    http_status = 404
    retryable = False
    user_message = "태스크를 찾을 수 없습니다."

    def __init__(self, *, task_id: str):
        super().__init__(f"Task not found: {task_id}")
        self.task_id = task_id
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `task_id` | str | 요청된 태스크 ID |

---

#### TaskNotResumableError

| 항목 | 값 |
|------|-----|
| **클래스** | `TaskNotResumableError(OrchestratorError)` |
| **error_code** | `"TASK_NOT_RESUMABLE"` |
| **http_status** | `409` |
| **retryable** | `False` |
| **user_message** | `"이 태스크는 재개할 수 없는 상태입니다."` |
| **발생 시점** | `paused` 또는 `failed`가 아닌 상태에서 resume 시도 |

```python
class TaskNotResumableError(OrchestratorError):
    error_code = "TASK_NOT_RESUMABLE"
    http_status = 409
    retryable = False
    user_message = "이 태스크는 재개할 수 없는 상태입니다."

    def __init__(self, *, task_id: str, current_status: str):
        super().__init__(
            f"Task {task_id} cannot be resumed from status: {current_status}",
        )
        self.task_id = task_id
        self.current_status = current_status
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `task_id` | str | 태스크 ID |
| `current_status` | str | 현재 상태 |

---

#### TaskAlreadyTerminalError

| 항목 | 값 |
|------|-----|
| **클래스** | `TaskAlreadyTerminalError(OrchestratorError)` |
| **error_code** | `"TASK_ALREADY_TERMINAL"` |
| **http_status** | `409` |
| **retryable** | `False` |
| **user_message** | `"이 태스크는 이미 완료되었거나 취소되었습니다."` |
| **발생 시점** | `completed` 또는 `cancelled` 상태의 태스크에 cancel 시도 |

```python
class TaskAlreadyTerminalError(OrchestratorError):
    error_code = "TASK_ALREADY_TERMINAL"
    http_status = 409
    retryable = False
    user_message = "이 태스크는 이미 완료되었거나 취소되었습니다."

    def __init__(self, *, task_id: str, current_status: str):
        super().__init__(
            f"Task {task_id} is already in terminal state: {current_status}",
        )
        self.task_id = task_id
        self.current_status = current_status
```

---

#### CyclicDependencyError

| 항목 | 값 |
|------|-----|
| **클래스** | `CyclicDependencyError(OrchestratorError)` |
| **error_code** | `"CYCLIC_DEPENDENCY"` |
| **http_status** | `400` |
| **retryable** | `False` |
| **user_message** | `"태스크 의존성에 순환이 감지되었습니다."` |
| **발생 시점** | 팀 프리셋의 `depends_on`에 순환 참조 존재 |

```python
class CyclicDependencyError(OrchestratorError):
    error_code = "CYCLIC_DEPENDENCY"
    http_status = 400
    retryable = False
    user_message = "태스크 의존성에 순환이 감지되었습니다."

    def __init__(self, *, cycle: list[str]):
        super().__init__(f"Cyclic dependency detected: {' -> '.join(cycle)}")
        self.cycle = cycle
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `cycle` | list[str] | 순환 경로 (예: `["A", "B", "C", "A"]`) |

---

### SynthesisError

| 항목 | 값 |
|------|-----|
| **클래스** | `SynthesisError(OrchestratorError)` |
| **error_code** | `"SYNTHESIS_FAILED"` |
| **http_status** | `500` |
| **retryable** | `True` |
| **user_message** | `"결과 종합에 실패했습니다."` |
| **발생 시점** | Synthesizer LLM 호출 실패 또는 출력 형식 오류 |

```python
class SynthesisError(OrchestratorError):
    error_code = "SYNTHESIS_FAILED"
    http_status = 500
    retryable = True
    user_message = "결과 종합에 실패했습니다."

    def __init__(
        self,
        message: str,
        *,
        strategy: str,
        input_count: int,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.strategy = strategy
        self.input_count = input_count
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `strategy` | str | 사용된 종합 전략 (`"narrative"` 등) |
| `input_count` | int | 종합 대상 결과 수 |

---

### AllProvidersFailedError

| 항목 | 값 |
|------|-----|
| **클래스** | `AllProvidersFailedError(OrchestratorError)` |
| **error_code** | `"ALL_PROVIDERS_FAILED"` |
| **http_status** | `502` |
| **retryable** | `False` |
| **user_message** | `"모든 CLI 프로바이더가 실패했습니다."` |
| **발생 시점** | 폴백 체인의 모든 CLI가 실패 |

```python
class AllProvidersFailedError(OrchestratorError):
    error_code = "ALL_PROVIDERS_FAILED"
    http_status = 502
    retryable = False
    user_message = "모든 CLI 프로바이더가 실패했습니다."

    def __init__(
        self,
        *,
        task_id: str,
        attempted: list[dict[str, str]],
    ):
        providers = [a["cli"] for a in attempted]
        super().__init__(
            f"All providers failed for task {task_id}: {providers}",
            details={"attempted": attempted},
        )
        self.task_id = task_id
        self.attempted = attempted
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `task_id` | str | 실패한 태스크 ID |
| `attempted` | list[dict] | 시도한 CLI별 에러 정보. 각 항목: `{"cli": "claude", "error_code": "CLI_TIMEOUT", "message": "..."}` |

---

### ValidationError

| 항목 | 값 |
|------|-----|
| **클래스** | `ValidationError(OrchestratorError)` |
| **error_code** | `"VALIDATION_ERROR"` |
| **http_status** | `400` |
| **retryable** | `False` |
| **user_message** | `"요청 형식이 올바르지 않습니다."` |
| **발생 시점** | API 요청 본문 유효성 검사 실패 (Pydantic ValidationError 래핑) |

```python
class ValidationError(OrchestratorError):
    error_code = "VALIDATION_ERROR"
    http_status = 400
    retryable = False
    user_message = "요청 형식이 올바르지 않습니다."

    def __init__(self, *, errors: list[dict[str, str]]):
        super().__init__(
            "Request validation failed",
            details={"validation_errors": errors},
        )
        self.errors = errors
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `errors` | list[dict] | 검증 에러 목록. 각 항목: `{"field": "task", "message": "필수 필드입니다"}` |

---

## 3. 에러 코드 레지스트리

모든 에러 코드의 전체 목록.

| 에러 코드 | 예외 클래스 | HTTP | 재시도 | 설명 |
|----------|------------|------|--------|------|
| `ORCHESTRATOR_ERROR` | OrchestratorError | 500 | No | 분류되지 않은 내부 오류 |
| `CLI_ERROR` | CLIError | 502 | Yes | CLI 일반 실행 오류 |
| `CLI_EXECUTION_ERROR` | CLIExecutionError | 502 | Yes* | CLI 비정상 종료 (*exit 137/139 제외) |
| `CLI_TIMEOUT` | CLITimeoutError | 504 | Yes | CLI 실행 타임아웃 |
| `CLI_PARSE_ERROR` | CLIParseError | 502 | Yes | CLI 출력 파싱 실패 |
| `CLI_NOT_FOUND` | CLINotFoundError | 503 | No | CLI 바이너리 없음 |
| `AUTH_ERROR` | AuthError | 401 | No | 인증 일반 오류 |
| `AUTH_MISSING_KEY` | AuthMissingKeyError | 503 | No | API 키 미설정 |
| `AUTH_INVALID_KEY` | AuthInvalidKeyError | 401 | No | API 키 무효 |
| `AUTH_QUOTA_EXCEEDED` | AuthQuotaExceededError | 429 | No | 할당량 초과 |
| `WORKTREE_ERROR` | WorktreeError | 500 | No | Worktree 일반 오류 |
| `WORKTREE_CREATE_FAILED` | WorktreeCreateError | 500 | Yes | Worktree 생성 실패 |
| `WORKTREE_CLEANUP_FAILED` | WorktreeCleanupError | 500 | No | Worktree 정리 실패 |
| `MERGE_CONFLICT` | MergeConflictError | 409 | No | Git 병합 충돌 |
| `DECOMPOSITION_FAILED` | DecompositionError | 500 | Yes | 태스크 분해 실패 |
| `PRESET_NOT_FOUND` | PresetNotFoundError | 404 | No | 프리셋 없음 |
| `PRESET_VALIDATION_ERROR` | PresetValidationError | 400 | No | 프리셋 형식 오류 |
| `PRESET_ALREADY_EXISTS` | PresetAlreadyExistsError | 409 | No | 프리셋 중복 |
| `TASK_NOT_FOUND` | TaskNotFoundError | 404 | No | 태스크 없음 |
| `TASK_NOT_RESUMABLE` | TaskNotResumableError | 409 | No | 태스크 재개 불가 |
| `TASK_ALREADY_TERMINAL` | TaskAlreadyTerminalError | 409 | No | 이미 종단 상태 |
| `CYCLIC_DEPENDENCY` | CyclicDependencyError | 400 | No | 순환 의존성 |
| `SYNTHESIS_FAILED` | SynthesisError | 500 | Yes | 결과 종합 실패 |
| `ALL_PROVIDERS_FAILED` | AllProvidersFailedError | 502 | No | 모든 프로바이더 실패 |
| `VALIDATION_ERROR` | ValidationError | 400 | No | 요청 검증 실패 |
| `REPO_NOT_FOUND` | (ValidationError 변형) | 404 | No | Git 저장소 경로 무효 |
| `ARTIFACT_NOT_FOUND` | (TaskNotFoundError 변형) | 404 | No | 아티팩트 파일 없음 |

---

## 4. 복구 전략

### 전략 유형 정의

| 전략 | 설명 | 적용 조건 |
|------|------|----------|
| **Retry** | 지수 백오프로 동일 작업 재시도 | `retryable == True` 이고 `retry_count < max_retries` |
| **Fallback** | 다른 CLI 프로바이더로 대체 실행 | CLIError 발생 시 `cli_priority` 목록의 다음 CLI로 시도 |
| **Escalate** | 파이프라인을 `failed` 상태로 전이 후 사용자에게 알림 | 모든 재시도/폴백 소진 |
| **Abort** | 즉시 실패. 재시도 없음 | `retryable == False` 이고 폴백 불가 |
| **Partial Continue** | 실패한 서브태스크를 제외하고 성공한 결과로 종합 진행 | 복수 서브태스크 중 일부만 실패 |

### 에러별 복구 전략 매핑

| 에러 코드 | 1차 전략 | 2차 전략 | 3차 전략 |
|----------|---------|---------|---------|
| `CLI_EXECUTION_ERROR` | Retry (지수 백오프) | Fallback (다음 CLI) | Escalate |
| `CLI_TIMEOUT` | Retry (타임아웃 1.5배 증가) | Fallback (다음 CLI) | Escalate |
| `CLI_PARSE_ERROR` | Retry (동일 CLI) | Fallback (다음 CLI) | Escalate |
| `CLI_NOT_FOUND` | Fallback (다음 CLI) | Escalate | — |
| `AUTH_MISSING_KEY` | Fallback (키 있는 CLI) | Abort | — |
| `AUTH_INVALID_KEY` | Abort | — | — |
| `AUTH_QUOTA_EXCEEDED` | Fallback (다른 프로바이더) | Escalate | — |
| `WORKTREE_CREATE_FAILED` | Retry (1회) | Abort | — |
| `MERGE_CONFLICT` | Escalate (사용자 알림) | — | — |
| `DECOMPOSITION_FAILED` | Retry (프롬프트 조정) | Abort | — |
| `SYNTHESIS_FAILED` | Retry (동일 입력) | Partial Continue | — |
| `ALL_PROVIDERS_FAILED` | Escalate | — | — |

### 재시도 설정

```python
class RetryConfig:
    """에러 유형별 재시도 설정."""

    max_retries: int = 3
    base_delay: float = 1.0        # 초
    max_delay: float = 60.0        # 초
    backoff_factor: float = 2.0    # 지수 배수
    jitter: float = 0.5            # 랜덤 범위 (0~jitter)
```

**재시도 대기 시간 계산:**

```
delay = min(base_delay * backoff_factor^attempt + random(0, jitter), max_delay)
```

| 시도 | 대기 시간 (base=1, factor=2) | 실제 범위 (jitter=0.5) |
|------|----------------------------|----------------------|
| 1회 | 1초 | 1.0 ~ 1.5초 |
| 2회 | 2초 | 2.0 ~ 2.5초 |
| 3회 | 4초 | 4.0 ~ 4.5초 |
| 4회 | 8초 | 8.0 ~ 8.5초 |
| 5회 | 16초 | 16.0 ~ 16.5초 |

### 폴백 체인

```python
class FallbackChain:
    """CLI 폴백 체인.

    cli_priority 순서대로 시도.
    현재 실패한 CLI를 제외하고 다음 CLI로 시도.
    """

    async def execute_with_fallback(
        self,
        prompt: str,
        cli_priority: list[str],  # ["claude", "codex", "gemini"]
        *,
        timeout: int = 300,
    ) -> AgentResult:
        attempted = []
        for cli in cli_priority:
            try:
                adapter = self._get_adapter(cli)
                return await adapter.execute(prompt, timeout=timeout)
            except CLIError as e:
                attempted.append({
                    "cli": cli,
                    "error_code": e.error_code,
                    "message": str(e),
                })
                continue

        raise AllProvidersFailedError(
            task_id=self._current_task_id,
            attempted=attempted,
        )
```

### 부분 실패 처리

N개 서브태스크 중 일부만 실패한 경우의 처리 규칙:

| 실패 비율 | 처리 | 근거 |
|----------|------|------|
| 0% (전부 성공) | 정상 종합 | — |
| 1~49% | Partial Continue: 성공 결과만으로 종합, 실패 태스크 표시 | 부분 결과도 가치 있음 |
| 50~99% | Escalate: 파이프라인 `failed`, 성공 결과는 보존 | 결과 신뢰도 부족 |
| 100% (전부 실패) | Escalate: 파이프라인 `failed` | 의미 있는 결과 없음 |

```python
async def _handle_execution_complete(self, pipeline: Pipeline) -> None:
    """실행 완료 후 종합 또는 실패 처리."""
    done_tasks = [t for t in pipeline.subtasks if t.state == "done"]
    failed_tasks = [t for t in pipeline.subtasks if t.state == "failed"]
    total = len(pipeline.subtasks)

    if not failed_tasks:
        # 전부 성공: 정상 종합
        await self._synthesize(pipeline, done_tasks)
    elif len(failed_tasks) / total < 0.5:
        # 부분 실패 (50% 미만): 성공 결과로 종합 + 경고
        await self._synthesize(pipeline, done_tasks, partial=True)
        self._event_bus.emit(Event(
            type="pipeline_completed",
            data={"partial": True, "failed_count": len(failed_tasks)},
        ))
    else:
        # 과반 실패: 파이프라인 실패
        pipeline.status = "failed"
        self._event_bus.emit(Event(
            type="pipeline_failed",
            data={
                "error_code": "PARTIAL_FAILURE",
                "error_message": f"{len(failed_tasks)}/{total} 서브태스크 실패",
            },
        ))
```

---

## 5. API 에러 응답 형식

### JSON Schema

```json
{
  "type": "object",
  "required": ["error"],
  "properties": {
    "error": {
      "type": "object",
      "required": ["code", "message"],
      "properties": {
        "code": {
          "type": "string",
          "description": "에러 코드 (에러 코드 레지스트리 참조)",
          "example": "TASK_NOT_FOUND"
        },
        "message": {
          "type": "string",
          "description": "사용자 표시용 메시지 (한국어)",
          "example": "태스크를 찾을 수 없습니다."
        },
        "details": {
          "type": "object",
          "description": "추가 정보 (에러별 상이)",
          "default": {}
        }
      }
    }
  }
}
```

### 변환 미들웨어

API 계층에서 `OrchestratorError`를 JSON 응답으로 변환하는 미들웨어:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

async def orchestrator_error_handler(request: Request, exc: OrchestratorError) -> JSONResponse:
    """OrchestratorError → JSON 에러 응답 변환."""
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.user_message,
                "details": exc.details,
            }
        },
    )

# FastAPI 등록
app.add_exception_handler(OrchestratorError, orchestrator_error_handler)
```

### 에러 응답 예시

#### 404 — 태스크 없음

```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "태스크를 찾을 수 없습니다.",
    "details": {}
  }
}
```

#### 400 — 요청 검증 실패

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "요청 형식이 올바르지 않습니다.",
    "details": {
      "validation_errors": [
        {
          "field": "task",
          "message": "필수 필드입니다"
        },
        {
          "field": "config.timeout",
          "message": "30 이상이어야 합니다"
        }
      ]
    }
  }
}
```

#### 409 — 상태 충돌

```json
{
  "error": {
    "code": "TASK_NOT_RESUMABLE",
    "message": "이 태스크는 재개할 수 없는 상태입니다.",
    "details": {}
  }
}
```

#### 502 — 모든 프로바이더 실패

```json
{
  "error": {
    "code": "ALL_PROVIDERS_FAILED",
    "message": "모든 CLI 프로바이더가 실패했습니다.",
    "details": {
      "attempted": [
        {
          "cli": "claude",
          "error_code": "CLI_TIMEOUT",
          "message": "Timeout after 300 seconds"
        },
        {
          "cli": "codex",
          "error_code": "CLI_EXECUTION_ERROR",
          "message": "Process exited with code 1"
        },
        {
          "cli": "gemini",
          "error_code": "AUTH_MISSING_KEY",
          "message": "API key not set for google: GOOGLE_API_KEY"
        }
      ]
    }
  }
}
```

#### 409 — 병합 충돌

```json
{
  "error": {
    "code": "MERGE_CONFLICT",
    "message": "Git 병합 충돌이 발생했습니다. 수동 해결이 필요합니다.",
    "details": {
      "source_branch": "agent/implementer-a1b2c3d4",
      "target_branch": "main",
      "conflicting_files": [
        "src/middleware/jwt.py",
        "src/config/settings.py"
      ]
    }
  }
}
```

#### 500 — 태스크 분해 실패

```json
{
  "error": {
    "code": "DECOMPOSITION_FAILED",
    "message": "태스크 분해에 실패했습니다. 태스크 설명을 더 구체적으로 작성해 보세요.",
    "details": {
      "task": "뭔가 해줘",
      "reason": "invalid_output"
    }
  }
}
```

---

## 6. 로깅 명세

### 로그 레벨별 기록 항목

| 레벨 | 기록 항목 | 예시 |
|------|----------|------|
| **DEBUG** | 모든 CLI 명령어 + 인자, subprocess stdin/stdout 원본, LangGraph 상태 전이, EventBus 발행 상세 | `DEBUG: CLI command: ['claude', '--bare', '-p', '...']` |
| **INFO** | 파이프라인 생성/완료, 서브태스크 상태 변경, 에이전트 할당, worktree 생성/정리, 프리셋 로딩 | `INFO: Pipeline created: 550e8400... task="JWT 인증 미들웨어 구현"` |
| **WARNING** | 재시도 발생, 폴백 발생, CLI 가용성 경고, 부분 실패, worktree 정리 실패 | `WARNING: CLI timeout, retrying (2/3): cli=claude task=a1b2c3d4` |
| **ERROR** | 서브태스크 최종 실패, 파이프라인 실패, 모든 프로바이더 실패, 분해 실패 | `ERROR: All providers failed: task=a1b2c3d4 attempted=[claude, codex, gemini]` |
| **CRITICAL** | 서버 시작 실패, 체크포인터 DB 오류, 이벤트 루프 크래시 | `CRITICAL: Checkpoint DB corrupted: checkpoints.db` |

### 구조화 로그 형식

structlog JSON 출력 형식:

```json
{
  "timestamp": "2026-04-05T14:30:05.123Z",
  "level": "warning",
  "event": "cli_retry",
  "logger": "orchestrator.core.executor.cli_executor",
  "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "cli": "claude",
  "attempt": 2,
  "max_retries": 3,
  "error_code": "CLI_TIMEOUT",
  "timeout_seconds": 300,
  "next_delay_seconds": 4.3
}
```

### 에러별 로그 출력

#### CLITimeoutError

```
WARNING: cli_timeout | pipeline_id=550e8400 task_id=a1b2c3d4 cli=claude timeout_seconds=300
WARNING: cli_retry | pipeline_id=550e8400 task_id=a1b2c3d4 cli=claude attempt=2 max_retries=3 next_delay=4.3s
```

#### CLIExecutionError

```
WARNING: cli_execution_error | pipeline_id=550e8400 task_id=a1b2c3d4 cli=codex exit_code=1 stderr="Error: ..."
```

#### AllProvidersFailedError

```
ERROR: all_providers_failed | pipeline_id=550e8400 task_id=a1b2c3d4 attempted=["claude(CLI_TIMEOUT)", "codex(CLI_EXECUTION_ERROR)", "gemini(AUTH_MISSING_KEY)"]
ERROR: pipeline_failed | pipeline_id=550e8400 error_code=ALL_PROVIDERS_FAILED subtask_id=a1b2c3d4
```

#### Fallback 발생

```
WARNING: cli_fallback | pipeline_id=550e8400 task_id=a1b2c3d4 from_cli=claude to_cli=codex reason=CLI_TIMEOUT
INFO: cli_fallback_success | pipeline_id=550e8400 task_id=a1b2c3d4 cli=codex
```

#### MergeConflictError

```
ERROR: merge_conflict | pipeline_id=550e8400 source=agent/implementer-a1b2c3d4 target=main files=["src/middleware/jwt.py", "src/config/settings.py"]
```

#### 파이프라인 생명주기

```
INFO: pipeline_created | pipeline_id=550e8400 task="JWT 인증 미들웨어 구현" team_preset=feature-team
INFO: decomposition_completed | pipeline_id=550e8400 subtask_count=3
INFO: team_composed | pipeline_id=550e8400 agents=["claude-architect", "codex-implementer", "gemini-reviewer"]
INFO: task_state_changed | pipeline_id=550e8400 task_id=a1b2c3d4 from=todo to=in_progress agent=claude-architect
INFO: agent_output | pipeline_id=550e8400 task_id=a1b2c3d4 agent=claude-architect artifact=subtask-a1b2c3d4/output.json
INFO: synthesis_completed | pipeline_id=550e8400 strategy=narrative
INFO: pipeline_completed | pipeline_id=550e8400 duration_seconds=312.5
```

### 민감 정보 마스킹

로그에 기록하지 않는 항목:

| 항목 | 처리 |
|------|------|
| API 키 | 절대 로그 불포함. 키 존재 여부만 `key_set=true/false` |
| CLI stdout 전문 | DEBUG 레벨에서만 기록. WARNING/ERROR에서는 마지막 500자만 |
| 프롬프트 원문 | DEBUG 레벨에서만 기록. INFO 이상에서는 최초 100자 + `...` |
| 사용자 코드 | 파일 경로만 기록, 내용 불포함 |

---

## 7. 사용자 표시 메시지

모든 에러의 사용자 표시 메시지 (한국어) 전체 목록.

| 에러 코드 | 사용자 메시지 |
|----------|-------------|
| `ORCHESTRATOR_ERROR` | 오케스트레이터 내부 오류가 발생했습니다. |
| `CLI_ERROR` | CLI 에이전트 실행 중 오류가 발생했습니다. |
| `CLI_EXECUTION_ERROR` | CLI 에이전트가 비정상 종료되었습니다. |
| `CLI_TIMEOUT` | CLI 에이전트 실행 시간이 초과되었습니다. |
| `CLI_PARSE_ERROR` | CLI 에이전트 출력을 해석할 수 없습니다. |
| `CLI_NOT_FOUND` | CLI 도구를 찾을 수 없습니다. 설치 여부를 확인하세요. |
| `AUTH_ERROR` | 인증 오류가 발생했습니다. |
| `AUTH_MISSING_KEY` | API 키가 설정되지 않았습니다. 환경변수를 확인하세요. |
| `AUTH_INVALID_KEY` | API 키가 유효하지 않습니다. 키를 확인하세요. |
| `AUTH_QUOTA_EXCEEDED` | API 할당량이 초과되었습니다. |
| `WORKTREE_ERROR` | Git worktree 작업 중 오류가 발생했습니다. |
| `WORKTREE_CREATE_FAILED` | Git worktree 생성에 실패했습니다. |
| `WORKTREE_CLEANUP_FAILED` | Git worktree 정리에 실패했습니다. 수동 확인이 필요합니다. |
| `MERGE_CONFLICT` | Git 병합 충돌이 발생했습니다. 수동 해결이 필요합니다. |
| `DECOMPOSITION_FAILED` | 태스크 분해에 실패했습니다. 태스크 설명을 더 구체적으로 작성해 보세요. |
| `PRESET_NOT_FOUND` | 프리셋을 찾을 수 없습니다. |
| `PRESET_VALIDATION_ERROR` | 프리셋 형식이 올바르지 않습니다. |
| `PRESET_ALREADY_EXISTS` | 동일한 이름의 프리셋이 이미 존재합니다. |
| `TASK_NOT_FOUND` | 태스크를 찾을 수 없습니다. |
| `TASK_NOT_RESUMABLE` | 이 태스크는 재개할 수 없는 상태입니다. |
| `TASK_ALREADY_TERMINAL` | 이 태스크는 이미 완료되었거나 취소되었습니다. |
| `CYCLIC_DEPENDENCY` | 태스크 의존성에 순환이 감지되었습니다. |
| `SYNTHESIS_FAILED` | 결과 종합에 실패했습니다. |
| `ALL_PROVIDERS_FAILED` | 모든 CLI 프로바이더가 실패했습니다. |
| `VALIDATION_ERROR` | 요청 형식이 올바르지 않습니다. |

---

## 8. 에러 흐름 다이어그램

### 흐름 1: CLI 타임아웃 → 재시도 → 폴백 → AllProvidersFailedError

```
AgentWorker                     FallbackChain                   EventBus
    │                               │                              │
    │─execute_with_fallback()──────▶│                              │
    │                               │                              │
    │                        [시도 1: claude]                       │
    │                               │─CLIAdapter("claude").run()   │
    │                               │   └─ subprocess timeout      │
    │                               │   └─ CLITimeoutError 발생    │
    │                               │                              │
    │                               │─── 재시도 1/3 ───            │
    │                               │   delay: 1.3초               │
    │                               │─CLIAdapter("claude").run()   │
    │                               │   └─ CLITimeoutError 발생    │
    │                               │                              │
    │                               │─── 재시도 2/3 ───            │
    │                               │   delay: 2.4초               │
    │                               │─CLIAdapter("claude").run()   │
    │                               │   └─ CLITimeoutError 발생    │
    │                               │                              │
    │                               │─── 재시도 3/3 소진 ───       │
    │                               │─emit(agent_error)───────────▶│
    │                               │                              │
    │                        [시도 2: codex (폴백)]                 │
    │                               │─emit(agent_fallback)────────▶│
    │                               │─CLIAdapter("codex").run()    │
    │                               │   └─ CLIExecutionError(137)  │
    │                               │   └─ retryable=False (OOM)   │
    │                               │─emit(agent_error)───────────▶│
    │                               │                              │
    │                        [시도 3: gemini (폴백)]                │
    │                               │─emit(agent_fallback)────────▶│
    │                               │─CLIAdapter("gemini").run()   │
    │                               │   └─ AuthMissingKeyError     │
    │                               │   └─ retryable=False         │
    │                               │─emit(agent_error)───────────▶│
    │                               │                              │
    │                        [모든 프로바이더 소진]                  │
    │◀─AllProvidersFailedError──────│                              │
    │                                                              │
    │─mark_failed()────▶TaskBoard                                  │
    │                    │─emit(task_state_changed: failed)────────▶│
    │                                                              │
    │   (retry_count >= max_retries이면)                           │
    │   Pipeline.status = "failed"                                 │
    │─emit(pipeline_failed)───────────────────────────────────────▶│
```

### 흐름 2: 태스크 분해 실패 → 재시도 → 성공

```
Engine                          TaskDecomposer              LLM
   │                                │                        │
   │─decompose(task, team)─────────▶│                        │
   │                                │─LLM 호출 (1차)────────▶│
   │                                │◀─ 빈 응답 ─────────────│
   │                                │                        │
   │                                │ DecompositionError      │
   │                                │   reason: "empty_result"│
   │                                │   retryable: True       │
   │                                │                        │
   │                                │─── 재시도 1/3 ───       │
   │                                │   프롬프트 보강:         │
   │                                │   "서브태스크를 최소     │
   │                                │    2개 이상 생성하세요"  │
   │                                │─LLM 호출 (2차)────────▶│
   │                                │◀─ 유효한 서브태스크 ────│
   │                                │                        │
   │◀─subtasks (성공)───────────────│                        │
```

### 흐름 3: 부분 실패 → Partial Continue

```
Engine                  Board               Synthesizer          EventBus
   │                      │                      │                  │
   │                      │  서브태스크 3개 중:    │                  │
   │                      │  [A] done             │                  │
   │                      │  [B] done             │                  │
   │                      │  [C] failed (3/3 retry 소진)            │
   │                      │                      │                  │
   │◀─execution_complete──│                      │                  │
   │                      │                      │                  │
   │  실패 비율: 1/3 = 33% (< 50%)               │                  │
   │  → Partial Continue 전략                     │                  │
   │                      │                      │                  │
   │─synthesize([A,B], partial=True)────────────▶│                  │
   │                      │                      │─LLM 종합         │
   │                      │                      │  (실패 태스크     │
   │                      │                      │   명시 포함)      │
   │◀─final_result (partial)─────────────────────│                  │
   │                      │                      │                  │
   │  Pipeline.status = "completed"               │                  │
   │  Pipeline.result = "...(일부 태스크 미완료)" │                  │
   │─emit(pipeline_completed, partial=True)───────────────────────▶│
```

### 흐름 4: resume (체크포인트 복구)

```
Client              API              Engine           Checkpointer    Board
   │                 │                 │                  │              │
   │─POST /resume───▶│                │                  │              │
   │                 │─resume_task()─▶│                  │              │
   │                 │                │                  │              │
   │                 │                │  Pipeline.status == "failed" ✓  │
   │                 │                │                  │              │
   │                 │                │─load_checkpoint()▶│              │
   │                 │                │◀─last_state───────│              │
   │                 │                │                  │              │
   │                 │                │  마지막 성공 노드: submit_to_board
   │                 │                │  → Execution Phase부터 재개     │
   │                 │                │                  │              │
   │                 │                │─reset_failed()────────────────▶│
   │                 │                │                  │  [C] failed  │
   │                 │                │                  │    → todo    │
   │                 │                │                  │  retry_count │
   │                 │                │                  │    = 0 (리셋)│
   │                 │                │                  │              │
   │                 │                │  Pipeline.status = "running"    │
   │◀─200 Pipeline───│               │                  │              │
   │                 │                │                  │              │
   │                 │                │  Workers 재시작 → 정상 실행 흐름│
```
