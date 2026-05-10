from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class SessionStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_session(
        self,
        *,
        user_id: str,
        organization_id: str,
        workspace_id: str,
        roles: list[str] | None = None,
        ttl_hours: int = 12,
    ) -> dict[str, Any]:
        session_id = f"sess_{secrets.token_hex(12)}"
        secret = secrets.token_urlsafe(32)
        token = f"lxs_{session_id}_{secret}"
        now = self._now()
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=max(1, min(int(ttl_hours or 12), 168)))).isoformat()
        clean_roles = [str(role).strip() for role in roles or ["legal_reviewer"] if str(role).strip()]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id, token_hash, user_id, organization_id, workspace_id,
                    roles_json, created_at, last_seen_at, expires_at, revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    session_id,
                    self._hash_token(token),
                    user_id,
                    organization_id,
                    workspace_id,
                    json.dumps(clean_roles, ensure_ascii=False),
                    now,
                    now,
                    expires_at,
                ),
            )
        return {
            "session_id": session_id,
            "session_token": token,
            "user_id": user_id,
            "organization_id": organization_id,
            "workspace_id": workspace_id,
            "roles": clean_roles,
            "expires_at": expires_at,
        }

    def get_session(self, token: str) -> dict[str, Any] | None:
        token_hash = self._hash_token(token)
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE token_hash = ?", (token_hash,)).fetchone()
            if row is None:
                return None
            session = self._row_to_dict(row)
            if session.get("revoked_at") or self._is_expired(session.get("expires_at")):
                return None
            connection.execute("UPDATE sessions SET last_seen_at = ? WHERE session_id = ?", (self._now(), session["session_id"]))
        return session

    def revoke_session(self, token: str) -> dict[str, Any] | None:
        token_hash = self._hash_token(token)
        now = self._now()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE token_hash = ?", (token_hash,)).fetchone()
            if row is None:
                return None
            session = self._row_to_dict(row)
            connection.execute("UPDATE sessions SET revoked_at = ? WHERE session_id = ?", (now, session["session_id"]))
        session["revoked_at"] = now
        return session

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    roles_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _is_expired(expires_at: str | None) -> bool:
        if not expires_at:
            return True
        expires = datetime.fromisoformat(expires_at)
        return expires <= datetime.now(timezone.utc)

    @staticmethod
    def _load_roles(value: str | None) -> list[str]:
        try:
            roles = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        return [str(role) for role in roles if str(role).strip()]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "organization_id": row["organization_id"],
            "workspace_id": row["workspace_id"],
            "roles": self._load_roles(row["roles_json"]),
            "created_at": row["created_at"],
            "last_seen_at": row["last_seen_at"],
            "expires_at": row["expires_at"],
            "revoked_at": row["revoked_at"],
        }
