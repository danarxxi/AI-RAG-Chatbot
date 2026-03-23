from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class GlossaryTerm(BaseModel):
    """Glossary term model representing a word from the database."""
    word_id: str
    word_name: str
    word_english_name: Optional[str] = None
    definition: str
    category: str


class GlossaryQueryRequest(BaseModel):
    """Request model for glossary query."""
    query: str
    session_id: str


class GlossaryQueryResponse(BaseModel):
    """Response model for glossary query."""
    answer: str
    source_terms: List[GlossaryTerm]
    session_id: str
    timestamp: datetime
    message_id: int = 0
    executed_query: Optional[str] = None
