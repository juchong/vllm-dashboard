"""FastAPI dependencies for authentication and authorization."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models.auth_models import User
from services.auth_service import AuthService


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Provide AuthService with database session."""
    return AuthService(db)


def get_current_user(request: Request) -> User:
    """Require authenticated user. Raises 401 if not authenticated.
    Uses a session created in the current thread to avoid SQLAlchemy
    cross-thread issues when FastAPI runs sync deps in a threadpool.
    """
    db = SessionLocal()
    try:
        auth_service = AuthService(db)
        return auth_service.get_current_user(request)
    finally:
        db.close()


def require_role(min_role: str):
    """Dependency factory enforcing a minimum role."""

    def _dep(
        current_user: User = Depends(get_current_user),
        auth_service: AuthService = Depends(get_auth_service),
    ) -> User:
        if not auth_service.has_role(current_user, min_role):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return _dep
