"""GeminiAdapter — Gemini CLI wrapper."""

from __future__ import annotations

import json

import structlog

from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.errors.exceptions import CLIExecutionError, CLIParseError
from orchestrator.core.models.schemas import AdapterConfig, AgentResult

logger = structlog.get_logger()


class GeminiAdapter(CLIAdapter):
    """Gemini CLI 어댑터.

    ``gemini -p "prompt" --output-format stream-json --sandbox=none --yolo``
    형태로 실행한다.
    stream-json 출력에서 'result' 이벤트만 필터링한다.
    """

    cli_name: str = "gemini"

    def _get_api_key_env_var(self) -> str:
        return "GEMINI_API_KEY"

    def _build_command(
        self,
        prompt: str,
        config: AdapterConfig,
        *,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Gemini CLI 명령어를 구성한다."""
        # system prompt is prepended to the prompt for gemini
        final_prompt = prompt
        if system_prompt:
            final_prompt = f"{system_prompt}\n\n{prompt}"

        cmd = [
            self.cli_name,
            "-p",
            final_prompt,
            "--output-format",
            "stream-json",
            "--sandbox=none",
            "--yolo",
        ]
        if config.model:
            cmd.extend(["--model", config.model])
        cmd.extend(config.extra_args)
        return cmd

    def _parse_output(self, stdout: str, stderr: str) -> AgentResult:
        """Gemini stream-json 출력을 파싱한다.

        stdout 오염 버그 (#21433) 대응: 'result' 이벤트만 필터링한다.
        """
        if not stdout.strip():
            if stderr.strip():
                raise CLIExecutionError(
                    f"Gemini produced no stdout, stderr: {stderr[:500]}",
                    cli=self.cli_name,
                    stderr=stderr[:2000],
                )
            raise CLIParseError(
                "Gemini produced empty output",
                cli=self.cli_name,
                raw_output="",
                expected_format="stream-json",
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
                continue

            event_type = event.get("type", "")
            # Filter for result and message events only (ignore stdout pollution)
            if event_type == "result":
                text = event.get("text", event.get("output", ""))
                if text:
                    output_parts.append(str(text))
            elif event_type == "message":
                text = event.get("text", event.get("content", ""))
                if text:
                    output_parts.append(str(text))

            usage = event.get("usage", {})
            if isinstance(usage, dict):
                tokens += int(usage.get("total_tokens", 0))

        final_output = "\n".join(output_parts) if output_parts else stdout.strip()
        return AgentResult(
            output=final_output,
            tokens_used=tokens,
            raw={"events": raw_events[:50]},
        )
