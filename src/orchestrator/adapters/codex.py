"""Codex CLI adapter."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from orchestrator.adapters.base import CLIAdapter
from orchestrator.errors.exceptions import CLIExecutionError, CLIParseError, CLITimeoutError
from orchestrator.models.schemas import AgentResult


class CodexAdapter(CLIAdapter):
    """Adapter for OpenAI Codex CLI (headless mode)."""

    @property
    def provider_name(self) -> str:
        return "openai"

    async def run(self, prompt: str, *, timeout: int = 300) -> AgentResult:
        cmd = [
            "codex",
            "exec",
            "--json",
            "--ephemeral",
            "--full-auto",
            prompt,
        ]
        env = {**os.environ, "CODEX_API_KEY": self.config.api_key}

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
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
            # Codex outputs JSONL — parse last complete JSON object
            lines = stdout.decode().strip().splitlines()
            data: dict[str, Any] = {}
            for line in reversed(lines):
                line = line.strip()
                if line:
                    data = json.loads(line)
                    break

            output = str(data.get("output", data.get("result", "")))
            return AgentResult(
                output=output,
                exit_code=proc.returncode,
                duration_ms=int(data.get("duration_ms", 0)),
                tokens_used=int(data.get("tokens_used", 0)),
                raw=data,
            )
        except (json.JSONDecodeError, ValueError) as e:
            raise CLIParseError(f"Failed to parse Codex output: {e}") from e

    async def health_check(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "codex",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
