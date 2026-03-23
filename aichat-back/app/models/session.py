from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class ServiceType(str, Enum):
    """Enum for different chatbot services."""
    HR = "hr"
    GLOSSARY = "glossary"
    WORK_GUIDE = "work_guide"


class Message(BaseModel):
    """Individual message in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime


class Session(BaseModel):
    """User session with separate conversation histories per service."""
    session_id: str
    user_id: str
    created_at: datetime
    last_accessed: datetime
    # Separate conversation histories for each service (hr, glossary, etc.)
    conversation_histories: Dict[str, List[Message]] = {
        ServiceType.HR: [],
        ServiceType.GLOSSARY: [],
        ServiceType.WORK_GUIDE: []
    }


class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str = "bearer"
    session_id: str
    user_id: str
    user_name: str


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
