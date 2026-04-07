"""PresetRegistry — YAML-based preset management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

from orchestrator.core.presets.models import AgentPreset, TeamPreset

logger = structlog.get_logger()


class PresetRegistry:
    """에이전트/팀 프리셋의 로딩, 검색, 저장을 담당한다.

    YAML 파일 기반으로 프리셋을 관리하며, 여러 검색 경로를 지원한다.
    동일 이름의 프리셋이 여러 경로에 있으면 앞선 경로가 우선한다.
    """

    def __init__(self, preset_dirs: list[str] | None = None) -> None:
        """PresetRegistry를 초기화하고 프리셋 디렉토리를 스캔한다.

        Args:
            preset_dirs: 프리셋 YAML 검색 디렉토리 목록. None이면 ["./presets"].
        """
        self._preset_dirs = preset_dirs or ["./presets"]
        self._agent_presets: dict[str, AgentPreset] = {}
        self._team_presets: dict[str, TeamPreset] = {}
        self._scan_directories()

    def _scan_directories(self) -> None:
        """프리셋 디렉토리를 스캔하여 YAML 파일을 로딩한다.

        앞선 경로가 우선이므로, 이미 로딩된 이름은 건너뛴다.
        """
        for preset_dir_str in self._preset_dirs:
            preset_dir = Path(preset_dir_str)
            if not preset_dir.exists():
                logger.debug("preset_dir_not_found", path=preset_dir_str)
                continue

            # Scan agents
            agents_dir = preset_dir / "agents"
            if agents_dir.exists():
                for yaml_path in sorted(agents_dir.glob("*.yaml")):
                    self._load_agent_yaml(yaml_path)

            # Scan teams
            teams_dir = preset_dir / "teams"
            if teams_dir.exists():
                for yaml_path in sorted(teams_dir.glob("*.yaml")):
                    self._load_team_yaml(yaml_path)

    def _load_agent_yaml(self, path: Path) -> None:
        """YAML 파일에서 에이전트 프리셋을 로딩한다.

        Args:
            path: YAML 파일 경로.
        """
        try:
            data = self._read_yaml(path)
            if data is None:
                return
            normalized = _normalize_agent_yaml(data)
            preset = AgentPreset.model_validate(normalized)
            if preset.name not in self._agent_presets:
                self._agent_presets[preset.name] = preset
                logger.debug("agent_preset_loaded", name=preset.name, path=str(path))
            else:
                logger.debug(
                    "agent_preset_skipped_duplicate",
                    name=preset.name,
                    path=str(path),
                )
        except Exception:
            logger.warning("agent_preset_load_failed", path=str(path), exc_info=True)

    def _load_team_yaml(self, path: Path) -> None:
        """YAML 파일에서 팀 프리셋을 로딩한다.

        Args:
            path: YAML 파일 경로.
        """
        try:
            data = self._read_yaml(path)
            if data is None:
                return
            normalized = _normalize_team_yaml(data)
            preset = TeamPreset.model_validate(normalized)
            if preset.name not in self._team_presets:
                self._team_presets[preset.name] = preset
                logger.debug("team_preset_loaded", name=preset.name, path=str(path))
            else:
                logger.debug(
                    "team_preset_skipped_duplicate",
                    name=preset.name,
                    path=str(path),
                )
        except Exception:
            logger.warning("team_preset_load_failed", path=str(path), exc_info=True)

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any] | None:
        """YAML 파일을 읽고 딕셔너리로 반환한다.

        Args:
            path: YAML 파일 경로.

        Returns:
            파싱된 딕셔너리. 실패 시 None.
        """
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        return data

    def load_agent_preset(self, name: str) -> AgentPreset:
        """이름으로 에이전트 프리셋을 조회한다.

        Args:
            name: 프리셋 이름.

        Returns:
            프리셋 인스턴스.

        Raises:
            KeyError: 프리셋이 존재하지 않는 경우.
        """
        if name not in self._agent_presets:
            msg = f"Agent preset not found: {name}"
            raise KeyError(msg)
        return self._agent_presets[name]

    def load_team_preset(self, name: str) -> TeamPreset:
        """이름으로 팀 프리셋을 조회한다.

        Args:
            name: 팀 프리셋 이름.

        Returns:
            팀 프리셋 인스턴스.

        Raises:
            KeyError: 프리셋이 존재하지 않는 경우.
        """
        if name not in self._team_presets:
            msg = f"Team preset not found: {name}"
            raise KeyError(msg)
        return self._team_presets[name]

    def list_agent_presets(self) -> list[AgentPreset]:
        """등록된 모든 에이전트 프리셋을 반환한다."""
        return sorted(self._agent_presets.values(), key=lambda p: p.name)

    def list_team_presets(self) -> list[TeamPreset]:
        """등록된 모든 팀 프리셋을 반환한다."""
        return sorted(self._team_presets.values(), key=lambda p: p.name)

    def save_agent_preset(
        self,
        preset: AgentPreset,
        *,
        overwrite: bool = True,
    ) -> None:
        """에이전트 프리셋을 레지스트리에 등록하고 YAML 파일로 저장한다.

        Args:
            preset: 저장할 프리셋.
            overwrite: 기존 프리셋 덮어쓰기 여부.

        Raises:
            ValueError: overwrite=False이고 이미 존재하는 경우.
        """
        if not overwrite and preset.name in self._agent_presets:
            msg = f"Agent preset already exists: {preset.name}"
            raise ValueError(msg)
        self._agent_presets[preset.name] = preset
        self._write_agent_yaml(preset)
        logger.info("agent_preset_saved", name=preset.name)

    def save_team_preset(
        self,
        preset: TeamPreset,
        *,
        overwrite: bool = True,
    ) -> None:
        """팀 프리셋을 레지스트리에 등록하고 YAML 파일로 저장한다.

        Args:
            preset: 저장할 프리셋.
            overwrite: 기존 프리셋 덮어쓰기 여부.

        Raises:
            ValueError: overwrite=False이고 이미 존재하는 경우.
        """
        if not overwrite and preset.name in self._team_presets:
            msg = f"Team preset already exists: {preset.name}"
            raise ValueError(msg)
        self._team_presets[preset.name] = preset
        self._write_team_yaml(preset)
        logger.info("team_preset_saved", name=preset.name)

    def _write_agent_yaml(self, preset: AgentPreset) -> None:
        """에이전트 프리셋을 첫 번째 프리셋 디렉토리에 YAML로 저장한다.

        Args:
            preset: 저장할 프리셋.
        """
        target_dir = Path(self._preset_dirs[0]) / "agents"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{preset.name}.yaml"
        with target_path.open("w", encoding="utf-8") as f:
            yaml.dump(
                preset.model_dump(mode="python"),
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        logger.debug("agent_preset_written", path=str(target_path))

    def _write_team_yaml(self, preset: TeamPreset) -> None:
        """팀 프리셋을 첫 번째 프리셋 디렉토리에 YAML로 저장한다.

        Args:
            preset: 저장할 프리셋.
        """
        target_dir = Path(self._preset_dirs[0]) / "teams"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{preset.name}.yaml"
        with target_path.open("w", encoding="utf-8") as f:
            yaml.dump(
                preset.model_dump(mode="python"),
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        logger.debug("team_preset_written", path=str(target_path))

    def delete_agent_preset(self, name: str) -> None:
        """에이전트 프리셋을 레지스트리와 YAML 파일에서 삭제한다.

        Args:
            name: 삭제할 프리셋 이름.

        Raises:
            KeyError: 프리셋이 존재하지 않는 경우.
        """
        if name not in self._agent_presets:
            msg = f"Agent preset not found: {name}"
            raise KeyError(msg)
        del self._agent_presets[name]
        # YAML 파일 삭제
        for preset_dir_str in self._preset_dirs:
            yaml_path = Path(preset_dir_str) / "agents" / f"{name}.yaml"
            if yaml_path.exists():
                yaml_path.unlink()
                logger.debug("agent_preset_file_deleted", path=str(yaml_path))
        logger.info("agent_preset_deleted", name=name)

    def delete_team_preset(self, name: str) -> None:
        """팀 프리셋을 레지스트리와 YAML 파일에서 삭제한다.

        Args:
            name: 삭제할 프리셋 이름.

        Raises:
            KeyError: 프리셋이 존재하지 않는 경우.
        """
        if name not in self._team_presets:
            msg = f"Team preset not found: {name}"
            raise KeyError(msg)
        del self._team_presets[name]
        # YAML 파일 삭제
        for preset_dir_str in self._preset_dirs:
            yaml_path = Path(preset_dir_str) / "teams" / f"{name}.yaml"
            if yaml_path.exists():
                yaml_path.unlink()
                logger.debug("team_preset_file_deleted", path=str(yaml_path))
        logger.info("team_preset_deleted", name=name)

    def merge_preset_with_overrides(
        self,
        preset_name: str,
        overrides: dict[str, Any],
    ) -> AgentPreset:
        """기존 AgentPreset에 오버라이드를 deep merge하여 새 인스턴스를 반환한다.

        Args:
            preset_name: 기반 AgentPreset 이름.
            overrides: 오버라이드할 필드.

        Returns:
            오버라이드가 적용된 새 인스턴스 (원본 불변).

        Raises:
            KeyError: preset_name이 존재하지 않는 경우.
        """
        base = self.load_agent_preset(preset_name)
        base_dict = base.model_dump()
        merged = _deep_merge(base_dict, overrides)
        return AgentPreset.model_validate(merged)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """딕셔너리를 재귀적으로 deep merge한다.

    스칼라/리스트: 오버라이드가 대체.
    dict: 재귀적으로 merge.
    """
    result = {**base}
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _normalize_agent_yaml(data: dict[str, Any]) -> dict[str, Any]:
    """YAML 프리셋 데이터를 AgentPreset 모델 형식으로 정규화한다.

    YAML 스키마(presets-guide.md)와 Pydantic 모델(data-models.md) 사이의
    필드명 차이를 해소한다.

    Args:
        data: YAML에서 파싱한 원본 딕셔너리.

    Returns:
        AgentPreset.model_validate()에 전달 가능한 딕셔너리.
    """
    result: dict[str, Any] = {}

    # Direct copy fields
    for key in ("name", "description", "tags", "persona", "limits"):
        if key in data:
            result[key] = data[key]

    if "execution" in data:
        exec_data = data["execution"]
        if "preferred_cli" in exec_data:
            cli_val = exec_data["preferred_cli"]
            result["preferred_cli"] = cli_val if cli_val else None
        if "fallback_cli" in exec_data:
            fallback = exec_data["fallback_cli"]
            if isinstance(fallback, str):
                result["fallback_cli"] = [fallback] if fallback else []
            elif isinstance(fallback, list):
                result["fallback_cli"] = fallback
        if exec_data.get("model_override"):
            result["model"] = exec_data["model_override"]
    else:
        for key in ("preferred_cli", "fallback_cli", "model"):
            if key in data:
                result[key] = data[key]

    # tools (pass through)
    if "tools" in data:
        result["tools"] = data["tools"]

    # mcp_servers
    if "mcp_servers" in data:
        result["mcp_servers"] = data["mcp_servers"]

    return result


def _normalize_team_yaml(data: dict[str, Any]) -> dict[str, Any]:
    """YAML 프리셋 데이터를 TeamPreset 모델 형식으로 정규화한다.

    Args:
        data: YAML에서 파싱한 원본 딕셔너리.

    Returns:
        TeamPreset.model_validate()에 전달 가능한 딕셔너리.
    """
    result: dict[str, Any] = {}

    for key in ("name", "description", "agents", "tasks", "workflow"):
        if key in data:
            result[key] = data[key]

    # synthesis -> synthesis_strategy
    if "synthesis" in data:
        synth = data["synthesis"]
        if isinstance(synth, dict) and "strategy" in synth:
            result["synthesis_strategy"] = synth["strategy"]
    elif "synthesis_strategy" in data:
        result["synthesis_strategy"] = data["synthesis_strategy"]

    return result
