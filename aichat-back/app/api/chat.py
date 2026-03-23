from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from app.models.chat import ChatRequest, ChatResponse, FeedbackRequest
from app.models.session import TokenData, ServiceType
from app.services.auth_service import get_current_user
from app.services.session_service import SessionService
from app.services.rag_service import RAGService
from app.utils.logger import setup_logger, log_api_call

router = APIRouter()
logger = setup_logger(__name__, service_type="HR")
session_service = SessionService()
rag_service = RAGService()


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: TokenData = Depends(get_current_user) # 의존성 주입 부분: chat() 함수를 실행하기 전에 get_current_user를 자동으로 먼저 호출하여 인증을 자동으로 처리. 해당 엔드포인트 보호하는 부분.
):
    """
    Process chat message and return RAG-based response.
    """
    try:
        # Validate session
        session = session_service.get_session(request.session_id)

        # Verify session belongs to current user
        if session.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to user")

        logger.info(f"Chat request from user {current_user.user_id}, session {request.session_id}")

        # Add user message to conversation history (HR service)
        session_service.add_message(
            session_id=request.session_id,
            role="user",
            content=request.message,
            service_type=ServiceType.HR
        )

        # Get conversation history for HR service only
        conversation_history = session_service.get_conversation_history(
            request.session_id,
            ServiceType.HR
        )

        # Get RAG response (returns dict with 'response' and 'sources')
        # Using async version to avoid blocking the event loop
        rag_result = await rag_service.get_rag_response_async(
            query=request.message,
            conversation_history=conversation_history
        )

        ai_response = rag_result['response']
        sources = rag_result['sources']

        # Add assistant response to conversation history (HR service)
        assistant_message_id = session_service.add_message(
            session_id=request.session_id,
            role="assistant",
            content=ai_response,
            service_type=ServiceType.HR
        )

        # Log the interaction
        log_api_call(
            logger=logger,
            user_id=current_user.user_id,
            session_id=request.session_id,
            endpoint="POST /api/chat",
            request_data=request.message,
            response_data=ai_response,
            status_code=200
        )

        return ChatResponse(
            response=ai_response,
            session_id=request.session_id,
            timestamp=datetime.now(),
            sources=sources,
            message_id=assistant_message_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get conversation history for HR chat service (DB 기반, 서버 재시작 후에도 유지됨).
    """
    try:
        from app.database.engine import SessionLocal
        from app.database.orm_models import ChatSession as DBChatSession

        db = SessionLocal()
        try:
            db_session = db.get(DBChatSession, session_id)
            if db_session is None:
                raise HTTPException(status_code=403, detail="Session does not belong to user")
            if str(db_session.user_id) != current_user.user_id:
                raise HTTPException(status_code=403, detail="Session does not belong to user")
        finally:
            db.close()

        messages = session_service.get_session_messages_from_db(session_id, "hr")
        return {"session_id": session_id, "messages": messages}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/messages/{message_id}/feedback")
async def submit_feedback(
    message_id: int,
    request: FeedbackRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """AI 답변에 별점 저장."""
    try:
        if not current_user.user_id:
            raise HTTPException(status_code=401, detail="인증 정보가 없습니다")
        session_service.update_message_rating(
            message_id=message_id,
            rating=request.rating,
            user_id=current_user.user_id
        )
        return {"message_id": message_id, "rating": request.rating}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"별점 저장 오류: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
