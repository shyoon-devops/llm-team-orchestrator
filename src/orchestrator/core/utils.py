"""Shared utility functions."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, TypeVar

import structlog

T = TypeVar("T")


def generate_id(prefix: str = "") -> str:
    """UUID 기반 고유 ID를 생성한다.

    Args:
        prefix: ID 접두어.

    Returns:
        고유 ID 문자열.
    """
    uid = str(uuid.uuid4())
    if prefix:
        return f"{prefix}-{uid[:8]}"
    return uid


def truncate(text: str, max_len: int = 2000) -> str:
    """텍스트를 지정 길이로 자른다.

    Args:
        text: 원본 텍스트.
        max_len: 최대 길이.

    Returns:
        잘린 텍스트.
    """
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def setup_logging(level: str = "INFO") -> None:
    """structlog 로깅을 설정한다.

    Args:
        level: 로그 레벨.
    """
    import logging

    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    log_level = level_map.get(level.lower(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )


async def run_with_timeout(coro: Any, timeout: float) -> Any:  # noqa: ASYNC109
    """타임아웃 래퍼.

    Args:
        coro: 실행할 코루틴.
        timeout: 최대 실행 시간 (초).

    Returns:
        코루틴 결과.

    Raises:
        TimeoutError: 타임아웃 초과.
    """
    return await asyncio.wait_for(coro, timeout=timeout)
