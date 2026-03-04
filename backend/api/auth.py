"""
Authentication API endpoints for vllm-dashboard.
"""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response

logger = logging.getLogger(__name__)
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from deps import get_auth_service, get_current_user
from models.auth_models import User
from services.auth_service import AuthService

router = APIRouter()

ACCESS_TOKEN_EXPIRE_HOURS = 8


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str | None
    last_login: str | None
    is_active: bool


class LoginResponse(BaseModel):
    """Login response. Token is set in httpOnly cookie only - never exposed to JS."""
    user: UserResponse
    token_type: str = "bearer"
    expires_in: int


class UserCreateRequest(BaseModel):
    username: str
    password: str


class UserUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class AuthConfigUpdateRequest(BaseModel):
    enabled: bool | None = None
    max_failed_attempts: int | None = None
    lockout_minutes: int | None = None
    token_expires_hours: int | None = None


def _cookie_kwargs(request: Request) -> dict:
    # Trust X-Forwarded-Proto only from trusted proxies (same host). Spoofing requires
    # direct backend access; nginx strips unknown headers from external clients.
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    secure = proto == "https"
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
        "max_age": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        "path": "/",
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Authenticate user and return JWT."""
    if not form_data.username or not form_data.password:
        logger.warning("Login failed: empty username or password")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    user = auth_service.authenticate(form_data.username, form_data.password)
    if not user:
        logger.warning("Login failed: invalid credentials for user=%s", form_data.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = auth_service.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    )
    response.set_cookie(key="session", value=token, **_cookie_kwargs(request))
    # Token only in cookie (httpOnly). Return user for UI; never expose token to JS.
    return {
        "user": user.to_dict(),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Clear session cookie and invalidate token."""
    auth_service.logout(request)
    response.delete_cookie(key="session", path="/")
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Refresh access token."""
    token = request.cookies.get("session")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = auth_service.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    new_token = auth_service.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    )
    response.set_cookie(key="session", value=new_token, **_cookie_kwargs(request))
    return {
        "user": user.to_dict(),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
    }


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current user info."""
    return current_user.to_dict()


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """List all users."""
    users = auth_service.list_users()
    return users


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Create a new user."""
    user = auth_service.create_user(user_data.username, user_data.password)
    return user.to_dict()


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Update a user."""
    user = auth_service.update_user(
        user_id,
        role=user_data.role,
        is_active=user_data.is_active,
    )
    return user.to_dict()


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Delete a user."""
    user = auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    auth_service.delete_user(user.username)
    return {"message": "User deleted successfully"}


@router.get("/config")
async def get_auth_config(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Get authentication configuration."""
    return auth_service.get_auth_config()


@router.put("/config")
async def update_auth_config(
    config_data: AuthConfigUpdateRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Update authentication configuration."""
    data = config_data.model_dump(exclude_none=True)
    auth_service.update_auth_config(data)
    return {"message": "Authentication configuration updated successfully"}
