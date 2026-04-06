"""Tests for core/adapters/claude.py."""

import json

import pytest

from orchestrator.core.adapters.claude import ClaudeAdapter
from orchestrator.core.errors.exceptions import CLIExecutionError, CLIParseError
from orchestrator.core.models.schemas import AdapterConfig


def test_build_command_basic():
    adapter = ClaudeAdapter()
    config = AdapterConfig()
    cmd = adapter._build_command("hello world", config)
    assert "claude" in cmd
    assert "--bare" not in cmd
    assert "-p" in cmd
    assert "hello world" in cmd
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "--verbose" in cmd
    assert "--permission-mode" in cmd
    assert "bypassPermissions" in cmd


def test_build_command_with_system_prompt():
    adapter = ClaudeAdapter()
    config = AdapterConfig()
    cmd = adapter._build_command("task", config, system_prompt="you are an expert")
    assert "--system-prompt" in cmd
    assert "you are an expert" in cmd


def test_build_command_with_model():
    adapter = ClaudeAdapter()
    config = AdapterConfig(model="claude-sonnet-4-20250514")
    cmd = adapter._build_command("task", config)
    assert "--model" in cmd
    assert "claude-sonnet-4-20250514" in cmd


def test_parse_output_json():
    """stream-json JSONL: result 이벤트에서 출력을 추출한다."""
    adapter = ClaudeAdapter()
    stdout = '{"type":"result","result":"JWT middleware implemented","is_error":false,"usage":{"output_tokens":100}}\n'
    result = adapter._parse_output(stdout, "")
    assert "JWT middleware" in result.output
    assert result.tokens_used == 100


def test_parse_output_empty():
    adapter = ClaudeAdapter()
    with pytest.raises(CLIParseError):
        adapter._parse_output("", "")


def test_parse_output_plain_text():
    adapter = ClaudeAdapter()
    result = adapter._parse_output("just plain text", "")
    assert result.output == "just plain text"


def test_parse_output_is_error():
    """stream-json result with is_error=True should raise CLIExecutionError."""
    adapter = ClaudeAdapter()
    stdout = '{"type":"result","result":"Something went wrong","is_error":true}\n'
    with pytest.raises(CLIExecutionError, match="Something went wrong"):
        adapter._parse_output(stdout, "")
