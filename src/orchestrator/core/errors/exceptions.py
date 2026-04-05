"""Orchestrator exception hierarchy."""

from __future__ import annotations

from typing import Any

# ============================================================
# Root
# ============================================================


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
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


# ============================================================
# CLI errors
# ============================================================


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
        cli: str,
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.cli = cli
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class CLIExecutionError(CLIError):
    """CLI 프로세스가 비정상 종료."""

    error_code: str = "CLI_EXECUTION_ERROR"
    user_message: str = "CLI 에이전트가 비정상 종료되었습니다."

    @property
    def retryable(self) -> bool:  # type: ignore[override]
        """OOM(137), segfault(139)는 재시도 불가."""
        return self.exit_code not in (137, 139)


class CLITimeoutError(CLIError):
    """CLI 실행 타임아웃."""

    error_code: str = "CLI_TIMEOUT"
    http_status: int = 504
    retryable: bool = True
    user_message: str = "CLI 에이전트 실행 시간이 초과되었습니다."

    def __init__(
        self,
        message: str,
        *,
        cli: str,
        timeout_seconds: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, cli=cli, **kwargs)
        self.timeout_seconds = timeout_seconds


class CLIParseError(CLIError):
    """CLI 출력 파싱 실패."""

    error_code: str = "CLI_PARSE_ERROR"
    retryable: bool = True
    user_message: str = "CLI 에이전트 출력을 해석할 수 없습니다."

    def __init__(
        self,
        message: str,
        *,
        cli: str,
        raw_output: str,
        expected_format: str = "json",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, cli=cli, **kwargs)
        self.raw_output = raw_output[:2000]
        self.expected_format = expected_format


class CLINotFoundError(CLIError):
    """CLI 바이너리 없음."""

    error_code: str = "CLI_NOT_FOUND"
    http_status: int = 503
    retryable: bool = False
    user_message: str = "CLI 도구를 찾을 수 없습니다. 설치 여부를 확인하세요."


# ============================================================
# Auth errors
# ============================================================


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
        provider: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.provider = provider


class AuthMissingKeyError(AuthError):
    """API 키 미설정."""

    error_code: str = "AUTH_MISSING_KEY"
    http_status: int = 503
    retryable: bool = False
    user_message: str = "API 키가 설정되지 않았습니다. 환경변수를 확인하세요."

    def __init__(self, *, provider: str, env_var: str) -> None:
        super().__init__(
            f"API key not set for {provider}: {env_var}",
            provider=provider,
        )
        self.env_var = env_var


class AuthInvalidKeyError(AuthError):
    """API 키 무효."""

    error_code: str = "AUTH_INVALID_KEY"
    http_status: int = 401
    retryable: bool = False
    user_message: str = "API 키가 유효하지 않습니다. 키를 확인하세요."


class AuthQuotaExceededError(AuthError):
    """할당량 초과."""

    error_code: str = "AUTH_QUOTA_EXCEEDED"
    http_status: int = 429
    retryable: bool = False
    user_message: str = "API 할당량이 초과되었습니다."


# ============================================================
# Worktree errors
# ============================================================


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
    ) -> None:
        super().__init__(message, details=details)
        self.repo_path = repo_path
        self.branch = branch


class WorktreeCreateError(WorktreeError):
    """worktree 생성 실패."""

    error_code: str = "WORKTREE_CREATE_FAILED"
    retryable: bool = True
    user_message: str = "Git worktree 생성에 실패했습니다."


class WorktreeCleanupError(WorktreeError):
    """worktree 정리 실패."""

    error_code: str = "WORKTREE_CLEANUP_FAILED"
    retryable: bool = False
    user_message: str = "Git worktree 정리에 실패했습니다. 수동 확인이 필요합니다."


# ============================================================
# Merge conflict
# ============================================================


