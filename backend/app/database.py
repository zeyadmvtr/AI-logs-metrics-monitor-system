from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import get_settings
from app.logger import logger

settings = get_settings()

db_url = settings.DATABASE_URL
is_sqlite = "sqlite" in db_url

# تحديد الـ Engine بناءً على نوع الداتابيز (تجنباً لمشاكل الـ Pooling مع SQLite)
if is_sqlite:
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        db_url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> tuple[bool, str]:
    """Verifies that the database is reachable and accepting queries."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Database connection OK"
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}", extra={"error_type": "db_conn_error"})
        return False, str(exc)