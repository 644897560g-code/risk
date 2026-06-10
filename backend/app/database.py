"""PostgreSQL database setup with SQLAlchemy."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Load models only; schema changes are managed by Alembic."""
    if os.environ.get("RISK_AGENT_TESTING") == "true":
        return
    import backend.models  # noqa: F401 ensure models are registered


def get_db():
    """FastAPI dependency: provide a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
