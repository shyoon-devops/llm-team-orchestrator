"""CheckpointStore — SQLite-backed pipeline state persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from orchestrator.core.models.pipeline import Pipeline

logger = structlog.get_logger()

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS checkpoints (
    pipeline_id TEXT PRIMARY KEY,
    state_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


class CheckpointStore:
    """SQLite-backed checkpoint store for pipeline state persistence.

    Saves and restores Pipeline state so that pipelines can be resumed
    after server restart or failure.

    Usage::

        store = CheckpointStore("./data/checkpoints.sqlite")
        store.save("pipeline-abc", pipeline)
        restored = store.load("pipeline-abc")
    """

    def __init__(self, db_path: str = "./data/checkpoints.sqlite") -> None:
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로.
        """
        self._db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """DB 파일과 테이블을 생성한다."""
        path = Path(self._db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()

    def save(self, pipeline_id: str, pipeline: Pipeline) -> None:
        """파이프라인 상태를 체크포인트로 저장한다.

        Args:
            pipeline_id: 파이프라인 ID.
            pipeline: 저장할 Pipeline 인스턴스.
        """
        now = datetime.utcnow().isoformat()
        state_json = pipeline.model_dump_json()

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (pipeline_id, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(pipeline_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (pipeline_id, state_json, now, now),
            )
            conn.commit()

        logger.debug("checkpoint_saved", pipeline_id=pipeline_id)

    def load(self, pipeline_id: str) -> Pipeline | None:
        """체크포인트에서 파이프라인 상태를 복원한다.

        Args:
            pipeline_id: 복원할 파이프라인 ID.

        Returns:
            복원된 Pipeline 인스턴스. 체크포인트가 없으면 None.
        """
        from orchestrator.core.models.pipeline import Pipeline

        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT state_json FROM checkpoints WHERE pipeline_id = ?",
                (pipeline_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        data = json.loads(row[0])
        return Pipeline.model_validate(data)

    def list_checkpoints(self) -> list[str]:
        """저장된 모든 체크포인트의 파이프라인 ID 목록을 반환한다.

        Returns:
            파이프라인 ID 목록 (updated_at 역순).
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("SELECT pipeline_id FROM checkpoints ORDER BY updated_at DESC")
            return [row[0] for row in cursor.fetchall()]

    def delete(self, pipeline_id: str) -> None:
        """체크포인트를 삭제한다.

        Args:
            pipeline_id: 삭제할 파이프라인 ID.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM checkpoints WHERE pipeline_id = ?",
                (pipeline_id,),
            )
            conn.commit()
        logger.debug("checkpoint_deleted", pipeline_id=pipeline_id)
