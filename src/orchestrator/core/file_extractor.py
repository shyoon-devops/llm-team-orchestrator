"""코드 블록에서 파일을 추출하여 저장하는 유틸리티."""

from __future__ import annotations

import os
import re

import structlog

logger = structlog.get_logger()

_CODE_BLOCK_PATTERN = re.compile(
    r"```(?:\w+)?(?::|\s*#\s*)([\w/.\-]+)\s*\n(.*?)```",
    re.DOTALL,
)


def extract_files_from_output(output: str, target_dir: str) -> list[str]:
    """CLI 출력에서 코드 블록을 파싱하여 파일로 저장한다.

    Args:
        output: CLI stdout 텍스트.
        target_dir: 파일을 저장할 디렉토리.

    Returns:
        생성된 파일 경로 목록 (상대 경로).
    """
    files_created: list[str] = []

    for match in _CODE_BLOCK_PATTERN.finditer(output):
        filepath = match.group(1).strip()
        content = match.group(2)

        if not filepath or filepath.startswith("/"):
            continue

        full_path = os.path.join(target_dir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w") as f:
            f.write(content)

        files_created.append(filepath)
        logger.info("file_extracted", path=filepath, size=len(content))

    return files_created
