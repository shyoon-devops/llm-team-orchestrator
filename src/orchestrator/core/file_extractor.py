"""코드 블록에서 파일을 추출하여 저장하는 유틸리티."""

from __future__ import annotations

import os
import re

import structlog

logger = structlog.get_logger()

# 다중 패턴: 우선순위 순서대로 시도
_PATTERNS: list[re.Pattern[str]] = [
    # ```python:src/app.py
    re.compile(
        r"```(?:\w+)?:([\w/.\-]+)\s*\n(.*?)```",
        re.DOTALL,
    ),
    # ```python # src/app.py
    re.compile(
        r"```(?:\w+)?\s*#\s*([\w/.\-]+)\s*\n(.*?)```",
        re.DOTALL,
    ),
    # **파일: src/app.py** 다음에 코드블록
    re.compile(
        r"\*\*(?:파일|File|file):\s*([\w/.\-]+)\*\*\s*\n```(?:\w+)?\n(.*?)```",
        re.DOTALL,
    ),
    # ### src/app.py 다음에 코드블록 (확장자 필수)
    re.compile(
        r"###?\s+([\w/.\-]+\.(?:py|ts|js|jsx|tsx|yaml|yml|json|md|txt|toml|cfg|ini|html|css|sh))\s*\n```(?:\w+)?\n(.*?)```",
        re.DOTALL,
    ),
]

# 허용 확장자
_VALID_EXTENSIONS = frozenset({
    ".py", ".ts", ".js", ".jsx", ".tsx",
    ".json", ".yaml", ".yml",
    ".md", ".txt", ".rst",
    ".toml", ".cfg", ".ini",
    ".html", ".css", ".scss",
    ".sh", ".bash",
    ".sql", ".graphql",
    ".dockerfile", ".env",
})


def _is_valid_filename(name: str) -> bool:
    """파일명이 유효한지 검증한다.

    Args:
        name: 검증할 파일명.

    Returns:
        유효하면 True.
    """
    # 확장자가 있어야 함
    if "." not in name:
        return False
    # ASCII 영숫자 + / . - _ 만 허용 (한글/특수문자 거부)
    if not re.match(r"^[a-zA-Z0-9_/.\-]+$", name):
        return False
    # 허용 확장자 확인
    _, ext = os.path.splitext(name)
    return ext.lower() in _VALID_EXTENSIONS


def extract_files_from_output(output: str, target_dir: str) -> list[str]:
    """CLI 출력에서 코드 블록을 파싱하여 파일로 저장한다.

    다중 패턴을 순서대로 적용하고, 파일명 검증을 통해 false positive를 방지한다.

    Args:
        output: CLI stdout 텍스트.
        target_dir: 파일을 저장할 디렉토리.

    Returns:
        생성된 파일 경로 목록 (상대 경로).
    """
    files_created: list[str] = []
    seen_paths: set[str] = set()

    for pattern in _PATTERNS:
        for match in pattern.finditer(output):
            filepath = match.group(1).strip()
            content = match.group(2)

            # 절대 경로 거부
            if filepath.startswith("/"):
                continue

            # 파일명 검증
            if not _is_valid_filename(filepath):
                logger.debug("file_extractor_skip_invalid", path=filepath)
                continue

            # 중복 방지 (먼저 매칭된 패턴 우선)
            if filepath in seen_paths:
                continue
            seen_paths.add(filepath)

            full_path = os.path.join(target_dir, filepath)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w") as f:
                f.write(content)

            files_created.append(filepath)
            logger.info("file_extracted", path=filepath, size=len(content))

    return files_created
