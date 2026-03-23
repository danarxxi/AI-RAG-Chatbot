from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.auth_service import AuthService, get_current_user
from app.services.session_service import SessionService
from app.models.session import TokenData, ServiceType
from app.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)
auth_service = AuthService()
session_service = SessionService()


class ClearHistoryRequest(BaseModel):
    """Request model for clearing conversation history."""
    service_type: ServiceType


class ClearHistoryResponse(BaseModel):
    """Response model for clearing conversation history."""
    session_id: str
    message: str = "Conversation history cleared"


@router.post("/new", response_model=ClearHistoryResponse)
async def clear_service_history(
    request: ClearHistoryRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Clear conversation history for a specific service in current session.
    Used when user clicks 'New Chat' - keeps session, clears only the specified service's conversation.
    """
    try:
        # Get current session from token
        session_id = current_user.session_id
        session = session_service.get_session(session_id)

        # Verify session belongs to current user
        if session.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to user")

        # Clear conversation history for specified service only
        session_service.clear_conversation_history(session_id, request.service_type)

        logger.info(f"Cleared {request.service_type} history for session {session_id}")

        return ClearHistoryResponse(session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing conversation history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
