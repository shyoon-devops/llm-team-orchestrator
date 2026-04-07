"""Tests for CLI adapter streaming output (_stream_output + on_output callback)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from orchestrator.core.adapters.claude import ClaudeAdapter
from orchestrator.core.adapters.codex import CodexAdapter
from orchestrator.core.errors.exceptions import CLITimeoutError
from orchestrator.core.models.schemas import AdapterConfig


@pytest.fixture
def adapter():
    return ClaudeAdapter()


@pytest.fixture
def config(tmp_path):
    return AdapterConfig(timeout=10, working_dir=str(tmp_path))


# --- _stream_output tests ---


@pytest.mark.asyncio
async def test_stream_output_collects_stdout_lines(adapter):
    """_stream_output이 stdout 라인을 리스트로 수집한다."""
    proc = await asyncio.create_subprocess_exec(
        "printf", "line1\nline2\nline3\n",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    callback = AsyncMock()
    stdout, stderr = await adapter._stream_output(proc, idle_timeout=5, on_output=callback)
    assert stdout == "line1\nline2\nline3"


@pytest.mark.asyncio
async def test_stream_output_collects_stderr_lines(adapter):
    """stderr도 동시 수집된다."""
    proc = await asyncio.create_subprocess_exec(
        "bash", "-c", "echo err1 >&2; echo err2 >&2",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    callback = AsyncMock()
    stdout, stderr = await adapter._stream_output(proc, idle_timeout=5, on_output=callback)
    assert "err1" in stderr
    assert "err2" in stderr


@pytest.mark.asyncio
async def test_stream_output_calls_callback_per_line(adapter):
    """콜백이 각 라인마다 호출된다."""
    proc = await asyncio.create_subprocess_exec(
        "printf", "a\nb\nc\n",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    callback = AsyncMock()
    await adapter._stream_output(proc, idle_timeout=5, on_output=callback)

    assert callback.call_count == 3
    callback.assert_any_call("a", "stdout")
    callback.assert_any_call("b", "stdout")
    callback.assert_any_call("c", "stdout")


@pytest.mark.asyncio
async def test_stream_output_callback_receives_stream_name(adapter):
    """콜백의 두 번째 인자가 'stdout' 또는 'stderr'이다."""
    proc = await asyncio.create_subprocess_exec(
        "bash", "-c", "echo out; echo err >&2",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    callback = AsyncMock()
    await adapter._stream_output(proc, idle_timeout=5, on_output=callback)

    streams = [call.args[1] for call in callback.call_args_list]
    assert "stdout" in streams
    assert "stderr" in streams


@pytest.mark.asyncio
async def test_stream_output_idle_timeout_kills_process(adapter):
    """무활동 시 idle timeout이 발동한다."""
    proc = await asyncio.create_subprocess_exec(
        "sleep", "100",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    callback = AsyncMock()

    with pytest.raises(TimeoutError, match="idle timeout"):
        await adapter._stream_output(proc, idle_timeout=6, on_output=callback)

    await proc.wait()


@pytest.mark.asyncio
async def test_stream_output_callback_error_does_not_stop_streaming(adapter):
    """콜백 예외가 스트리밍을 중단하지 않는다."""
    proc = await asyncio.create_subprocess_exec(
        "printf", "x\ny\nz\n",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    callback = AsyncMock(side_effect=RuntimeError("boom"))
    stdout, _ = await adapter._stream_output(proc, idle_timeout=5, on_output=callback)

    # 콜백 에러에도 불구하고 모든 라인 수집됨
    assert stdout == "x\ny\nz"
    assert callback.call_count == 3


@pytest.mark.asyncio
async def test_stream_output_idle_reset_on_activity(adapter):
    """출력이 계속 오면 idle timeout이 리셋되어 타임아웃되지 않는다."""
    # 1초 간격으로 3줄 출력 (총 3초), idle_timeout=6초
    proc = await asyncio.create_subprocess_exec(
        "bash", "-c", "for i in 1 2 3; do echo $i; sleep 1; done",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    callback = AsyncMock()
    stdout, _ = await adapter._stream_output(proc, idle_timeout=6, on_output=callback)
    assert callback.call_count == 3
    assert "1" in stdout


@pytest.mark.asyncio
async def test_stream_output_idle_timeout_after_silence(adapter):
    """출력 후 침묵하면 idle timeout이 발동한다."""
    # 1줄 출력 후 100초 대기
    proc = await asyncio.create_subprocess_exec(
        "bash", "-c", "echo hello; sleep 100",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    callback = AsyncMock()
    with pytest.raises(TimeoutError):
        await adapter._stream_output(proc, idle_timeout=6, on_output=callback)
    # "hello" 라인은 수신됨
    callback.assert_any_call("hello", "stdout")
    await proc.wait()


@pytest.mark.asyncio
async def test_stream_output_active_process_no_timeout(adapter):
    """계속 출력하는 프로세스는 idle timeout보다 오래 실행해도 안 죽는다."""
    # 0.5초 간격으로 8줄 출력 (총 4초), idle_timeout=6초
    proc = await asyncio.create_subprocess_exec(
        "bash", "-c", "for i in 1 2 3 4 5 6 7 8; do echo line$i; sleep 0.5; done",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    callback = AsyncMock()
    stdout, _ = await adapter._stream_output(proc, idle_timeout=6, on_output=callback)
    assert callback.call_count == 8


# --- run() on_output 분기 tests ---


@pytest.mark.asyncio
async def test_run_without_callback_uses_communicate(adapter, config, monkeypatch):
    """on_output=None → communicate() 경로."""
    # Mock adapter internals to avoid running real CLI
    monkeypatch.setattr(
        adapter, "_build_command",
        lambda *a, **kw: ["echo", "hello"],
    )
    result = await adapter.run("test", config, on_output=None)
    assert "hello" in result.output


@pytest.mark.asyncio
async def test_run_with_callback_uses_stream(adapter, config, monkeypatch):
    """on_output 전달 → _stream_output() 경로, 콜백 호출됨."""
    monkeypatch.setattr(
        adapter, "_build_command",
        lambda *a, **kw: ["printf", "line1\\nline2\\n"],
    )
    callback = AsyncMock()
    result = await adapter.run("test", config, on_output=callback)
    assert callback.call_count >= 1


@pytest.mark.asyncio
async def test_run_streaming_timeout_raises_cli_timeout(config, monkeypatch):
    """스트리밍 모드에서 idle timeout 시 CLITimeoutError."""
    adapter = ClaudeAdapter()
    short_config = config.model_copy(update={"timeout": 6})
    monkeypatch.setattr(
        adapter, "_build_command",
        lambda *a, **kw: ["sleep", "100"],
    )
    callback = AsyncMock()

    with pytest.raises(CLITimeoutError):
        await adapter.run("test", short_config, on_output=callback)


@pytest.mark.asyncio
async def test_parse_output_receives_same_data_streaming_vs_buffered(config, monkeypatch):
    """스트리밍/버퍼링 결과가 _parse_output()에 동일하게 전달된다."""
    adapter = CodexAdapter()
    monkeypatch.setattr(
        adapter, "_build_command",
        lambda *a, **kw: ["printf", '{"type":"item.completed","item":{"content":[{"type":"text","text":"ok"}]}}\\n'],
    )

    # Buffered
    result_buf = await adapter.run("test", config, on_output=None)
    # Streaming
    callback = AsyncMock()
    result_str = await adapter.run("test", config, on_output=callback)

    assert result_buf.output == result_str.output
