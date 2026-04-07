"""Tests for MCP isolation abstraction (iter19).

각 CLI 어댑터가 MCP 서버를 CLI별 방식으로 주입하는지 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.core.adapters.claude import ClaudeAdapter
from orchestrator.core.adapters.codex import CodexAdapter
from orchestrator.core.adapters.gemini import GeminiAdapter
from orchestrator.core.models.schemas import AdapterConfig
from orchestrator.core.presets.models import MCPServerDef


# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_mcp_servers() -> dict[str, MCPServerDef]:
    return {
        "elastic-mock": MCPServerDef(
            command="uv",
            args=["run", "python", "tools/mcp-servers/elastic_mcp.py"],
        ),
        "grafana-mock": MCPServerDef(
            command="npx",
            args=["-y", "@mcp/server-grafana"],
            env={"GRAFANA_TOKEN": "secret123"},
        ),
    }


@pytest.fixture
def config_with_mcp(tmp_path, sample_mcp_servers) -> AdapterConfig:
    return AdapterConfig(
        timeout=30,
        working_dir=str(tmp_path),
        mcp_servers=sample_mcp_servers,
    )


@pytest.fixture
def config_empty_mcp(tmp_path) -> AdapterConfig:
    return AdapterConfig(timeout=30, working_dir=str(tmp_path))


# ──────────────────────────────────────────────────────────
# AdapterConfig defaults
# ──────────────────────────────────────────────────────────


def test_adapter_config_mcp_servers_default():
    """기본 AdapterConfig.mcp_servers는 빈 dict이다."""
    config = AdapterConfig(timeout=30)
    assert config.mcp_servers == {}


# ──────────────────────────────────────────────────────────
# Claude adapter
# ──────────────────────────────────────────────────────────


def test_claude_build_command_with_mcp(config_with_mcp, sample_mcp_servers):
    """MCP 서버가 있으면 --mcp-config JSON과 --strict-mcp-config가 명령어에 포함된다."""
    adapter = ClaudeAdapter()
    cmd = adapter._build_command("hello", config_with_mcp)
    assert "--mcp-config" in cmd
    assert "--strict-mcp-config" in cmd
    idx = cmd.index("--mcp-config")
    mcp_json = cmd[idx + 1]
    parsed = json.loads(mcp_json)
    assert "elastic-mock" in parsed["mcpServers"]
    assert "grafana-mock" in parsed["mcpServers"]


def test_claude_build_command_empty_mcp(config_empty_mcp):
    """빈 mcp_servers여도 --strict-mcp-config으로 전체 MCP 차단한다."""
    adapter = ClaudeAdapter()
    cmd = adapter._build_command("hello", config_empty_mcp)
    assert "--strict-mcp-config" in cmd
    assert "--mcp-config" in cmd
    idx = cmd.index("--mcp-config")
    mcp_json = cmd[idx + 1]
    parsed = json.loads(mcp_json)
    assert parsed == {"mcpServers": {}}


def test_claude_mcp_config_json_format(sample_mcp_servers):
    """_build_mcp_config_json 출력이 유효한 JSON이며 예상 구조를 가진다."""
    result = ClaudeAdapter._build_mcp_config_json(sample_mcp_servers)
    parsed = json.loads(result)
    assert "mcpServers" in parsed
    assert parsed["mcpServers"]["elastic-mock"]["command"] == "uv"
    assert parsed["mcpServers"]["elastic-mock"]["args"] == [
        "run", "python", "tools/mcp-servers/elastic_mcp.py"
    ]
    # env가 있는 서버에 env 포함
    assert parsed["mcpServers"]["grafana-mock"]["env"]["GRAFANA_TOKEN"] == "secret123"
    # env가 없는 서버에는 env 키 없음
    assert "env" not in parsed["mcpServers"]["elastic-mock"]


# ──────────────────────────────────────────────────────────
# Gemini adapter
# ──────────────────────────────────────────────────────────


def test_gemini_prepare_workspace_creates_settings(config_with_mcp):
    """MCP 서버가 있으면 .gemini/settings.json이 생성된다."""
    adapter = GeminiAdapter()
    workspace, env = adapter._prepare_mcp_workspace(config_with_mcp)
    assert workspace is not None
    settings_path = Path(workspace) / ".gemini" / "settings.json"
    assert settings_path.exists()
    content = json.loads(settings_path.read_text())
    assert "mcpServers" in content
    assert "elastic-mock" in content["mcpServers"]
    assert content["mcpServers"]["elastic-mock"]["trust"] is True
    assert env == {}


def test_gemini_prepare_workspace_empty_mcp(config_empty_mcp):
    """빈 mcp_servers면 workspace를 생성하지 않는다."""
    adapter = GeminiAdapter()
    workspace, env = adapter._prepare_mcp_workspace(config_empty_mcp)
    assert workspace is None
    assert env == {}


def test_gemini_build_command_with_mcp(config_with_mcp):
    """MCP 서버가 있으면 --allowed-mcp-server-names가 명령어에 포함된다."""
    adapter = GeminiAdapter()
    cmd = adapter._build_command("analyze logs", config_with_mcp)
    assert "--allowed-mcp-server-names" in cmd
    idx = cmd.index("--allowed-mcp-server-names")
    # 서버 이름들이 인자로 포함
    assert "elastic-mock" in cmd[idx + 1 :]
    assert "grafana-mock" in cmd[idx + 1 :]


def test_gemini_prepare_workspace_correct_content(config_with_mcp):
    """settings.json 내용이 mcp_servers와 일치한다."""
    adapter = GeminiAdapter()
    workspace, _ = adapter._prepare_mcp_workspace(config_with_mcp)
    settings_path = Path(workspace) / ".gemini" / "settings.json"
    content = json.loads(settings_path.read_text())
    grafana = content["mcpServers"]["grafana-mock"]
    assert grafana["command"] == "npx"
    assert grafana["args"] == ["-y", "@mcp/server-grafana"]
    assert grafana["env"]["GRAFANA_TOKEN"] == "secret123"


# ──────────────────────────────────────────────────────────
# Codex adapter
# ──────────────────────────────────────────────────────────


def test_codex_prepare_workspace_copies_home(tmp_path, sample_mcp_servers):
    """~/.codex가 있으면 복사본을 만들고 config.toml에 MCP를 교체한다."""
    import tomllib

    # 가짜 ~/.codex 생성
    fake_codex_home = tmp_path / ".codex"
    fake_codex_home.mkdir()
    (fake_codex_home / "config.toml").write_text('model = "o3-mini"\n')

    config = AdapterConfig(
        timeout=30,
        working_dir=str(tmp_path),
        mcp_servers=sample_mcp_servers,
    )

    adapter = CodexAdapter()
    with patch.object(Path, "home", return_value=tmp_path):
        cwd_override, env = adapter._prepare_mcp_workspace(config)

    assert cwd_override is None  # Codex는 cwd 오버라이드 없음
    assert "CODEX_HOME" in env
    codex_copy = Path(env["CODEX_HOME"])
    assert codex_copy.exists()

    config_toml = codex_copy / "config.toml"
    assert config_toml.exists()
    cfg = tomllib.loads(config_toml.read_text())
    assert "mcp_servers" in cfg
    assert "elastic-mock" in cfg["mcp_servers"]
    assert cfg["mcp_servers"]["elastic-mock"]["command"] == "uv"


def test_codex_prepare_workspace_returns_env(tmp_path, sample_mcp_servers):
    """CODEX_HOME env가 반환된다."""
    fake_codex_home = tmp_path / ".codex"
    fake_codex_home.mkdir()
    (fake_codex_home / "config.toml").write_text("")

    config = AdapterConfig(
        timeout=30,
        working_dir=str(tmp_path),
        mcp_servers=sample_mcp_servers,
    )

    adapter = CodexAdapter()
    with patch.object(Path, "home", return_value=tmp_path):
        _, env = adapter._prepare_mcp_workspace(config)

    assert "CODEX_HOME" in env
    assert Path(env["CODEX_HOME"]).exists()


def test_codex_prepare_workspace_empty_mcp(config_empty_mcp):
    """빈 mcp_servers면 workspace를 생성하지 않는다."""
    adapter = CodexAdapter()
    cwd_override, env = adapter._prepare_mcp_workspace(config_empty_mcp)
    assert cwd_override is None
    assert env == {}


def test_codex_prepare_workspace_no_codex_home(tmp_path, sample_mcp_servers):
    """~/.codex가 없으면 (None, {})를 반환한다."""
    config = AdapterConfig(
        timeout=30,
        working_dir=str(tmp_path),
        mcp_servers=sample_mcp_servers,
    )

    adapter = CodexAdapter()
    # tmp_path 아래에 .codex가 없으므로
    with patch.object(Path, "home", return_value=tmp_path / "nonexistent"):
        cwd_override, env = adapter._prepare_mcp_workspace(config)

    assert cwd_override is None
    assert env == {}


# ──────────────────────────────────────────────────────────
# Engine — preset mcp_servers → AdapterConfig
# ──────────────────────────────────────────────────────────


def test_engine_passes_mcp_from_preset(sample_mcp_servers):
    """프리셋의 mcp_servers가 AdapterConfig.mcp_servers로 전달된다."""
    from unittest.mock import patch as mock_patch

    from orchestrator.core.presets.models import AgentLimits, AgentPreset, PersonaDef

    preset = AgentPreset(
        name="test-agent",
        persona=PersonaDef(role="tester", goal="test"),
        preferred_cli="claude",
        mcp_servers=sample_mcp_servers,
        limits=AgentLimits(timeout=120),
    )

    # engine._create_executor_for_preset 내부에서 AdapterConfig 생성 추적
    from orchestrator.core.engine import OrchestratorEngine

    engine = OrchestratorEngine()

    with (
        mock_patch.object(
            engine._preset_registry, "load_agent_preset", return_value=preset
        ),
        mock_patch(
            "orchestrator.core.engine.CLIAgentExecutor"
        ) as mock_executor_cls,
    ):
        mock_executor_cls.return_value = MagicMock()
        executor = engine._create_executor_for_preset("test-agent", cwd="/tmp/test")

    # CLIAgentExecutor에 전달된 config에 mcp_servers가 포함되어야 함
    call_args = mock_executor_cls.call_args
    adapter_config = call_args.kwargs.get("config") or call_args[1].get("config")
    assert adapter_config.mcp_servers == sample_mcp_servers


# ──────────────────────────────────────────────────────────
# Base adapter — run() merges mcp env
# ──────────────────────────────────────────────────────────


def test_base_prepare_mcp_workspace_default():
    """기본 _prepare_mcp_workspace는 (None, {})를 반환한다."""
    adapter = ClaudeAdapter()
    # ClaudeAdapter는 _prepare_mcp_workspace를 오버라이드하지 않으므로 기본 구현 사용
    config = AdapterConfig(timeout=30)
    cwd_override, env = adapter._prepare_mcp_workspace(config)
    assert cwd_override is None
    assert env == {}
