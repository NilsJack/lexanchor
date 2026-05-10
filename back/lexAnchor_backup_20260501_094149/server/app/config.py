from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.server_root = Path(__file__).resolve().parents[1]
        self.rules_dir = self.server_root / "rules"
        self.storage_dir = self.server_root / "storage"
        self.uploads_dir = self.storage_dir / "uploads"
        self.artifacts_dir = self.storage_dir / "artifacts"
        self.database_path = self.storage_dir / "lexanchor.sqlite3"
        self.default_ruleset = "rules_v0.1"
        self.default_user_id = os.getenv("LEXANCHOR_DEFAULT_USER_ID", "default_user")
        self.default_organization_id = "default_org"
        self.default_workspace_id = "default_workspace"
        self.default_extraction_backend = os.getenv("LEXANCHOR_EXTRACTION_BACKEND", "auto")
        self.default_grounding_backend = os.getenv("LEXANCHOR_GROUNDING_BACKEND", "auto")

    def ensure_directories(self) -> None:
        for directory in (self.storage_dir, self.uploads_dir, self.artifacts_dir):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
