"""SQLAlchemy ORM 모델.

앱이 직접 소유하고 관리하는 테이블 2개:
- tb_chat_session: 로그인 세션 정보
- tb_chat_message: 대화 메시지 (HR / 업무 가이드 / 용어 사전)
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Boolean, DateTime, Integer, SmallInteger, Text, ForeignKey, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database.engine import Base


class ChatSession(Base):
    __tablename__ = "tb_chat_session"
    __table_args__ = (
        Index("ix_chat_session_user_id", "user_id"),
        {"schema": "aichat"},
    )

    session_id:    Mapped[str]      = mapped_column(String(36), primary_key=True)
    user_id:       Mapped[str]      = mapped_column(String(50), nullable=False)
    created_at:    Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_accessed: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active:     Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)

    messages: Mapped[List[ChatMessage]] = relationship(
        "ChatMessage",
        back_populates="session",
        order_by="ChatMessage.created_at",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    __tablename__ = "tb_chat_message"
    __table_args__ = (
        Index("ix_chat_message_session_service", "session_id", "service_type"),
        {"schema": "aichat"},
    )

    message_id:   Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id:   Mapped[str]  = mapped_column(
        String(36),
        ForeignKey("aichat.tb_chat_session.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    service_type: Mapped[str]  = mapped_column(String(20), nullable=False)   # 'hr' / 'glossary' / 'work_guide'
    role:         Mapped[str]  = mapped_column(String(20), nullable=False)   # 'user' / 'assistant'
    content:      Mapped[str]           = mapped_column(Text, nullable=False)
    created_at:   Mapped[datetime]       = mapped_column(DateTime, nullable=False)
    rating:       Mapped[Optional[int]]  = mapped_column(SmallInteger, nullable=True)
    rated_at:     Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")
