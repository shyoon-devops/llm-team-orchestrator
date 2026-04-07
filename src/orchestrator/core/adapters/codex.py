"""CodexAdapter — Codex CLI wrapper."""

from __future__ import annotations

import json

import structlog

from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.errors.exceptions import CLIExecutionError, CLIParseError
from orchestrator.core.models.schemas import AdapterConfig, AgentResult

logger = structlog.get_logger()


class CodexAdapter(CLIAdapter):
    """Codex CLI 어댑터.

    ``codex exec --json --full-auto "prompt"`` 형태로 실행한다.
    --ephemeral 사용 금지: worktree cwd에서 직접 파일 생성해야 함.
    JSONL 출력을 파싱하여 item.completed 또는 turn.completed 이벤트를 찾는다.
    """

    cli_name: str = "codex"

    def _get_api_key_env_var(self) -> str:
        return "OPENAI_API_KEY"

    def _build_command(
        self,
        prompt: str,
        config: AdapterConfig,
        *,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Codex CLI 명령어를 구성한다."""
        cmd = [
            self.cli_name,
            "exec",
            "--json",
            "--full-auto",
        ]
        if config.model:
            cmd.extend(["--model", config.model])
        cmd.extend(config.extra_args)
        # system prompt is prepended to the prompt for codex
        if system_prompt:
            cmd.append(f"{system_prompt}\n\n{prompt}")
        else:
            cmd.append(prompt)
        return cmd

    def _parse_output(self, stdout: str, stderr: str) -> AgentResult:
        """Codex JSONL 출력을 파싱한다.

        JSONL 형식에서 item.completed 또는 turn.completed 이벤트를 찾는다.
        """
        if not stdout.strip():
            if stderr.strip():
                raise CLIExecutionError(
                    f"Codex produced no stdout, stderr: {stderr[:500]}",
                    cli=self.cli_name,
                    stderr=stderr[:2000],
                )
            raise CLIParseError(
                "Codex produced empty output",
                cli=self.cli_name,
                raw_output="",
                expected_format="json",
            )

        output_parts: list[str] = []
        tokens = 0
        raw_events: list[dict[str, object]] = []

        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                raw_events.append(event)
            except json.JSONDecodeError:
                output_parts.append(line)
                continue

            event_type = event.get("type", "")

            # error / turn.failed → 즉시 에러 raise
            if event_type == "error":
                error_msg = event.get("message", "Unknown Codex error")
                raise CLIExecutionError(
                    f"Codex error: {error_msg}",
                    cli=self.cli_name,
                    stdout=stdout[:2000],
                    stderr=stderr[:2000],
                )
            if event_type == "turn.failed":
                error_info = event.get("error", {})
                error_msg = error_info.get("message", "Turn failed") if isinstance(error_info, dict) else str(error_info)
                raise CLIExecutionError(
                    f"Codex turn failed: {error_msg}",
                    cli=self.cli_name,
                    stdout=stdout[:2000],
                    stderr=stderr[:2000],
                )

            if event_type in ("item.completed", "turn.completed"):
                item = event.get("item", {})
                if isinstance(item, dict):
                    content = item.get("content", "")
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "text":
                                output_parts.append(str(c.get("text", "")))
                    elif isinstance(content, str):
                        output_parts.append(content)

            usage = event.get("usage", {})
            if isinstance(usage, dict):
                tokens += int(usage.get("total_tokens", 0))

        final_output = "\n".join(output_parts) if output_parts else stdout.strip()
        return AgentResult(
            output=final_output,
            tokens_used=tokens,
            raw={"events": raw_events[:50]},
        )
