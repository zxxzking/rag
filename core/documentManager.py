import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import Settings as AppSettings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DocumentManager:
    """Manage document processing status in SQLite."""

    def __init__(self, db_path: str = AppSettings.SQLITE_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_path TEXT,
                    file_type TEXT,
                    file_size INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    message TEXT DEFAULT '',
                    node_count INTEGER DEFAULT 0,
                    error TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_status
                ON documents(status)
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def build_doc_id(filename: str) -> str:
        return f"knowledge_base/{Path(filename).name}"

    def upsert_document(
        self,
        *,
        file_name: str,
        file_path: str,
        status: str,
        message: str = "",
        node_count: int = 0,
        error: str = "",
        file_size: Optional[int] = None,
    ) -> None:
        path = Path(file_path)
        safe_file_name = Path(file_name).name
        doc_id = self.build_doc_id(safe_file_name)
        now = self._now()
        resolved_file_size = file_size
        if resolved_file_size is None:
            resolved_file_size = path.stat().st_size if path.exists() else 0

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    doc_id, file_name, file_path, file_type, file_size,
                    status, message, node_count, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    file_name = excluded.file_name,
                    file_path = excluded.file_path,
                    file_type = excluded.file_type,
                    file_size = excluded.file_size,
                    status = excluded.status,
                    message = excluded.message,
                    node_count = excluded.node_count,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (
                    doc_id,
                    safe_file_name,
                    str(path),
                    path.suffix.lower(),
                    resolved_file_size,
                    status,
                    message,
                    node_count,
                    error,
                    now,
                    now,
                ),
            )

    def mark_processing(self, file_name: str, file_path: str) -> None:
        self.upsert_document(
            file_name=file_name,
            file_path=file_path,
            status="processing",
            message="document is being parsed and embedded",
            node_count=0,
            error="",
        )

    def mark_completed(
        self,
        file_name: str,
        file_path: str,
        *,
        message: str = "",
        node_count: int = 0,
    ) -> None:
        self.upsert_document(
            file_name=file_name,
            file_path=file_path,
            status="completed",
            message=message or "document has been vectorized",
            node_count=node_count,
            error="",
        )

    def mark_failed(self, file_name: str, file_path: str, error: str) -> None:
        self.upsert_document(
            file_name=file_name,
            file_path=file_path,
            status="failed",
            message="document processing failed",
            node_count=0,
            error=error,
        )

    def list_documents(self) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        doc_id, file_name, file_path, file_type, file_size,
                        status, message, node_count, error, created_at, updated_at
                    FROM documents
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list documents from SQLite: {e}")
            return []

    def get_document_names_only(self) -> List[str]:
        return [doc["file_name"] for doc in self.list_documents()]

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents")


if __name__ == "__main__":
    print(DocumentManager().list_documents())
