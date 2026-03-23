from fastapi import APIRouter, Depends, HTTPException
from app.models.glossary import GlossaryQueryRequest, GlossaryQueryResponse
from app.models.chat import FeedbackRequest
from app.models.session import TokenData, ServiceType
from app.services.auth_service import get_current_user
from app.services.session_service import SessionService
from app.services.glossary_service import glossary_service
from app.utils.logger import setup_logger, log_api_call

router = APIRouter()
logger = setup_logger(__name__, service_type="GLOSSARY")
session_service = SessionService()


@router.post("/query", response_model=GlossaryQueryResponse)
async def query_glossary(
    request: GlossaryQueryRequest,
    current_user: TokenData = Depends(get_current_user) # 보안 인증
):
    """
    Query the internal glossary using natural language with conversation history support.

    - Classifies query type (greeting, summary, glossary lookup, etc.)
    - Extracts terms from the query using LLM
    - Searches the glossary database
    - Generates a contextually aware natural language response
    """
    try:
        # Validate session
        session = session_service.get_session(request.session_id)

        # Verify session belongs to current user
        if session.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to user")

        logger.info(f"Glossary query from user {current_user.user_id}: {request.query[:50]}...")

        # Add user message to conversation history (Glossary service)
        session_service.add_message(
            session_id=request.session_id,
            role="user",
            content=request.query,
            service_type=ServiceType.GLOSSARY
        )

        # Get conversation history for Glossary service only
        conversation_history = session_service.get_conversation_history(
            request.session_id,
            ServiceType.GLOSSARY
        )

        # Process glossary query with conversation history (async processing)
        response = await glossary_service.query_glossary_async(request, conversation_history)

        # Add assistant response to conversation history (Glossary service)
        assistant_message_id = session_service.add_message(
            session_id=request.session_id,
            role="assistant",
            content=response.answer,
            service_type=ServiceType.GLOSSARY
        )

        # Log the interaction
        log_api_call(
            logger=logger,
            user_id=current_user.user_id,
            session_id=request.session_id,
            endpoint="POST /api/glossary/query",
            request_data=request.query,
            response_data=f"Found {len(response.source_terms)} terms | {response.answer}",
            status_code=200
        )

        return GlossaryQueryResponse(
            answer=response.answer,
            source_terms=response.source_terms,
            session_id=response.session_id,
            timestamp=response.timestamp,
            message_id=assistant_message_id,
            executed_query=response.executed_query
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing glossary query: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/{session_id}")
async def get_glossary_history(
    session_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get conversation history for Glossary service (DB 기반, 서버 재시작 후에도 유지됨).
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

        messages = session_service.get_session_messages_from_db(session_id, "glossary")
        return {"session_id": session_id, "messages": messages}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving glossary history: {e}")
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
