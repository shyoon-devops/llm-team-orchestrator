"""Gemini CLI adapter."""

from __future__ import annotations

import asyncio
import json
import os

from orchestrator.adapters.base import CLIAdapter
from orchestrator.errors.exceptions import CLIExecutionError, CLIParseError, CLITimeoutError
from orchestrator.models.schemas import AgentResult


class GeminiAdapter(CLIAdapter):
    """Adapter for Google Gemini CLI (headless mode)."""

    @property
    def provider_name(self) -> str:
        return "google"

    async def run(self, prompt: str, *, timeout: int = 300) -> AgentResult:
        cmd = [
            "gemini",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--yolo",
        ]
        env = dict(os.environ)
        if self.config.api_key:
            env["GEMINI_API_KEY"] = self.config.api_key

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
            raise CLITimeoutError(f"Gemini CLI timed out after {timeout}s") from None

        if proc.returncode != 0:
            raise CLIExecutionError(
                f"Gemini CLI failed (exit {proc.returncode}): {stderr.decode()[:500]}"
            )

        try:
            # Gemini stream-json: filter for "result" events only
            # (stdout pollution bug workaround — #21433)
            lines = stdout.decode().strip().splitlines()
            result_text = ""
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "result":
                    result_text = str(event.get("data", ""))
                    break

            if not result_text:
                # Fallback: use last valid JSON line
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            result_text = str(data.get("result", data.get("data", "")))
                            break
                        except json.JSONDecodeError:
                            continue

            return AgentResult(
                output=result_text,
                exit_code=proc.returncode,
                raw={},
            )
        except (json.JSONDecodeError, ValueError) as e:
            raise CLIParseError(f"Failed to parse Gemini output: {e}") from e

    async def health_check(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "gemini",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
