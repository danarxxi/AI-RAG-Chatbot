from fastapi import APIRouter, HTTPException, status
from app.models.session import LoginRequest, LoginResponse
from app.services.auth_service import AuthService
from app.services.session_service import SessionService
from app.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)
auth_service = AuthService()
session_service = SessionService()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and create session.
    """
    logger.info(f"Login attempt for user: {request.username}")

    # Verify credentials
    user_name = auth_service.verify_credentials(request.username, request.password)
    if user_name is None:
        logger.warning(f"Failed login attempt for user: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate session ID
    session_id = auth_service.generate_session_id()

    # Create session
    session_service.create_session(session_id=session_id, user_id=request.username)

    # Create access token
    access_token = auth_service.create_access_token(
        data={"sub": request.username, "session_id": session_id}
    )

    logger.info(f"Successful login for user: {request.username}, session: {session_id}")

    return LoginResponse(
        access_token=access_token,
        session_id=session_id,
        user_id=request.username,
        user_name=user_name
    )


@router.post("/logout")
async def logout(session_id: str):
    """Logout user and clear session."""
    session_service.delete_session(session_id)
    logger.info(f"User logged out, session: {session_id}")
    return {"message": "Logged out successfully"}
