"""CodexAdapter — Codex CLI wrapper."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import structlog

from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.errors.exceptions import CLIExecutionError, CLIParseError
from orchestrator.core.models.schemas import AdapterConfig, AgentResult

logger = structlog.get_logger()


def _toml_value(val: object) -> str:
    """Python 값을 TOML 리터럴 문자열로 변환한다."""
    if isinstance(val, str):
        return json.dumps(val)  # JSON 문자열 이스케이프는 TOML과 호환
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, list):
        items = ", ".join(json.dumps(item) if isinstance(item, str) else str(item) for item in val)
        return f"[{items}]"
    return json.dumps(str(val))


class CodexAdapter(CLIAdapter):
    """Codex CLI 어댑터.

    ``codex exec --json --full-auto "prompt"`` 형태로 실행한다.
    --ephemeral 사용 금지: worktree cwd에서 직접 파일 생성해야 함.
    JSONL 출력을 파싱하여 item.completed 또는 turn.completed 이벤트를 찾는다.
    """

    cli_name: str = "codex"

    def _get_api_key_env_var(self) -> str:
        return "OPENAI_API_KEY"

    def _prepare_mcp_workspace(
        self,
        config: AdapterConfig,
    ) -> tuple[str | None, dict[str, str]]:
        """Codex는 ~/.codex 복사본 + config.toml MCP 교체."""
        if not config.mcp_servers:
            return None, {}

        import tomllib

        codex_home = Path.home() / ".codex"
        if not codex_home.exists():
            return None, {}

        # 복사본 생성
        workspace = tempfile.mkdtemp(prefix="codex-mcp-")
        codex_copy = Path(workspace) / ".codex-home"
        shutil.copytree(codex_home, codex_copy)

        # config.toml에서 기존 mcp_servers 제거 + 새 MCP 추가
        config_path = codex_copy / "config.toml"
        if config_path.exists():
            cfg = tomllib.loads(config_path.read_text())
        else:
            cfg = {}

        # 기존 mcp_servers 섹션 제거
        cfg.pop("mcp_servers", None)

        # 새 MCP 서버 설정 추가 후 TOML 직렬화
        mcp_section: dict[str, dict[str, object]] = {}
        for name, sd in config.mcp_servers.items():
            mcp_section[name] = {
                "command": sd.command,
                "args": sd.args,
            }
        cfg["mcp_servers"] = mcp_section

        config_path.write_text(self._serialize_toml(cfg))

        return None, {"CODEX_HOME": str(codex_copy)}

    @staticmethod
    def _serialize_toml(data: dict[str, object]) -> str:
        """간단한 TOML 직렬화 (codex config.toml용).

        중첩 테이블과 기본 타입(str, int, bool, list[str])을 지원한다.
        """
        lines: list[str] = []
        # 먼저 최상위 스칼라 키 출력
        for key, val in data.items():
            if not isinstance(val, dict):
                lines.append(f"{key} = {_toml_value(val)}")
        # 그 다음 테이블 섹션 출력
        for key, val in data.items():
            if isinstance(val, dict):
                for sub_key, sub_val in val.items():
                    if isinstance(sub_val, dict):
                        lines.append(f"\n[{key}.{sub_key}]")
                        for k, v in sub_val.items():
                            lines.append(f"{k} = {_toml_value(v)}")
                    else:
                        if not any(
                            ln.strip() == f"[{key}]" for ln in lines
                        ):
                            lines.append(f"\n[{key}]")
                        lines.append(f"{sub_key} = {_toml_value(sub_val)}")
        return "\n".join(lines) + "\n"

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
