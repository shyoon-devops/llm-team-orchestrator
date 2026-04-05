"""Tests for core/adapters/claude.py."""

import pytest

from orchestrator.core.adapters.claude import ClaudeAdapter
from orchestrator.core.errors.exceptions import CLIParseError
from orchestrator.core.models.schemas import AdapterConfig


def test_build_command_basic():
    adapter = ClaudeAdapter()
    config = AdapterConfig()
    cmd = adapter._build_command("hello world", config)
    assert "claude" in cmd
    assert "--bare" in cmd
    assert "-p" in cmd
    assert "hello world" in cmd
    assert "--output-format" in cmd
    assert "json" in cmd
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
    adapter = ClaudeAdapter()
    import json

    data = {"result": "JWT middleware implemented", "num_tokens": 100}
    result = adapter._parse_output(json.dumps(data), "")
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
