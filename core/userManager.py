import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import Settings as AppSettings


class UserManager:
    """Manage users in SQLite."""

    def __init__(self, db_path: str = AppSettings.SQLITE_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    hashed_password TEXT NOT NULL,
                    email TEXT,
                    full_name TEXT,
                    role TEXT NOT NULL DEFAULT 'user',
                    disabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(users)").fetchall()
            }
            if "role" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username)
                """
            )

    def ensure_default_user(self, username: str, hashed_password: str) -> None:
        existing = self.get_user(username)
        if existing:
            if existing.get("role") != "admin":
                with self._connect() as conn:
                    conn.execute(
                        "UPDATE users SET role = 'admin', updated_at = ? WHERE username = ?",
                        (self._now(), username),
                    )
            return
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    username, hashed_password, email, full_name, role,
                    disabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'admin', 0, ?, ?)
                """,
                (
                    username,
                    hashed_password,
                    "admin@example.com",
                    "Administrator",
                    now,
                    now,
                ),
            )

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT username, hashed_password, email, full_name, role, disabled
                FROM users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if not row:
            return None
        user = dict(row)
        user["disabled"] = bool(user["disabled"])
        return user

    def create_user(
        self,
        *,
        username: str,
        hashed_password: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: str = "user",
    ) -> Dict[str, Any]:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    username, hashed_password, email, full_name, role,
                    disabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (username, hashed_password, email, full_name, role, now, now),
            )
        return self.get_user(username)

    def update_user(
        self,
        *,
        username: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        user = self.get_user(username)
        if not user:
            return None

        next_email = email if email is not None else user.get("email")
        next_full_name = full_name if full_name is not None else user.get("full_name")
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET email = ?,
                    full_name = ?,
                    updated_at = ?
                WHERE username = ?
                """,
                (next_email, next_full_name, now, username),
            )
        return self.get_user(username)

    def delete_user(self, username: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM users WHERE username = ?",
                (username,),
            )
            return cursor.rowcount > 0

    def list_users(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT username, hashed_password, email, full_name, role, disabled
                FROM users
                ORDER BY username
                """
            ).fetchall()

        users = []
        for row in rows:
            user = dict(row)
            user["disabled"] = bool(user["disabled"])
            users.append(user)
        return users
