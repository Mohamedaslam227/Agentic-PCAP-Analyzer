from pydantic import BaseModel, Field
from typing import List, Optional


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    database: bool = False
    redis: bool = False


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    message: str = "File accepted"


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8)
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    session_id: str
    answer: str


class ChatStreamTokenEvent(BaseModel):
    """Single SSE token event emitted during streaming."""
    token: str = ""
    done: bool = False
    answer: Optional[str] = None   # populated only in the final done=True event
    cached: Optional[bool] = None
    error: Optional[str] = None


class ResearchRequest(BaseModel):
    session_id: Optional[str] = None
    question: str = Field(min_length=1, max_length=4000)


class ResearchResponse(BaseModel):
    result: str


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=8, max_length=256)


class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    username: str
    email: str


# ── Processing status ──────────────────────────────────────────────────────────

class ProcessingStatusResponse(BaseModel):
    session_id: str
    status: str                      # pending | processing | completed | failed
    progress_pct: float = 0.0
    total_packets: int = 0
    total_flows: int = 0
    unique_aps: int = 0
    unique_clients: int = 0
    capture_type: Optional[str] = None
    wifi_bands: List[str] = []
    channels: List[int] = []
    error: Optional[str] = None


# ── Research jobs ──────────────────────────────────────────────────────────────

class ResearchCreateResponse(BaseModel):
    job_id: str
    status: str = "pending"


class ResearchResultResponse(BaseModel):
    job_id: str
    status: str                      # pending | running | completed | failed
    result: Optional[str] = None
