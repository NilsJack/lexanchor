from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MembershipStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def grant_membership(
        self,
        *,
        user_id: str,
        organization_id: str,
        workspace_id: str,
        roles: list[str],
        status: str = "active",
    ) -> dict[str, Any]:
        clean_roles = self._clean_roles(roles)
        if not clean_roles:
            raise ValueError("At least one role is required")
        now = self._now()
        existing = self.get_membership(user_id=user_id, organization_id=organization_id, workspace_id=workspace_id, include_disabled=True)
        with self._connect() as connection:
            if existing:
                connection.execute(
                    """
                    UPDATE memberships
                    SET roles_json = ?, status = ?, updated_at = ?
                    WHERE membership_id = ?
                    """,
                    (json.dumps(clean_roles, ensure_ascii=False), status, now, existing["membership_id"]),
                )
                membership_id = existing["membership_id"]
                created_at = existing["created_at"]
            else:
                membership_id = f"mbr_{uuid.uuid4().hex[:16]}"
                created_at = now
                connection.execute(
                    """
                    INSERT INTO memberships (
                        membership_id, user_id, organization_id, workspace_id,
                        roles_json, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (membership_id, user_id, organization_id, workspace_id, json.dumps(clean_roles, ensure_ascii=False), status, now, now),
                )
        return {
            "membership_id": membership_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "workspace_id": workspace_id,
            "roles": clean_roles,
            "status": status,
            "created_at": created_at,
            "updated_at": now,
        }

    def get_membership(
        self,
        *,
        user_id: str,
        organization_id: str,
        workspace_id: str,
        include_disabled: bool = False,
    ) -> dict[str, Any] | None:
        query = """
            SELECT * FROM memberships
            WHERE user_id = ? AND organization_id = ? AND workspace_id = ?
        """
        params: list[Any] = [user_id, organization_id, workspace_id]
        if not include_disabled:
            query += " AND status = 'active'"
        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        return self._row_to_dict(row) if row else None

    def list_memberships(self, *, organization_id: str, workspace_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        clauses = ["organization_id = ?"]
        params: list[Any] = [organization_id]
        if workspace_id:
            clauses.append("workspace_id = ?")
            params.append(workspace_id)
        params.append(max(1, min(int(limit or 100), 500)))
        query = f"""
            SELECT * FROM memberships
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC
            LIMIT ?
        """
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memberships (
                    membership_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    roles_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, organization_id, workspace_id)
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
    def _clean_roles(roles: list[str]) -> list[str]:
        return list(dict.fromkeys(str(role).strip() for role in roles if str(role).strip()))

    @staticmethod
    def _load_roles(value: str | None) -> list[str]:
        try:
            roles = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        return MembershipStore._clean_roles(roles)

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "membership_id": row["membership_id"],
            "user_id": row["user_id"],
            "organization_id": row["organization_id"],
            "workspace_id": row["workspace_id"],
            "roles": self._load_roles(row["roles_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
