"""
Database configuration for vllm-dashboard authentication.

Uses SQLite with NullPool for safe multi-threaded access. Database file
is stored in VLLM_CONFIG_DIR for persistence across container restarts.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator

from models.auth_models import Base

# Database path: persist in config dir (mounted volume)
CONFIG_DIR = os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")
DATABASE_PATH = os.path.join(CONFIG_DIR, "auth.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: provide a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
