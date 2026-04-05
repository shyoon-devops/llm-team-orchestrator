"""ArtifactStore — file-based result storage (stub for Phase 1)."""

from __future__ import annotations

from pathlib import Path

import structlog

logger = structlog.get_logger()


class ArtifactStore:
    """파일 기반 아티팩트 저장소.

    에이전트 실행 결과, 중간 산출물 등을 파일로 저장/조회한다.
    Phase 1에서는 최소 기능만 구현한다.
    """

    def __init__(self, base_dir: str = "./data/artifacts") -> None:
        """
        Args:
            base_dir: 아티팩트 저장 기본 디렉토리.
        """
        self._base_dir = Path(base_dir)

    async def save(self, key: str, content: str) -> Path:
        """아티팩트를 저장한다.

        Args:
            key: 아티팩트 키 (파일 이름).
            content: 저장할 내용.

        Returns:
            저장된 파일 경로.
        """
        self._base_dir.mkdir(parents=True, exist_ok=True)
        path = self._base_dir / key
        path.write_text(content, encoding="utf-8")
        logger.info("artifact_saved", key=key, path=str(path))
        return path

    async def load(self, key: str) -> str | None:
        """아티팩트를 로드한다.

        Args:
            key: 아티팩트 키 (파일 이름).

        Returns:
            내용 문자열. 없으면 None.
        """
        path = self._base_dir / key
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")
