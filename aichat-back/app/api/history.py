from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from app.services.auth_service import get_current_user
from app.models.session import TokenData
from app.services.session_service import SessionService
from app.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)
session_service = SessionService()


@router.get("/sessions")
async def get_user_sessions(
    service_type: str,
    current_user: TokenData = Depends(get_current_user),
):
    """
    현재 로그인 사용자의 10일 이내 과거 세션 목록 반환.
    service_type: 'hr' | 'glossary' | 'work_guide'
    """
    sessions = session_service.get_user_sessions(current_user.user_id, service_type)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    service_type: str,
    current_user: TokenData = Depends(get_current_user),
):
    """
    특정 세션의 메시지 전체 반환.
    - 10일 이내 세션만 허용
    - 자신의 세션만 조회 가능
    """
    from app.database.engine import SessionLocal
    from app.database.orm_models import ChatSession as DBChatSession

    db = SessionLocal()
    try:
        db_session = db.get(DBChatSession, session_id)
        if not db_session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        if db_session.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

        cutoff = datetime.now() - timedelta(days=10)
        if db_session.created_at < cutoff:
            raise HTTPException(status_code=404, detail="10일이 지난 대화는 조회할 수 없습니다.")
    finally:
        db.close()

    messages = session_service.get_session_messages_from_db(session_id, service_type)
    return {
        "session_id": session_id,
        "service_type": service_type,
        "messages": messages,
    }
