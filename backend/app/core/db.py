"""Database engine with SQLite pragmas and a request-scoped session."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.base import Base

# Import every model module so metadata contains all tables before create_all.
from app.models import entities  # noqa: F401


def _sqlite_connect_args(url: str) -> dict[str, bool]:
    """FastAPI uses threads; SQLite needs check_same_thread disabled for that."""
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


settings = get_settings()
database_url = settings.sqlalchemy_database_url()
engine_options = {"connect_args": _sqlite_connect_args(database_url), "future": True}
if database_url.startswith("sqlite"):
    engine_options["poolclass"] = NullPool
engine = create_engine(database_url, **engine_options)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
    """Turn on foreign keys and WAL for every new SQLite connection."""
    if not database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    """Yield a session and always close it, even when a handler raises."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables, FTS index, and the uploads folder on first boot."""
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        _ensure_fts()
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)


def _ensure_fts() -> None:
    """
    SQLite FTS5 lets name/brand/SKU search stay fast.

    If FTS5 is missing on a stripped build, product search falls back to LIKE.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
                    name,
                    brand,
                    sku,
                    content='products',
                    content_rowid='id'
                )
                """
            )
        )
