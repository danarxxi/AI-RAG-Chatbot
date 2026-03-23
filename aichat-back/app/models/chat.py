from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: str


class SourceDocument(BaseModel):
    """Source document model for RAG citations."""
    content: str
    document_name: str
    score: float


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    session_id: str
    timestamp: datetime
    sources: List[SourceDocument] = []
    message_id: int


class FeedbackRequest(BaseModel):
    """별점 피드백 요청 모델."""
    rating: int

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("별점은 1~5 사이여야 합니다")
        return v
