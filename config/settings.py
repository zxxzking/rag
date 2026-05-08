import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()


PROJECT_ROOT = Path(__file__).parent.parent


def path_from_env(name: str, default: Path) -> str:
    value = os.getenv(name)
    if not value:
        return str(default)
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


class Settings:
    """Application configuration."""

    PROJECT_ROOT: Path = PROJECT_ROOT

    # Auth
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY",
        "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    ENABLE_DEFAULT_ADMIN: bool = os.getenv("ENABLE_DEFAULT_ADMIN", "true").lower() == "true"
    DEFAULT_ADMIN_USERNAME: str = os.getenv("DEFAULT_ADMIN_USERNAME", "root")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "root")

    # LLM
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "deepseek-r1:1.5b")
    OLLAMA_REQUEST_TIMEOUT: float = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "600.0"))
    API_KEY: Optional[str] = os.getenv("DASHSCOPE_API_KEY")
    API_BASE_URL: Optional[str] = os.getenv("DASHSCOPE_BASE_URL")
    MODEL: str = os.getenv("MODEL", OLLAMA_MODEL)
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))

    # Local models
    EMBEDDING_MODEL_PATH: str = os.getenv(
        "EMBEDDING_MODEL_PATH",
        r"D:\llm\Local_model\BAAI\bge-large-zh-v1___5",
    )
    RERANK_MODEL_PATH: str = os.getenv(
        "RERANK_MODEL_PATH",
        r"D:\llm\Local_model\BAAI\bge-reranker-large",
    )

    # Ingestion
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "512"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))
    TITLE_EXTRACTOR_NODES: int = int(os.getenv("TITLE_EXTRACTOR_NODES", "5"))

    # Retrieval
    SIMILARITY_TOP_K: int = int(os.getenv("SIMILARITY_TOP_K", "5"))
    RERANK_TOP_K: int = int(os.getenv("RERANK_TOP_K", "3"))
    SIMILARITY_CUTOFF: float = float(os.getenv("SIMILARITY_CUTOFF", "0.5"))

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6380"))
    REDIS_INDEX_NAMESPACE: str = os.getenv("REDIS_INDEX_NAMESPACE", "redis_index")
    REDIS_DOCS_NAMESPACE: str = os.getenv("REDIS_DOCS_NAMESPACE", "redis_docs")
    REDIS_CACHE_COLLECTION: str = os.getenv("REDIS_CACHE_COLLECTION", "redis_cache")

    # Storage
    CHROMA_PERSIST_DIR: str = path_from_env("CHROMA_PERSIST_DIR", PROJECT_ROOT / "file/chroma_db")
    CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "quickstart")
    BM25_PERSIST_DIR: str = path_from_env("BM25_PERSIST_DIR", PROJECT_ROOT / "file/storage_bm25")
    DOCUMENTS_DIR: str = path_from_env("DOCUMENTS_DIR", PROJECT_ROOT / "file/documents")
    RESOURCES_DIR: str = path_from_env("RESOURCES_DIR", PROJECT_ROOT / "file/resources")
    DEFAULT_PERSIST_DIR: str = path_from_env("DEFAULT_PERSIST_DIR", PROJECT_ROOT / "file/storage")
    PDF_IMAGE_DIR: str = path_from_env("PDF_IMAGE_DIR", PROJECT_ROOT / "file/image")
    LOG_DIR: str = path_from_env("LOG_DIR", PROJECT_ROOT / "file")
    SQLITE_DB_PATH: str = path_from_env("SQLITE_DB_PATH", PROJECT_ROOT / "file/app.db")

    SUPPORTED_FILE_TYPES: list = [".txt", ".pdf", ".docx", ".md"]

    @classmethod
    def validate_api_key(cls) -> bool:
        return cls.API_KEY is not None and len(cls.API_KEY.strip()) > 0
