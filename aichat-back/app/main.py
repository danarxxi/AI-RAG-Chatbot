from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.utils.logger import setup_logger
import asyncio
import time
from contextlib import asynccontextmanager
from app.services.session_service import SessionService

settings = get_settings()
logger = setup_logger(__name__)


async def cleanup_sessions_task():
    """Background task to periodically clean expired sessions."""
    session_service = SessionService()
    while True:
        await asyncio.sleep(300)  # Sleep for 5 minutes (300 seconds)
        try:
            session_service.clear_expired_sessions()
            logger.info("Session cleanup completed")
        except Exception as e:
            logger.error(f"Error in session cleanup task: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: DB 테이블 초기화
    from app.database.orm_models import Base
    from app.database.engine import engine
    Base.metadata.create_all(bind=engine)
    logger.info("DB 테이블 초기화 완료 (tb_chat_session, tb_chat_message)")

    # Startup: Start background task
    cleanup_task = asyncio.create_task(cleanup_sessions_task())
    logger.info("Session cleanup background task started")

    yield  # Server runs here

    # Shutdown: Cancel background task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Session cleanup background task stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="RAG-based HR Chatbot API",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s - {request.client.host}")
    return response


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0"
    }


# Import and include routers
from app.api import auth, chat, session, glossary, work_guide, history
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(session.router, prefix="/api/session", tags=["Session"])
app.include_router(glossary.router, prefix="/api/glossary", tags=["Glossary"])
app.include_router(work_guide.router, prefix="/api/work-guide", tags=["WorkGuide"])
app.include_router(history.router, prefix="/api/history", tags=["History"])
