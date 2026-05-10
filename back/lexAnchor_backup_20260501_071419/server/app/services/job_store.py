from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JobStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_job(
        self,
        *,
        organization_id: str | None,
        workspace_id: str | None,
        created_by: str | None,
        request: dict[str, Any],
        status: str = "queued",
    ) -> str:
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (job_id, organization_id, workspace_id, created_by, status, progress, request_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, organization_id, workspace_id, created_by, status, 0, self._dump(request), now, now),
            )
        return job_id

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        current = self.get_job(job_id)
        if not current:
            raise KeyError(f"Job not found: {job_id}")
        next_status = status if status is not None else current.get("status")
        next_progress = progress if progress is not None else current.get("progress", 0)
        next_result = result if result is not None else current.get("result")
        next_error = error if error is not None else current.get("error")
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, progress = ?, result_json = ?, error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (next_status, int(next_progress or 0), self._dump(next_result), next_error, self._now(), job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    organization_id TEXT,
                    workspace_id TEXT,
                    created_by TEXT,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    request_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(connection, "jobs", "created_by", "TEXT")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _dump(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _load(value: str | None) -> Any:
        if not value:
            return None
        return json.loads(value)

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "organization_id": row["organization_id"],
            "workspace_id": row["workspace_id"],
            "created_by": row["created_by"],
            "status": row["status"],
            "progress": row["progress"],
            "request": self._load(row["request_json"]) or {},
            "result": self._load(row["result_json"]),
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
