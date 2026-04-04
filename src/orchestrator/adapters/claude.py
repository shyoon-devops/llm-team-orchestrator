"""Claude Code CLI adapter."""

from __future__ import annotations

import asyncio
import json
import os

from orchestrator.adapters.base import CLIAdapter
from orchestrator.errors.exceptions import CLIExecutionError, CLIParseError, CLITimeoutError
from orchestrator.models.schemas import AgentResult


class ClaudeAdapter(CLIAdapter):
    """Adapter for Claude Code CLI (headless mode)."""

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def run(self, prompt: str, *, timeout: int = 300) -> AgentResult:
        cmd = [
            "claude",
            "--bare",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--max-turns",
            "20",
        ]
        env = {**os.environ, "ANTHROPIC_API_KEY": self.config.api_key}

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
            raise CLITimeoutError(f"Claude CLI timed out after {timeout}s") from None

        if proc.returncode != 0:
            raise CLIExecutionError(
                f"Claude CLI failed (exit {proc.returncode}): {stderr.decode()[:500]}"
            )

        try:
            data = json.loads(stdout.decode())
            return AgentResult(
                output=data.get("result", ""),
                exit_code=proc.returncode,
                duration_ms=data.get("duration_ms", 0),
                tokens_used=data.get("usage", {}).get("input_tokens", 0)
                + data.get("usage", {}).get("output_tokens", 0),
                raw=data,
            )
        except json.JSONDecodeError as e:
            raise CLIParseError(f"Failed to parse Claude output: {e}") from e

    async def health_check(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
