"""SQLite database setup with SQLAlchemy"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.app.config import get_settings

settings = get_settings()
os.makedirs(os.path.dirname(settings.database_url.replace("sqlite:///", "")), exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,
)

# Enable WAL mode for better concurrent read performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if os.environ.get("RISK_AGENT_TESTING") == "true":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Initialize database — create all tables + apply migrations"""
    if os.environ.get("RISK_AGENT_TESTING") == "true":
        return  # skip in test mode — tests manage their own DB
    import backend.models  # noqa: ensure models are registered
    Base.metadata.create_all(bind=engine)

    # --- Schema migrations (additive only) ---
    with engine.connect() as conn:
        # Migration: add linked_task_id column if missing
        try:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN linked_task_id INTEGER REFERENCES tasks(id)"
            )
            conn.commit()
        except Exception:
            pass  # column already exists

        # Migration: add scheduled_at column if missing
        try:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN scheduled_at DATETIME"
            )
            conn.commit()
        except Exception:
            pass  # column already exists


def get_db():
    """FastAPI dependency: provide a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
