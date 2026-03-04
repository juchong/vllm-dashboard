"""
FastAPI dependencies for authentication.
"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from models.auth_models import User
from services.auth_service import AuthService


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Provide AuthService with database session."""
    return AuthService(db)


def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Require authenticated user. Raises 401 if not authenticated."""
    return auth_service.get_current_user(request)
