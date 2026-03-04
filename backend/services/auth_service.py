"""
Authentication service for vllm-dashboard

Handles user authentication, password hashing, and session management.
All users are considered administrators with the same permissions.
"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from models.auth_models import AuthConfig, Token, User, UserSession

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"])

# JWT configuration
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = os.urandom(32).hex()
    logger.warning("SECRET_KEY not set; using random key. Set SECRET_KEY for production.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72  # bcrypt limit
ALLOWED_ROLES = frozenset({"admin"})
AUTH_CONFIG_BOUNDS = {
    "max_failed_attempts": (1, 20),
    "lockout_minutes": (1, 1440),
    "token_expires_hours": (1, 168),
}


def _validate_username(username: str) -> None:
    if not username or not USERNAME_PATTERN.match(username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-32 characters, alphanumeric, underscore, or hyphen only",
        )


def _validate_password(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at most {MAX_PASSWORD_LENGTH} bytes",
        )


class AuthService:
    """Authentication service for vllm-dashboard."""

    def __init__(self, db: Session):
        self.db = db

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(
        self, data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> Optional[User]:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
            return self.get_user(username)
        except JWTError:
            return None

    def get_user(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def authenticate(self, username: str, password: str) -> Optional[User]:
        config = self.get_auth_config()
        user = self.get_user(username)
        if user and user.login_failed_attempts >= config.get("max_failed_attempts", 5):
            lockout_min = config.get("lockout_minutes", 15)
            if user.last_failed_login:
                if datetime.utcnow() - user.last_failed_login < timedelta(minutes=lockout_min):
                    logger.warning("Account locked: user=%s", username)
                    return None
                user.login_failed_attempts = 0
        if user and self.verify_password(password, user.password_hash):
            if not user.is_active:
                raise HTTPException(status_code=403, detail="Account is deactivated")
            user.last_login = datetime.utcnow()
            user.login_failed_attempts = 0
            self.db.commit()
            self.db.refresh(user)
            return user
        if user:
            user.login_failed_attempts += 1
            user.last_failed_login = datetime.utcnow()
            self.db.commit()
        return None

    def get_current_user(self, request: Request) -> User:
        token = request.cookies.get("session")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        user = self.verify_token(token)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is disabled")
        return user

    def logout(self, request: Request) -> bool:
        token = request.cookies.get("session")
        if not token:
            return True
        try:
            auth_token = self.db.query(Token).filter(Token.token == token).first()
            if auth_token:
                auth_token.invalidated_at = datetime.utcnow()
                self.db.commit()
            return True
        except Exception as e:
            logger.exception("Logout failed: %s", e)
            self.db.rollback()
            raise HTTPException(status_code=500, detail="An error occurred")

    def create_user(self, username: str, password: str) -> User:
        _validate_username(username)
        _validate_password(password)
        existing = self.get_user(username)
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        hashed = self.hash_password(password)
        user = User(username=username, password_hash=hashed, role="admin")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, username: str) -> bool:
        user = self.get_user(username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        self.db.delete(user)
        self.db.commit()
        return True

    def update_user(self, user_id: int, role: Optional[str] = None, is_active: Optional[bool] = None) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if role is not None and role not in ALLOWED_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        self.db.commit()
        self.db.refresh(user)
        return user

    def list_users(self) -> list:
        users = self.db.query(User).all()
        return [u.to_dict() for u in users]

    def get_auth_config(self) -> dict:
        """Get auth configuration from database."""
        configs = self.db.query(AuthConfig).all()
        result = {
            "enabled": True,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
            "token_expires_hours": 8,
        }
        for c in configs:
            if c.key in result:
                try:
                    if c.key == "enabled":
                        result[c.key] = c.value.lower() in ("true", "1", "yes")
                    elif c.key in ("max_failed_attempts", "lockout_minutes", "token_expires_hours"):
                        result[c.key] = int(c.value)
                    else:
                        result[c.key] = c.value
                except (ValueError, TypeError):
                    pass
        return result

    def update_auth_config(self, config: dict) -> None:
        """Update auth configuration in database."""
        for key, value in config.items():
            if key in ("enabled", "max_failed_attempts", "lockout_minutes", "token_expires_hours"):
                if key in AUTH_CONFIG_BOUNDS:
                    lo, hi = AUTH_CONFIG_BOUNDS[key]
                    try:
                        ival = int(value)
                        if ival < lo or ival > hi:
                            raise HTTPException(
                                status_code=400,
                                detail=f"{key} must be between {lo} and {hi}",
                            )
                    except (ValueError, TypeError):
                        raise HTTPException(status_code=400, detail=f"Invalid value for {key}")
                existing = self.db.query(AuthConfig).filter(AuthConfig.key == key).first()
                str_val = str(value).lower() if isinstance(value, bool) else str(value)
                if existing:
                    existing.value = str_val
                else:
                    self.db.add(AuthConfig(key=key, value=str_val, description=""))
        self.db.commit()
