from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import get_settings
from app.models.session import TokenData
from app.utils.logger import setup_logger
import uuid

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
logger = setup_logger(__name__)


class AuthService:
    """Authentication service for JWT token management."""

    @staticmethod
    def verify_credentials(username: str, password: str) -> Optional[str]:
        """Verify credentials from environment variables.
        Returns username if credentials are valid, None otherwise."""
        if username == settings.admin_user_id and password == settings.admin_password:
            return username
        return None

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now() + expires_delta
        else:
            expire = datetime.now() + timedelta(minutes=settings.access_token_expire_minutes)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> TokenData:
        """Verify and decode JWT token."""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            user_id: Optional[str] = payload.get("sub")
            session_id: Optional[str] = payload.get("session_id")

            if user_id is None:
                raise credentials_exception

            return TokenData(user_id=user_id, session_id=session_id)
        except JWTError:
            raise credentials_exception

    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID."""
        return str(uuid.uuid4())


# 헤더에서 JWT 추출, 서명 검증, user_id 디코딩, TokenData 반환
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """Dependency to get current authenticated user."""
    token = credentials.credentials
    token_data = AuthService.verify_token(token)
    return token_data
