"""Gemini CLI adapter."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from orchestrator.adapters.base import CLIAdapter
from orchestrator.errors.exceptions import CLIExecutionError, CLIParseError, CLITimeoutError
from orchestrator.models.schemas import AgentResult

_NPM_BIN = "/home/yoon/.local/npm/bin"


class GeminiAdapter(CLIAdapter):
    """Adapter for Google Gemini CLI (headless mode).

    Real stream-json output format (gemini -p "..." --output-format stream-json --sandbox=none):
        {"type":"message","role":"assistant","content":"...","delta":true}
        {"type":"result","status":"success","stats":{...}}
    """

    @property
    def provider_name(self) -> str:
        return "google"

    @staticmethod
    def _build_env(api_key: str) -> dict[str, str]:
        env = dict(os.environ)
        path = env.get("PATH", "")
        if _NPM_BIN not in path:
            env["PATH"] = f"{_NPM_BIN}:{path}"
        if api_key:
            env["GEMINI_API_KEY"] = api_key
        return env

    async def run(self, prompt: str, *, timeout: int = 300) -> AgentResult:
        cmd = [
            "gemini",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--sandbox=none",
        ]
        env = self._build_env(self.config.api_key)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise CLITimeoutError(f"Gemini CLI timed out after {timeout}s") from None

        if proc.returncode != 0:
            raise CLIExecutionError(
                f"Gemini CLI failed (exit {proc.returncode}): {stderr.decode()[:500]}"
            )

        try:
            # Gemini stream-json: collect assistant message content and result stats
            lines = stdout.decode().strip().splitlines()
            content_parts: list[str] = []
            stats: dict[str, Any] = {}
            raw_events: list[dict[str, Any]] = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue  # ignore non-JSON stderr noise
                raw_events.append(event)

                event_type = event.get("type", "")
                if event_type == "message" and event.get("role") == "assistant":
                    content = event.get("content", "")
                    if content:
                        content_parts.append(content)
                elif event_type == "result":
                    stats = event.get("stats", {})

            output = "".join(content_parts)
            input_tokens = int(stats.get("input_tokens", 0))
            output_tokens = int(stats.get("output_tokens", 0))
            duration_ms = int(stats.get("duration_ms", 0))

            return AgentResult(
                output=output,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                tokens_used=input_tokens + output_tokens,
                raw={"events": raw_events, "stats": stats},
            )
        except (json.JSONDecodeError, ValueError) as e:
            raise CLIParseError(f"Failed to parse Gemini output: {e}") from e

    async def health_check(self) -> bool:
        try:
            env = self._build_env(self.config.api_key)
            proc = await asyncio.create_subprocess_exec(
                "gemini",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
