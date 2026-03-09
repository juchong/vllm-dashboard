"""
Authentication API endpoints for vllm-dashboard.

Trust and security behavior:
- When TRUST_PROXY_HEADERS=true, x-forwarded-proto is trusted for secure cookie flag
  (required behind nginx/reverse proxy with HTTPS termination).
- Session cookie is httpOnly, SameSite=lax; secure flag follows request scheme or proxy proto.
- Cookie max_age is driven by token_expires_hours from AuthConfig.
- CSRF: mutating routes require csrf_token cookie + X-CSRF-Token header match; login/refresh exempt.
"""

import logging
import os
from datetime import timedelta
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response

logger = logging.getLogger(__name__)
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from deps import get_auth_service, get_current_user, require_role
from models.auth_models import User
from rate_limit import enforce_login_limits
from security import audit_event
from services.auth_service import AuthService

router = APIRouter()

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
    role: Literal["viewer", "operator", "admin"] = "viewer"


class UserUpdateRequest(BaseModel):
    role: Literal["viewer", "operator", "admin"] | None = None
    is_active: bool | None = None


class AuthConfigUpdateRequest(BaseModel):
    enabled: bool | None = None
    max_failed_attempts: int | None = None
    lockout_minutes: int | None = None
    token_expires_hours: int | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _cookie_kwargs(request: Request) -> dict:
    """Cookie options for session/csrf. secure=True when HTTPS or when proxy reports HTTPS."""
    secure = request.url.scheme == "https"
    trust_proxy = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes"}
    if trust_proxy:
        proto = request.headers.get("x-forwarded-proto")
        if proto:
            proto = proto.split(",")[0].strip()
            secure = proto == "https"
    auth_service = request.state.auth_service
    cfg = auth_service.get_auth_config()
    max_age = int(cfg.get("token_expires_hours", 8)) * 3600
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
        "max_age": max_age,
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
    request.state.auth_service = auth_service
    if not form_data.username or not form_data.password:
        logger.warning("Login failed: empty username or password")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    enforce_login_limits(request, form_data.username)
    user = auth_service.authenticate(form_data.username, form_data.password)
    if not user:
        logger.warning("Login failed: invalid credentials for user=%s", form_data.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = auth_service.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(hours=auth_service.get_auth_config()["token_expires_hours"]),
    )
    cookie = _cookie_kwargs(request)
    response.set_cookie(key="session", value=token, **cookie)
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, samesite="lax", secure=cookie["secure"], path="/")
    # Token only in cookie (httpOnly). Return user for UI; never expose token to JS.
    return {
        "user": user.to_dict(),
        "token_type": "bearer",
        "expires_in": auth_service.get_auth_config()["token_expires_hours"] * 3600,
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
    response.delete_cookie(key="csrf_token", path="/")
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Refresh access token."""
    request.state.auth_service = auth_service
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

    auth_service.revoke_token(token)
    new_token = auth_service.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(hours=auth_service.get_auth_config()["token_expires_hours"]),
    )
    cookie = _cookie_kwargs(request)
    response.set_cookie(key="session", value=new_token, **cookie)
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, samesite="lax", secure=cookie["secure"], path="/")
    return {
        "user": user.to_dict(),
        "token_type": "bearer",
        "expires_in": auth_service.get_auth_config()["token_expires_hours"] * 3600,
    }


@router.get("/me")
async def get_me(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Get current user info. Sets csrf_token cookie for users with existing session."""
    request.state.auth_service = auth_service
    cookie = _cookie_kwargs(request)
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, samesite="lax", secure=cookie["secure"], path="/")
    return current_user.to_dict()


@router.post("/password")
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Change the current user's password."""
    request.state.current_user = current_user
    auth_service.change_password(current_user, password_data.current_password, password_data.new_password)
    audit_event(request, "change_password", current_user.username, "success")
    return {"message": "Password changed successfully"}


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(require_role("admin")),
    auth_service: AuthService = Depends(get_auth_service),
):
    """List all users."""
    users = auth_service.list_users()
    return users


@router.post("/users", response_model=UserResponse)
async def create_user(
    request: Request,
    user_data: UserCreateRequest,
    current_user: User = Depends(require_role("admin")),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Create a new user."""
    request.state.current_user = current_user
    user = auth_service.create_user(user_data.username, user_data.password, role=user_data.role)
    audit_event(request, "create_user", user.username, "success", {"role": user.role})
    return user.to_dict()


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: int,
    user_data: UserUpdateRequest,
    current_user: User = Depends(require_role("admin")),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Update a user."""
    request.state.current_user = current_user
    user = auth_service.update_user(
        user_id,
        role=user_data.role,
        is_active=user_data.is_active,
    )
    audit_event(request, "update_user", str(user_id), "success", {"role": user.role, "is_active": user.is_active})
    return user.to_dict()


@router.delete("/users/{user_id}")
async def delete_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Delete a user."""
    request.state.current_user = current_user
    user = auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    auth_service.delete_user(user.username)
    audit_event(request, "delete_user", str(user_id), "success")
    return {"message": "User deleted successfully"}


@router.get("/config")
async def get_auth_config(
    current_user: User = Depends(require_role("admin")),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Get authentication configuration."""
    return auth_service.get_auth_config()


@router.put("/config")
async def update_auth_config(
    request: Request,
    config_data: AuthConfigUpdateRequest,
    current_user: User = Depends(require_role("admin")),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Update authentication configuration."""
    request.state.current_user = current_user
    data = config_data.model_dump(exclude_none=True)
    auth_service.update_auth_config(data)
    audit_event(request, "update_auth_config", "auth_config", "success", {"keys": sorted(list(data.keys()))})
    return {"message": "Authentication configuration updated successfully"}
