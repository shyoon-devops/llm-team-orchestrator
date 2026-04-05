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

    ``claude --bare -p "prompt" --output-format json`` 형태로 실행한다.
    """

    cli_name: str = "claude"

    def _get_api_key_env_var(self) -> str:
        return "ANTHROPIC_API_KEY"

    def _build_command(
        self,
        prompt: str,
        config: AdapterConfig,
        *,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Claude CLI 명령어를 구성한다."""
        cmd = [
            self.cli_name,
            "--bare",
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
            # --bare mode may output plain text
            return AgentResult(output=stdout.strip(), raw={"raw_stdout": stdout[:2000]})

        # Claude JSON output contains a 'result' field
        if isinstance(data, dict):
            output_text = data.get("result", data.get("output", stdout.strip()))
            return AgentResult(
                output=str(output_text),
                tokens_used=data.get("num_tokens", 0),
                raw=data,
            )

        return AgentResult(output=stdout.strip(), raw={"raw_stdout": stdout[:2000]})
