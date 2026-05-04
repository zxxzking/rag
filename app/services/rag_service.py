import os
import shutil
import tempfile
from typing import Any, Dict, List, Tuple

from core.application import RAGApplication
from core.chatSessionManager import ChatSessionManager
from core.documentManager import DocumentManager
from utils.logger import setup_logger

logger = setup_logger(__name__)


class RAGService:
    """Adapter between FastAPI routers and the core RAG application."""

    def __init__(self):
        self.app = RAGApplication()
        self.doc_manager = DocumentManager()
        self.session_manager = ChatSessionManager()

    def upload_and_process_files(self, files: List[bytes], filenames: List[str]) -> Tuple[str, str, List[str]]:
        tmpdir = tempfile.mkdtemp(prefix="rag_upload_")
        paths = []
        try:
            for name, content in zip(filenames, files):
                p = os.path.join(tmpdir, name)
                with open(p, "wb") as f:
                    f.write(content)
                paths.append(p)

            return self.upload_and_process_file_paths(paths, filenames)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def upload_and_process_file_paths(self, paths: List[str], filenames: List[str]) -> Tuple[str, str, List[str]]:
        logger.info(f"Uploaded documents: {paths}")
        for path, filename in zip(paths, filenames):
            self.doc_manager.mark_processing(filename, path)

        try:
            result = self.app.upload_and_process_files(paths)
            if isinstance(result, tuple):
                status = result[0]
                status_text = result[1] if len(result) > 1 else ""
            else:
                status = "error"
                status_text = str(result)

            node_count = (
                len(result[2])
                if isinstance(result, tuple) and len(result) > 2 and isinstance(result[2], list)
                else 0
            )

            if status == "success":
                for path, filename in zip(paths, filenames):
                    self.doc_manager.mark_completed(
                        filename,
                        path,
                        message=status_text,
                        node_count=node_count,
                    )
            else:
                for path, filename in zip(paths, filenames):
                    self.doc_manager.mark_failed(filename, path, status_text)

            return status, status_text, filenames
        except Exception as e:
            error = str(e)
            for path, filename in zip(paths, filenames):
                self.doc_manager.mark_failed(filename, path, error)
            raise

    def get_documents(self) -> List[Dict[str, Any]]:
        return self.doc_manager.list_documents()

    async def query(
        self,
        session_id: str,
        query: str,
        model: str,
        knowledge_bool: bool,
        temperature: float,
        max_tokens: int,
        username: str = None,
    ):
        session = self.session_manager.ensure_session(
            username=username or session_id,
            query=query,
            session_id=session_id,
        )
        self.app.update_model_config(model, temperature, max_tokens)
        try:
            answer, sources = await self.app.query_documents(
                session_id=session["session_id"],
                query=query,
                knowledge_bool=knowledge_bool,
            )
        except Exception:
            if session.get("is_new"):
                self.session_manager.delete_session(username or session_id, session["session_id"])
            raise
        if isinstance(answer, str) and answer.startswith("查询失败"):
            if session.get("is_new"):
                self.session_manager.delete_session(username or session_id, session["session_id"])
            return session["session_id"], answer, sources
        self.session_manager.touch_session(
            username=username or session_id,
            session_id=session["session_id"],
            last_message=query,
            message_increment=1,
        )
        return session["session_id"], answer, sources

    async def query_stream(
        self,
        session_id: str,
        query: str,
        model: str,
        knowledge_bool: bool,
        temperature: float,
        max_tokens: int,
        username: str = None,
    ):
        session = self.session_manager.ensure_session(
            username=username or session_id,
            query=query,
            session_id=session_id,
        )
        yield {
            "type": "session",
            "finished": False,
            "content": {
                "session_id": session["session_id"],
                "title": session["title"],
            },
        }
        self.app.update_model_config(model, temperature, max_tokens)
        completed = False
        try:
            async for chunk in self.app.query_documents_stream(
                session_id=session["session_id"],
                query=query,
                knowledge_bool=knowledge_bool,
            ):
                if chunk.get("type") == "complete":
                    completed = True
                yield chunk
        except Exception:
            if session.get("is_new"):
                self.session_manager.delete_session(username or session_id, session["session_id"])
            raise
        if completed:
            self.session_manager.touch_session(
                username=username or session_id,
                session_id=session["session_id"],
                last_message=query,
                message_increment=1,
            )
        elif session.get("is_new"):
            self.session_manager.delete_session(username or session_id, session["session_id"])

    def get_session(self, session_id: str):
        return self.app.get_session_history(session_id)

    def clear_session(self, session_id: str):
        self.app.clear_session(session_id)

    def list_chat_sessions(self, username: str):
        return self.session_manager.list_sessions(username)

    def delete_chat_session(self, username: str, session_id: str) -> bool:
        return self.session_manager.delete_session(username, session_id)

    def clear_user_chat_sessions(self, username: str):
        self.session_manager.clear_user_sessions(username)

    def reset_system(self):
        self.app.reset()
        if hasattr(self.doc_manager, "clear_all"):
            self.doc_manager.clear_all()
        if hasattr(self.session_manager, "clear_all"):
            self.session_manager.clear_all()
