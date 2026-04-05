"""ClaudeAdapter — Claude Code CLI wrapper."""

from __future__ import annotations

import json

import structlog

from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.errors.exceptions import CLIExecutionError, CLIParseError
from orchestrator.core.models.schemas import AdapterConfig, AgentResult

logger = structlog.get_logger()


class ClaudeAdapter(CLIAdapter):
    """Claude Code CLI 어댑터.

    ``claude -p "prompt" --output-format json --permission-mode bypassPermissions``
    형태로 실행한다. firstParty 인증 사용 (API 키 불필요).

    Note: --bare는 사용하지 않는다 — JSON 출력이 불안정해질 수 있음.
    """

    cli_name: str = "claude"

    def _get_api_key_env_var(self) -> str:
        # Claude Code uses firstParty auth (no API key needed),
        # but we still set this for fallback/proxy scenarios.
        return "ANTHROPIC_API_KEY"

    def _build_command(
        self,
        prompt: str,
        config: AdapterConfig,
        *,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Claude CLI 명령어를 구성한다.

        Note: --bare is intentionally not used; it can produce
        unstable output in certain scenarios.
        """
        cmd = [
            self.cli_name,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--permission-mode",
            "bypassPermissions",
        ]
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])
        if config.model:
            cmd.extend(["--model", config.model])
        cmd.extend(config.extra_args)
        return cmd

    def _parse_output(self, stdout: str, stderr: str) -> AgentResult:
        """Claude CLI JSON 출력을 파싱한다."""
        if not stdout.strip():
            if stderr.strip():
                raise CLIExecutionError(
                    f"Claude produced no stdout, stderr: {stderr[:500]}",
                    cli=self.cli_name,
                    stderr=stderr[:2000],
                )
            raise CLIParseError(
                "Claude produced empty output",
                cli=self.cli_name,
                raw_output="",
                expected_format="json",
            )

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            # Plain text output (fallback)
            return AgentResult(output=stdout.strip(), raw={"raw_stdout": stdout[:2000]})

        # Claude JSON output: check for is_error flag
        if isinstance(data, dict):
            if data.get("is_error", False):
                error_msg = data.get("result", data.get("error", "Unknown Claude error"))
                raise CLIExecutionError(
                    f"Claude returned error: {error_msg}",
                    cli=self.cli_name,
                    stdout=stdout[:2000],
                    stderr=stderr[:2000],
                )
            output_text = data.get("result", data.get("output", stdout.strip()))
            return AgentResult(
                output=str(output_text),
                tokens_used=data.get("num_tokens", 0),
                raw=data,
            )

        return AgentResult(output=stdout.strip(), raw={"raw_stdout": stdout[:2000]})
