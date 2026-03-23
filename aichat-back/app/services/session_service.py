from datetime import datetime, timedelta
from typing import Dict, Optional, List
from app.models.session import Session, Message, ServiceType
from app.config import get_settings
from app.utils.logger import setup_logger
from fastapi import HTTPException, status

settings = get_settings()
logger = setup_logger(__name__)


class SessionService:
    """세션 관리 서비스.

    전략: 인메모리(RAG 멀티턴 컨텍스트용) + DB(영속화) 병행
    - 메시지 발생 시 → 인메모리 저장 + DB INSERT 동시 수행
    - 인메모리에 없는 세션 → DB에서 복원 (서버 재시작 대응)
    """

    # 클래스 레벨 공유 세션 저장소
    _sessions: Dict[str, Session] = {}

    def __init__(self):
        pass

    # ──────────────────────────────────────────────
    # 세션 생성 / 조회 / 삭제
    # ──────────────────────────────────────────────

    def create_session(self, session_id: str, user_id: str) -> Session:
        """새 세션 생성. 인메모리 + DB 동시 저장."""
        now = datetime.now()
        session = Session(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            last_accessed=now,
            conversation_histories={
                ServiceType.HR: [],
                ServiceType.GLOSSARY: [],
                ServiceType.WORK_GUIDE: [],
            },
        )
        self._sessions[session_id] = session

        # DB 저장
        self._db_create_session(session_id, user_id, now)

        logger.info(f"Session created: {session_id} for user: {user_id}")
        return session

    def get_session(self, session_id: str) -> Session:
        """세션 조회. 인메모리에 없으면 DB에서 복원."""
        session = self._sessions.get(session_id)

        if not session:
            # 서버 재시작 등으로 인메모리에 없는 경우 DB에서 복원
            session = self._restore_session_from_db(session_id)
            if not session:
                logger.warning(f"Session not found: {session_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session not found or expired",
                )

        # 만료 체크
        expiry_time = session.last_accessed + timedelta(minutes=settings.session_expire_minutes)
        if datetime.now() > expiry_time:
            logger.warning(f"Session expired: {session_id}")
            self.delete_session(session_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired",
            )

        session.last_accessed = datetime.now()
        return session

    def delete_session(self, session_id: str) -> None:
        """세션 삭제. 인메모리 제거 + DB is_active=False."""
        if session_id in self._sessions:
            del self._sessions[session_id]

        self._db_deactivate_session(session_id)
        logger.info(f"Session deleted: {session_id}")

    # ──────────────────────────────────────────────
    # 메시지 관리
    # ──────────────────────────────────────────────

    def add_message(self, session_id: str, role: str, content: str, service_type: ServiceType) -> int:
        """메시지 추가. 인메모리 저장 + DB INSERT. 생성된 message_id 반환."""
        session = self.get_session(session_id)
        now = datetime.now()

        message = Message(role=role, content=content, timestamp=now)

        service_history = session.conversation_histories.get(service_type, [])
        service_history.append(message)
        session.conversation_histories[service_type] = service_history

        # 최대 10턴(메시지 20개) 유지
        max_messages = settings.max_conversation_turns * 2
        if len(service_history) > max_messages:
            session.conversation_histories[service_type] = service_history[-max_messages:]

        # DB 저장
        return self._db_insert_message(session_id, service_type.value, role, content, now)

    def get_conversation_history(self, session_id: str, service_type: ServiceType) -> List[Message]:
        """현재 세션의 특정 서비스 대화 이력 반환 (인메모리)."""
        session = self.get_session(session_id)
        return session.conversation_histories.get(service_type, [])

    def clear_conversation_history(self, session_id: str, service_type: ServiceType) -> None:
        """새 대화 시작 시 특정 서비스의 인메모리 이력 초기화."""
        session = self.get_session(session_id)
        session.conversation_histories[service_type] = []
        logger.info(f"Conversation cleared for session {session_id}, service {service_type}")

    # ──────────────────────────────────────────────
    # 히스토리 조회 (DB)
    # ──────────────────────────────────────────────

    def get_user_sessions(self, user_id: str, service_type: str) -> List[dict]:
        """사용자의 10일 이내 과거 세션 목록 반환."""
        from app.database.engine import SessionLocal
        from app.database.orm_models import ChatSession as DBChatSession, ChatMessage as DBChatMessage

        cutoff_date = datetime.now() - timedelta(days=10)
        db = SessionLocal()
        try:
            # 해당 service_type 메시지가 존재하는 세션만, 10일 이내, 최신순
            sessions = (
                db.query(DBChatSession)
                .join(DBChatMessage, DBChatSession.session_id == DBChatMessage.session_id)
                .filter(
                    DBChatSession.user_id == user_id,
                    DBChatSession.created_at >= cutoff_date,
                    DBChatMessage.service_type == service_type,
                )
                .distinct()
                .order_by(DBChatSession.created_at.desc())
                .all()
            )

            result = []
            for s in sessions:
                first_msg = (
                    db.query(DBChatMessage)
                    .filter(
                        DBChatMessage.session_id == s.session_id,
                        DBChatMessage.service_type == service_type,
                        DBChatMessage.role == "user",
                    )
                    .order_by(DBChatMessage.created_at)
                    .first()
                )
                msg_count = (
                    db.query(DBChatMessage)
                    .filter(
                        DBChatMessage.session_id == s.session_id,
                        DBChatMessage.service_type == service_type,
                    )
                    .count()
                )
                result.append(
                    {
                        "session_id": s.session_id,
                        "created_at": s.created_at,
                        "message_preview": first_msg.content[:80] if first_msg else "",
                        "message_count": msg_count,
                    }
                )
            return result
        except Exception as e:
            logger.error(f"과거 세션 목록 조회 실패: {e}")
            return []
        finally:
            db.close()

    def get_session_messages_from_db(self, session_id: str, service_type: str) -> List[Message]:
        """DB에서 특정 세션의 특정 서비스 메시지 전체 반환."""
        from app.database.engine import SessionLocal
        from app.database.orm_models import ChatMessage as DBChatMessage

        db = SessionLocal()
        try:
            rows = (
                db.query(DBChatMessage)
                .filter(
                    DBChatMessage.session_id == session_id,
                    DBChatMessage.service_type == service_type,
                )
                .order_by(DBChatMessage.created_at)
                .all()
            )
            return [Message(role=m.role, content=m.content, timestamp=m.created_at) for m in rows]
        except Exception as e:
            logger.error(f"DB 메시지 조회 실패: {e}")
            return []
        finally:
            db.close()

    # ──────────────────────────────────────────────
    # 세션 만료 정리 (백그라운드 태스크)
    # ──────────────────────────────────────────────

    def clear_expired_sessions(self) -> None:
        """만료된 인메모리 세션 정리."""
        now = datetime.now()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now > session.last_accessed + timedelta(minutes=settings.session_expire_minutes)
        ]
        for session_id in expired:
            self.delete_session(session_id)

        if expired:
            logger.info(f"Cleared {len(expired)} expired sessions")

        # DB에서 만료된 세션 일괄 비활성화 (서버 재시작·브라우저 강제 종료 등으로 남은 세션 처리)
        db_deactivated = self._db_deactivate_expired_sessions()
        if db_deactivated:
            logger.info(f"DB 만료 세션 비활성화: {db_deactivated}건")

        active_sessions = list(self._sessions.items())
        if active_sessions:
            lines = [f"Active sessions: {len(active_sessions)}"]
            for session_id, session in active_sessions:
                inactive_minutes = (now - session.last_accessed).total_seconds() / 60
                expires_in_minutes = settings.session_expire_minutes - inactive_minutes
                lines.append(
                    f"  - {session_id[:8]}... | {session.user_id} | "
                    f"{inactive_minutes:.1f}m inactive | {expires_in_minutes:.1f}m remaining"
                )
            logger.info("\n".join(lines))
        else:
            logger.info("Active sessions: 0")

    # ──────────────────────────────────────────────
    # DB 헬퍼 (내부 메서드)
    # ──────────────────────────────────────────────

    def _restore_session_from_db(self, session_id: str) -> Optional[Session]:
        """DB에서 세션 복원. 만료된 세션은 None 반환."""
        from app.database.engine import SessionLocal
        from app.database.orm_models import ChatSession as DBChatSession, ChatMessage as DBChatMessage

        db = SessionLocal()
        try:
            db_session = db.get(DBChatSession, session_id)
            if not db_session or not db_session.is_active:
                return None

            # 만료 여부 확인
            expiry_time = db_session.last_accessed + timedelta(minutes=settings.session_expire_minutes)
            if datetime.now() > expiry_time:
                # 만료된 세션은 DB에서도 비활성화 (서버 재시작 후 남은 세션 처리)
                self._db_deactivate_session(session_id)
                return None

            # 서비스별 최근 대화 이력 복원 (RAG 컨텍스트용)
            max_messages = settings.max_conversation_turns * 2
            histories: Dict[str, List[Message]] = {
                ServiceType.HR: [],
                ServiceType.GLOSSARY: [],
                ServiceType.WORK_GUIDE: [],
            }

            for svc in ServiceType:
                db_msgs = (
                    db.query(DBChatMessage)
                    .filter(
                        DBChatMessage.session_id == session_id,
                        DBChatMessage.service_type == svc.value,
                    )
                    .order_by(DBChatMessage.created_at)
                    .all()
                )
                recent = db_msgs[-max_messages:]
                histories[svc] = [
                    Message(role=m.role, content=m.content, timestamp=m.created_at)
                    for m in recent
                ]

            session = Session(
                session_id=db_session.session_id,
                user_id=db_session.user_id,
                created_at=db_session.created_at,
                last_accessed=db_session.last_accessed,
                conversation_histories=histories,
            )
            self._sessions[session_id] = session
            logger.info(f"세션 복원 완료: {session_id}")
            return session

        except Exception as e:
            logger.error(f"세션 복원 실패: {e}")
            return None
        finally:
            db.close()

    def _db_create_session(self, session_id: str, user_id: str, now: datetime) -> None:
        """DB에 세션 레코드 INSERT."""
        from app.database.engine import SessionLocal
        from app.database.orm_models import ChatSession as DBChatSession

        db = SessionLocal()
        try:
            db_session = DBChatSession(
                session_id=session_id,
                user_id=user_id,
                created_at=now,
                last_accessed=now,
                is_active=True,
            )
            db.add(db_session)
            db.commit()
        except Exception as e:
            logger.error(f"DB 세션 저장 실패: {e}")
            db.rollback()
        finally:
            db.close()

    def _db_insert_message(
        self,
        session_id: str,
        service_type: str,
        role: str,
        content: str,
        now: datetime,
    ) -> int:
        """DB에 메시지 INSERT + 세션 last_accessed 갱신. 생성된 message_id 반환."""
        from app.database.engine import SessionLocal
        from app.database.orm_models import ChatSession as DBChatSession, ChatMessage as DBChatMessage

        db = SessionLocal()
        try:
            db_msg = DBChatMessage(
                session_id=session_id,
                service_type=service_type,
                role=role,
                content=content,
                created_at=now,
            )
            db.add(db_msg)
            db_session = db.get(DBChatSession, session_id)
            if db_session:
                db_session.last_accessed = now
            db.commit()
            db.refresh(db_msg)
            return db_msg.message_id
        except Exception as e:
            logger.error(f"DB 메시지 저장 실패: {e}")
            db.rollback()
            return -1
        finally:
            db.close()

    def _db_deactivate_expired_sessions(self) -> int:
        """DB에서 만료된 활성 세션을 일괄 비활성화. 갱신된 행 수 반환.

        인메모리에 없는 세션(서버 재시작, 브라우저 강제 종료 등)도 처리한다.
        """
        from app.database.engine import SessionLocal
        from app.database.orm_models import ChatSession as DBChatSession

        db = SessionLocal()
        try:
            cutoff = datetime.now() - timedelta(minutes=settings.session_expire_minutes)
            updated = (
                db.query(DBChatSession)
                .filter(
                    DBChatSession.is_active == True,
                    DBChatSession.last_accessed < cutoff,
                )
                .update({"is_active": False}, synchronize_session=False)
            )
            db.commit()
            return updated
        except Exception as e:
            logger.error(f"DB 만료 세션 일괄 비활성화 실패: {e}")
            db.rollback()
            return 0
        finally:
            db.close()

    def update_message_rating(self, message_id: int, rating: int, user_id: str) -> None:
        """assistant 메시지에 별점 저장."""
        from app.database.engine import SessionLocal
        from app.database.orm_models import ChatSession as DBChatSession, ChatMessage as DBChatMessage

        db = SessionLocal()
        try:
            db_msg = db.get(DBChatMessage, message_id)
            if not db_msg:
                raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다")

            db_session = db.get(DBChatSession, db_msg.session_id)
            if not db_session or db_session.user_id != user_id:
                raise HTTPException(status_code=403, detail="권한이 없습니다")

            if db_msg.role != "assistant":
                raise HTTPException(status_code=400, detail="AI 답변에만 별점을 줄 수 있습니다")

            db_msg.rating = rating
            db_msg.rated_at = datetime.now()
            db.commit()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"별점 저장 실패: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail="별점 저장에 실패했습니다")
        finally:
            db.close()

    def _db_deactivate_session(self, session_id: str) -> None:
        """DB 세션을 비활성화 (is_active=False)."""
        from app.database.engine import SessionLocal
        from app.database.orm_models import ChatSession as DBChatSession

        db = SessionLocal()
        try:
            db_session = db.get(DBChatSession, session_id)
            if db_session:
                db_session.is_active = False
                db.commit()
        except Exception as e:
            logger.error(f"DB 세션 비활성화 실패: {e}")
            db.rollback()
        finally:
            db.close()
