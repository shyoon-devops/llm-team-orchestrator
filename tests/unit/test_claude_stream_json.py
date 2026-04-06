"""Tests for Claude adapter stream-json output format."""

from __future__ import annotations

import pytest

from orchestrator.core.adapters.claude import ClaudeAdapter
from orchestrator.core.errors.exceptions import CLIExecutionError
from orchestrator.core.models.schemas import AdapterConfig


@pytest.fixture
def adapter():
    return ClaudeAdapter()


@pytest.fixture
def config(tmp_path):
    return AdapterConfig(timeout=10, working_dir=str(tmp_path))


def test_claude_build_command_uses_stream_json(adapter, config):
    """_build_command()가 --output-format stream-json --verbose를 사용한다."""
    cmd = adapter._build_command("hello", config)
    assert "--output-format" in cmd
    idx = cmd.index("--output-format")
    assert cmd[idx + 1] == "stream-json"
    assert "--verbose" in cmd


def test_claude_parse_stream_json_result_event(adapter):
    """result 이벤트에서 출력 텍스트를 추출한다."""
    stdout = '{"type":"system","subtype":"init"}\n{"type":"result","result":"42","is_error":false}\n'
    result = adapter._parse_output(stdout, "")
    assert "42" in result.output


def test_claude_parse_stream_json_assistant_event(adapter):
    """assistant 이벤트에서 text content를 추출한다."""
    stdout = (
        '{"type":"assistant","message":{"content":[{"type":"text","text":"hello world"}]}}\n'
        '{"type":"result","result":"hello world","is_error":false}\n'
    )
    result = adapter._parse_output(stdout, "")
    assert "hello world" in result.output


def test_claude_parse_stream_json_is_error(adapter):
    """is_error=true 시 CLIExecutionError가 발생한다."""
    stdout = '{"type":"result","result":"something broke","is_error":true}\n'
    with pytest.raises(CLIExecutionError, match="something broke"):
        adapter._parse_output(stdout, "")


def test_claude_parse_stream_json_mixed_lines(adapter):
    """JSON + 비JSON 혼합 라인을 처리한다."""
    stdout = (
        "some random text\n"
        '{"type":"system","subtype":"init"}\n'
        '{"type":"result","result":"done","is_error":false}\n'
    )
    result = adapter._parse_output(stdout, "")
    # 비JSON 라인("some random text")과 result("done") 모두 수집
    assert "some random text" in result.output
    assert "done" in result.output


def test_claude_parse_stream_json_usage_tokens(adapter):
    """usage에서 토큰 수를 추출한다."""
    stdout = (
        '{"type":"result","result":"ok","is_error":false,'
        '"usage":{"output_tokens":15}}\n'
    )
    result = adapter._parse_output(stdout, "")
    assert result.tokens_used == 15
