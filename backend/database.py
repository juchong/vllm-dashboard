"""
Database configuration for vllm-dashboard authentication.

Uses SQLite with NullPool for safe multi-threaded access. Database file
is stored in VLLM_CONFIG_DIR for persistence across container restarts.

Engine and session factory are created lazily so that tests can override
VLLM_CONFIG_DIR before any database access occurs.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator

from models.auth_models import Base

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        config_dir = os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")
        db_path = os.path.join(config_dir, "auth.db")
        _engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
            echo=False,
        )
    return _engine


def _get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


def SessionLocal():
    """Return a new database session."""
    factory = _get_session_local()
    return factory()


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=_get_engine())


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: provide a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