class MergeConflictError(OrchestratorError):
    """Git 병합 충돌."""

    error_code: str = "MERGE_CONFLICT"
    http_status: int = 409
    retryable: bool = False
    user_message: str = "Git 병합 충돌이 발생했습니다. 수동 해결이 필요합니다."

    def __init__(
        self,
        message: str,
        *,
        source_branch: str,
        target_branch: str,
        conflicting_files: list[str],
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.source_branch = source_branch
        self.target_branch = target_branch
        self.conflicting_files = conflicting_files


# ============================================================
# Decomposition
# ============================================================


class DecompositionError(OrchestratorError):
    """태스크 분해 실패."""

    error_code: str = "DECOMPOSITION_FAILED"
    http_status: int = 500
    retryable: bool = True
    user_message: str = "태스크 분해에 실패했습니다. 태스크 설명을 더 구체적으로 작성해 보세요."

    def __init__(
        self,
        message: str,
        *,
        task: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.task = task
        self.reason = reason


# ============================================================
# Preset errors
# ============================================================


class PresetNotFoundError(OrchestratorError):
    """프리셋 없음."""

    error_code: str = "PRESET_NOT_FOUND"
    http_status: int = 404
    retryable: bool = False
    user_message: str = "프리셋을 찾을 수 없습니다."

    def __init__(self, *, preset_name: str, preset_type: str = "agent") -> None:
        super().__init__(f"{preset_type} preset not found: {preset_name}")
        self.preset_name = preset_name
        self.preset_type = preset_type


class PresetValidationError(OrchestratorError):
    """프리셋 형식 오류."""

    error_code: str = "PRESET_VALIDATION_ERROR"
    http_status: int = 400
    retryable: bool = False
    user_message: str = "프리셋 형식이 올바르지 않습니다."

    def __init__(self, *, preset_name: str, errors: list[dict[str, str]]) -> None:
        super().__init__(f"Preset validation failed: {preset_name}")
        self.preset_name = preset_name
        self.errors = errors


class PresetAlreadyExistsError(OrchestratorError):
    """중복 프리셋 이름."""

    error_code: str = "PRESET_ALREADY_EXISTS"
    http_status: int = 409
    retryable: bool = False
    user_message: str = "동일한 이름의 프리셋이 이미 존재합니다."

    def __init__(self, *, preset_name: str, preset_type: str = "agent") -> None:
        super().__init__(f"{preset_type} preset already exists: {preset_name}")
        self.preset_name = preset_name
        self.preset_type = preset_type


# ============================================================
# Board errors
# ============================================================


class TaskNotFoundError(OrchestratorError):
    """태스크 없음."""

    error_code: str = "TASK_NOT_FOUND"
    http_status: int = 404
    retryable: bool = False
    user_message: str = "태스크를 찾을 수 없습니다."

    def __init__(self, *, task_id: str) -> None:
        super().__init__(f"Task not found: {task_id}")
        self.task_id = task_id


class TaskNotResumableError(OrchestratorError):
    """재개 불가 상태."""

    error_code: str = "TASK_NOT_RESUMABLE"
    http_status: int = 409
    retryable: bool = False
    user_message: str = "이 태스크는 재개할 수 없는 상태입니다."

    def __init__(self, *, task_id: str, current_status: str) -> None:
        super().__init__(
            f"Task {task_id} cannot be resumed from status: {current_status}",
        )
        self.task_id = task_id
        self.current_status = current_status


class TaskAlreadyTerminalError(OrchestratorError):
    """이미 종단 상태."""

    error_code: str = "TASK_ALREADY_TERMINAL"
    http_status: int = 409
    retryable: bool = False
    user_message: str = "이 태스크는 이미 완료되었거나 취소되었습니다."

    def __init__(self, *, task_id: str, current_status: str) -> None:
        super().__init__(
            f"Task {task_id} is already in terminal state: {current_status}",
        )
        self.task_id = task_id
        self.current_status = current_status


class CyclicDependencyError(OrchestratorError):
    """순환 의존성."""

    error_code: str = "CYCLIC_DEPENDENCY"
    http_status: int = 400
    retryable: bool = False
    user_message: str = "태스크 의존성에 순환이 감지되었습니다."

    def __init__(self, *, cycle: list[str]) -> None:
        super().__init__(f"Cyclic dependency detected: {' -> '.join(cycle)}")
        self.cycle = cycle


# ============================================================
# Synthesis
# ============================================================


class SynthesisError(OrchestratorError):
    """결과 종합 실패."""

    error_code: str = "SYNTHESIS_FAILED"
    http_status: int = 500
    retryable: bool = True
    user_message: str = "결과 종합에 실패했습니다."

    def __init__(
        self,
        message: str,
        *,
        strategy: str,
        input_count: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.strategy = strategy
        self.input_count = input_count


# ============================================================
# All providers failed
# ============================================================


class AllProvidersFailedError(OrchestratorError):
    """모든 CLI 폴백 실패."""

    error_code: str = "ALL_PROVIDERS_FAILED"
    http_status: int = 502
    retryable: bool = False
    user_message: str = "모든 CLI 에이전트가 실패했습니다."
