from typing import List, Optional

from pydantic import BaseModel

from config.settings import Settings


class UploadResponse(BaseModel):
    status: str
    message: str
    processed_files: List[str] = []


class DocumentStatus(BaseModel):
    doc_id: str
    file_name: str
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    file_size: int = 0
    status: str
    message: str = ""
    node_count: int = 0
    error: str = ""
    created_at: str
    updated_at: str


class DocsListResponse(BaseModel):
    documents: List[DocumentStatus]


class ChatMessage(BaseModel):
    role: str
    content: str
    sources: List[str]


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    query: str
    model: Optional[str] = Settings.MODEL
    knowledge_bool: bool = None
    temperature: Optional[float] = Settings.TEMPERATURE
    max_tokens: int = 100


class ChatResponse(BaseModel):
    session_id: str
    messages: ChatMessage


class ChatSession(BaseModel):
    session_id: str
    title: str
    first_query: str = ""
    last_message: str = ""
    message_count: int = 0
    created_at: str
    updated_at: str


class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSession]


class ClearRequest(BaseModel):
    session_id: str


class CommonResponse(BaseModel):
    status: str
    message: str


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    message: str
    access_token: str
    token_type: str
    username: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class UserInDB(User):
    hashed_password: str


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
