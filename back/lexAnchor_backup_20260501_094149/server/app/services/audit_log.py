from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.access_control import RequestScope


class AuditLogStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def record_event(
        self,
        *,
        scope: RequestScope,
        event_type: str,
        resource_type: str,
        resource_id: str,
        outcome: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_id = f"audit_{uuid.uuid4().hex[:16]}"
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    event_id, organization_id, workspace_id, user_id, event_type,
                    resource_type, resource_id, outcome, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    scope.organization_id,
                    scope.workspace_id,
                    scope.user_id,
                    event_type,
                    resource_type,
                    resource_id,
                    outcome,
                    self._dump(metadata or {}),
                    now,
                ),
            )
        return {
            "event_id": event_id,
            "organization_id": scope.organization_id,
            "workspace_id": scope.workspace_id,
            "user_id": scope.user_id,
            "event_type": event_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "outcome": outcome,
            "metadata": metadata or {},
            "created_at": now,
        }

    def list_events(
        self,
        *,
        scope: RequestScope,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = ["organization_id = ?", "workspace_id = ?", "user_id = ?"]
        params: list[Any] = [scope.organization_id, scope.workspace_id, scope.user_id]
        if resource_type:
            clauses.append("resource_type = ?")
            params.append(resource_type)
        if resource_id:
            clauses.append("resource_id = ?")
            params.append(resource_id)
        params.append(max(1, min(int(limit or 100), 500)))
        query = f"""
            SELECT * FROM audit_events
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT ?
        """
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _dump(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _load(value: str | None) -> Any:
        return json.loads(value or "{}")

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "organization_id": row["organization_id"],
            "workspace_id": row["workspace_id"],
            "user_id": row["user_id"],
            "event_type": row["event_type"],
            "resource_type": row["resource_type"],
            "resource_id": row["resource_id"],
            "outcome": row["outcome"],
            "metadata": self._load(row["metadata_json"]),
            "created_at": row["created_at"],
        }
