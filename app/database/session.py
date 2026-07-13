"""Database engine and session management.

Uses SQLAlchemy against `settings.database_url` (SQLite by default, but any
SQLAlchemy-supported URL works, e.g. Postgres in production).
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def _make_engine():
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        # Needed for SQLite when accessed from multiple threads (FastAPI's
        # default threadpool executor for sync endpoints).
        connect_args = {"check_same_thread": False}

    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        future=True,
    )


engine = _make_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def init_db() -> None:
    """Create all tables that don't exist yet.

    Import all model modules first so they register themselves on
    `Base.metadata` before `create_all` runs.
    """
    from app import models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator:
    """FastAPI-style dependency that yields a session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session():
    """Return a new session directly (for non-request contexts, e.g. stores)."""
    return SessionLocal()
