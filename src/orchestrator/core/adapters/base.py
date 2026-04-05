"""CLIAdapter abstract base class."""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from subprocess import DEVNULL

import structlog

from orchestrator.core.errors.exceptions import CLITimeoutError
from orchestrator.core.models.schemas import AdapterConfig, AgentResult

logger = structlog.get_logger()

_NPM_BIN = "/home/yoon/.local/npm/bin"


class CLIAdapter(ABC):
    """CLI subprocess 래퍼 추상 기본 클래스.

    모든 CLI 어댑터(Claude, Codex, Gemini)는 이 ABC를 상속한다.
    run()으로 CLI를 실행하고, health_check()로 가용성을 확인한다.
    """

    cli_name: str  # 서브클래스에서 정의 ("claude" | "codex" | "gemini")

    @abstractmethod
    def _build_command(
        self,
        prompt: str,
        config: AdapterConfig,
        *,
        system_prompt: str | None = None,
    ) -> list[str]:
        """CLI 명령어를 구성한다.

        Args:
            prompt: 에이전트에 전달할 프롬프트.
            config: 어댑터 설정.
            system_prompt: 시스템 프롬프트 (페르소나).

        Returns:
            명령어 리스트.
        """
        ...

    @abstractmethod
    def _parse_output(self, stdout: str, stderr: str) -> AgentResult:
        """CLI 출력을 AgentResult로 파싱한다.

        Args:
            stdout: 표준 출력.
            stderr: 표준 에러.

        Returns:
            파싱된 AgentResult.
        """
        ...

    def _build_env(self, config: AdapterConfig) -> dict[str, str]:
        """subprocess 환경 변수를 구성한다.

        Args:
            config: 어댑터 설정.

        Returns:
            환경 변수 딕셔너리.
        """
        env = {**os.environ}
        # npm bin 경로를 PATH에 추가
        current_path = env.get("PATH", "")
        if _NPM_BIN not in current_path:
            env["PATH"] = f"{_NPM_BIN}:{current_path}"
        # API 키 설정
        if config.api_key is not None:
            key = config.api_key.get_secret_value()
            env_var_name = self._get_api_key_env_var()
            env[env_var_name] = key
        # 추가 환경 변수
        env.update(config.env)
        return env

    @abstractmethod
    def _get_api_key_env_var(self) -> str:
        """API 키 환경 변수 이름을 반환한다.

        Returns:
            환경 변수 이름 (예: "ANTHROPIC_API_KEY").
        """
        ...

    async def run(
        self,
        prompt: str,
        config: AdapterConfig,
        *,
        system_prompt: str | None = None,
    ) -> AgentResult:
        """CLI subprocess를 실행하여 결과를 반환한다.

        Args:
            prompt: 에이전트에 전달할 프롬프트.
            config: 어댑터 설정.
            system_prompt: 시스템 프롬프트 (페르소나).

        Returns:
            실행 결과.

        Raises:
            CLITimeoutError: 타임아웃 초과.
            CLIExecutionError: 프로세스 비정상 종료.
            CLIParseError: 출력 파싱 실패.
        """
        cmd = self._build_command(prompt, config, system_prompt=system_prompt)
        env = self._build_env(config)
        cwd = config.working_dir

        log = logger.bind(cli=self.cli_name, cmd=cmd[:3])
        log.info("cli_executing")

        start_time = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=DEVNULL,
            env=env,
            cwd=cwd,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=config.timeout,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            raise CLITimeoutError(
                f"{self.cli_name} timed out after {config.timeout}s",
                cli=self.cli_name,
                timeout_seconds=config.timeout,
            ) from None

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        stdout_str = stdout_bytes.decode() if stdout_bytes else ""
        stderr_str = stderr_bytes.decode() if stderr_bytes else ""

        result = self._parse_output(stdout_str, stderr_str)
        result = result.model_copy(
            update={
                "exit_code": proc.returncode or 0,
                "duration_ms": elapsed_ms,
            },
        )
        log.info("cli_completed", exit_code=proc.returncode, duration_ms=elapsed_ms)
        return result

    async def health_check(self) -> bool:
        """CLI 바이너리 존재 여부를 확인한다.

        Returns:
            가용하면 True.
        """
        env = {**os.environ}
        current_path = env.get("PATH", "")
        if _NPM_BIN not in current_path:
            env["PATH"] = f"{_NPM_BIN}:{current_path}"
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_name,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=DEVNULL,
                env=env,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            return proc.returncode == 0
        except (FileNotFoundError, TimeoutError, OSError):
            return False
