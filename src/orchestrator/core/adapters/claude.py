"""ClaudeAdapter — Claude Code CLI wrapper."""

from __future__ import annotations

import json

import structlog

from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.errors.exceptions import CLIExecutionError, CLIParseError
from orchestrator.core.models.schemas import AdapterConfig, AgentResult
from orchestrator.core.presets.models import MCPServerDef

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

        stream-json + --verbose 조합으로 JSONL 실시간 스트리밍을 활성화한다.
        Note: --bare is intentionally not used; it can produce
        unstable output in certain scenarios.
        """
        cmd = [
            self.cli_name,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
        ]

        # MCP 주입: --mcp-config + --strict-mcp-config
        mcp_json = self._build_mcp_config_json(config.mcp_servers)
        cmd.extend(["--mcp-config", mcp_json, "--strict-mcp-config"])

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])
        if config.model:
            cmd.extend(["--model", config.model])
        cmd.extend(config.extra_args)
        return cmd

    @staticmethod
    def _build_mcp_config_json(
        mcp_servers: dict[str, MCPServerDef],
    ) -> str:
        """MCPServerDef → Claude --mcp-config용 JSON 문자열."""
        servers: dict[str, dict[str, object]] = {}
        for name, server_def in mcp_servers.items():
            entry: dict[str, object] = {"command": server_def.command}
            if server_def.args:
                entry["args"] = server_def.args
            if server_def.env:
                entry["env"] = server_def.env
            servers[name] = entry
        return json.dumps({"mcpServers": servers})

    def _parse_output(self, stdout: str, stderr: str) -> AgentResult:
        """Claude stream-json JSONL 출력을 파싱한다.

        이벤트 흐름: system(init) → assistant → rate_limit_event → result
        result 이벤트에서 최종 출력을 추출한다.
        """
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
                output_parts.append(line)
                continue

            event_type = event.get("type", "")

            if event_type == "result":
                result_text = event.get("result", "")
                if result_text:
                    output_parts.append(str(result_text))
                if event.get("is_error", False):
                    error_msg = event.get("result", "Unknown Claude error")
                    raise CLIExecutionError(
                        f"Claude returned error: {error_msg}",
                        cli=self.cli_name,
                        stdout=stdout[:2000],
                        stderr=stderr[:2000],
                    )

            elif event_type == "assistant":
                message = event.get("message", {})
                content = message.get("content", []) if isinstance(message, dict) else []
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text = c.get("text", "")
                            if text:
                                output_parts.append(str(text))

            usage = event.get("usage", {})
            if isinstance(usage, dict):
                tokens += int(
                    usage.get("total_tokens", usage.get("output_tokens", 0))
                )

        final_output = "\n".join(output_parts) if output_parts else stdout.strip()
        return AgentResult(
            output=final_output,
            tokens_used=tokens,
            raw={"events": raw_events[:50]},
        )
