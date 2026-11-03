"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / ".tmp" / "savings.db"
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def database_path() -> Path:
    return Path(os.getenv("SAVINGS_DB", DEFAULT_DB_PATH))


def auth_user() -> str:
    return os.getenv("SAVINGS_USER", "admin")


def auth_password() -> str:
    """Basic auth is enabled only when a password is configured."""
    return os.getenv("SAVINGS_PASSWORD", "")
