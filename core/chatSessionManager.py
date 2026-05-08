import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import Settings as AppSettings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ChatSessionManager:
    """Manage chat sessions in SQLite."""

    def __init__(self, db_path: str = AppSettings.SQLITE_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def close(self) -> None:
        """Compatibility hook for tests; connections are short-lived."""
        return None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL,
                    title TEXT NOT NULL,
                    first_query TEXT NOT NULL DEFAULT '',
                    last_message TEXT NOT NULL DEFAULT '',
                    message_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
                ON chat_sessions(username, updated_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT NOT NULL DEFAULT '[]',
                    model TEXT,
                    knowledge_bool INTEGER NOT NULL DEFAULT 0,
                    temperature REAL,
                    max_tokens INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
                ON chat_messages(session_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created
                ON chat_messages(username, created_at)
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def build_title(query: str, max_length: int = 18) -> str:
        text = " ".join((query or "").strip().split())
        if not text:
            return "New chat"
        return text[:max_length]

    def ensure_session(
        self,
        *,
        username: str,
        query: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = self._now()
        requested_session_id = (session_id or "").strip()

        with self._connect() as conn:
            if requested_session_id:
                row = conn.execute(
                    """
                    SELECT session_id, username, title, first_query, last_message,
                           message_count, created_at, updated_at
                    FROM chat_sessions
                    WHERE session_id = ? AND username = ?
                    """,
                    (requested_session_id, username),
                ).fetchone()
                if row:
                    session = dict(row)
                    session["is_new"] = False
                    return session

                id_owner = conn.execute(
                    """
                    SELECT username
                    FROM chat_sessions
                    WHERE session_id = ?
                    """,
                    (requested_session_id,),
                ).fetchone()
                if id_owner:
                    requested_session_id = ""

            new_session_id = requested_session_id or str(uuid.uuid4())
            title = self.build_title(query)
            conn.execute(
                """
                INSERT INTO chat_sessions (
                    session_id, username, title, first_query, last_message,
                    message_count, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    new_session_id,
                    username,
                    title,
                    query or "",
                    query or "",
                    now,
                    now,
                ),
            )

            return {
                "session_id": new_session_id,
                "username": username,
                "title": title,
                "first_query": query or "",
                "last_message": query or "",
                "message_count": 0,
                "created_at": now,
                "updated_at": now,
                "is_new": True,
            }

    def touch_session(
        self,
        *,
        username: str,
        session_id: str,
        last_message: str,
        message_increment: int = 1,
    ) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE chat_sessions
                SET last_message = ?,
                    message_count = message_count + ?,
                    updated_at = ?
                WHERE session_id = ? AND username = ?
                """,
                (
                    last_message or "",
                    message_increment,
                    now,
                    session_id,
                    username,
                ),
            )

    def add_message(
        self,
        *,
        username: str,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[List[str]] = None,
        model: Optional[str] = None,
        knowledge_bool: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (
                    session_id, username, role, content, sources, model,
                    knowledge_bool, temperature, max_tokens, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    username,
                    role,
                    content or "",
                    json.dumps(sources or [], ensure_ascii=False),
                    model,
                    1 if knowledge_bool else 0,
                    temperature,
                    max_tokens,
                    now,
                ),
            )

    def add_exchange(
        self,
        *,
        username: str,
        session_id: str,
        query: str,
        answer: str,
        sources: Optional[List[str]] = None,
        model: Optional[str] = None,
        knowledge_bool: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        self.add_message(
            username=username,
            session_id=session_id,
            role="user",
            content=query,
            sources=[],
            model=model,
            knowledge_bool=knowledge_bool,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.add_message(
            username=username,
            session_id=session_id,
            role="assistant",
            content=answer,
            sources=sources or [],
            model=model,
            knowledge_bool=knowledge_bool,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def list_messages(
        self,
        *,
        username: str,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [username]
        where = "WHERE username = ?"
        if session_id:
            where += " AND session_id = ?"
            params.append(session_id)

        try:
            with self._connect() as conn:
                rows = conn.execute(
                    f"""
                    SELECT session_id, role, content, sources, model, knowledge_bool,
                           temperature, max_tokens, created_at
                    FROM chat_messages
                    {where}
                    ORDER BY created_at ASC, id ASC
                    """,
                    params,
                ).fetchall()
        except Exception as e:
            logger.error(f"Failed to list chat messages from SQLite: {e}")
            return []

        messages = []
        for row in rows:
            message = dict(row)
            try:
                message["sources"] = json.loads(message.get("sources") or "[]")
            except json.JSONDecodeError:
                message["sources"] = []
            message["knowledge_bool"] = bool(message.get("knowledge_bool"))
            messages.append(message)
        return messages

    def clear_session_messages(self, username: str, session_id: str) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM chat_messages
                WHERE username = ? AND session_id = ?
                """,
                (username, session_id),
            )
            conn.execute(
                """
                UPDATE chat_sessions
                SET last_message = '',
                    message_count = 0,
                    updated_at = ?
                WHERE username = ? AND session_id = ?
                """,
                (now, username, session_id),
            )

    def list_sessions(self, username: str) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT session_id, title, first_query, last_message,
                           message_count, created_at, updated_at
                    FROM chat_sessions
                    WHERE username = ?
                    ORDER BY updated_at DESC
                    """,
                    (username,),
                ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list chat sessions from SQLite: {e}")
            return []

    def delete_session(self, username: str, session_id: str) -> bool:
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM chat_messages
                WHERE username = ? AND session_id = ?
                """,
                (username, session_id),
            )
            cursor = conn.execute(
                """
                DELETE FROM chat_sessions
                WHERE username = ? AND session_id = ?
                """,
                (username, session_id),
            )
            return cursor.rowcount > 0

    def clear_user_sessions(self, username: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chat_messages WHERE username = ?", (username,))
            conn.execute("DELETE FROM chat_sessions WHERE username = ?", (username,))

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chat_messages")
            conn.execute("DELETE FROM chat_sessions")
