"""Codex CLI adapter."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from orchestrator.adapters.base import CLIAdapter
from orchestrator.errors.exceptions import CLIExecutionError, CLIParseError, CLITimeoutError
from orchestrator.models.schemas import AgentResult

_NPM_BIN = "/home/yoon/.local/npm/bin"


class CodexAdapter(CLIAdapter):
    """Adapter for OpenAI Codex CLI (headless mode).

    Real JSONL output format (codex exec --full-auto --json "prompt"):
        {"type":"item.completed","item":{"id":"...","type":"agent_message","text":"..."}}
        {"type":"turn.completed","usage":{"input_tokens":N,"output_tokens":N,...}}
    """

    @property
    def provider_name(self) -> str:
        return "openai"

    @staticmethod
    def _build_env(api_key: str) -> dict[str, str]:
        env = dict(os.environ)
        path = env.get("PATH", "")
        if _NPM_BIN not in path:
            env["PATH"] = f"{_NPM_BIN}:{path}"
        if api_key:
            env["OPENAI_API_KEY"] = api_key
        return env

    async def run(
        self, prompt: str, *, timeout: int = 300, cwd: str | None = None
    ) -> AgentResult:
        cmd = [
            "codex",
            "exec",
            "--full-auto",
            "--json",
            prompt,
        ]
        env = self._build_env(self.config.api_key)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise CLITimeoutError(f"Codex CLI timed out after {timeout}s") from None

        if proc.returncode != 0:
            raise CLIExecutionError(
                f"Codex CLI failed (exit {proc.returncode}): {stderr.decode()[:500]}"
            )

        try:
            # Codex outputs JSONL — collect item.completed texts and turn.completed usage
            lines = stdout.decode().strip().splitlines()
            texts: list[str] = []
            usage: dict[str, Any] = {}
            raw_events: list[dict[str, Any]] = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                raw_events.append(event)

                event_type = event.get("type", "")
                if event_type == "item.completed":
                    item = event.get("item", {})
                    text = item.get("text", "")
                    if text:
                        texts.append(text)
                elif event_type == "turn.completed":
                    usage = event.get("usage", {})

            output = "\n".join(texts)
            input_tokens = int(usage.get("input_tokens", 0))
            output_tokens = int(usage.get("output_tokens", 0))

            return AgentResult(
                output=output,
                exit_code=proc.returncode,
                duration_ms=0,
                tokens_used=input_tokens + output_tokens,
                raw={"events": raw_events, "usage": usage},
            )
        except (json.JSONDecodeError, ValueError) as e:
            raise CLIParseError(f"Failed to parse Codex output: {e}") from e

    async def health_check(self) -> bool:
        try:
            env = self._build_env(self.config.api_key)
            proc = await asyncio.create_subprocess_exec(
                "codex",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
