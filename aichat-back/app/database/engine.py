"""SQLAlchemy 엔진 및 세션 팩토리.

기존 psycopg2 pool.py를 대체합니다.
- 용어 사전 / 로그인 쿼리: engine.connect()로 직접 실행 (Core 방식)
- 대화 세션 / 메시지 저장: SessionLocal (ORM 방식)
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings

settings = get_settings()

DATABASE_URL = (
    f"postgresql+psycopg2://{settings.pg_user}:{settings.pg_password}"
    f"@{settings.pg_host}:{settings.pg_port}/{settings.pg_database}"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=10,
    pool_pre_ping=True,   # 커넥션 사용 전 유효성 확인 (서버 재시작 대응)
    pool_recycle=3600,    # 1시간마다 커넥션 재생성
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# ORM 모델의 Base — orm_models.py에서 상속
Base = declarative_base()


def get_db():
    """FastAPI Depends()용 DB 세션 제공자."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
