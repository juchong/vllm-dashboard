"""
Authentication models for vllm-dashboard

All users are considered administrators with the same permissions.
Authentication configuration is managed through the dashboard's "Settings" page.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from passlib.context import CryptContext

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"])


class User(Base):
    """
    User model for authentication
    All users are considered administrators with the same permissions
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(255))  # bcrypt hash
    role = Column(String(20), default='admin')  # All users are admins
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=None)
    is_active = Column(Boolean, default=True)
    login_failed_attempts = Column(Integer, default=0)
    last_failed_login = Column(DateTime, default=None)
    
    def __repr__(self):
        return f"<User(username={self.username}, role={self.role})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary (excluding sensitive fields)"""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }
    
    def check_password(self, password: str) -> bool:
        """Check if password matches the bcrypt hash."""
        if not self.password_hash:
            return False
        return pwd_context.verify(password, self.password_hash)


class Token(Base):
    """
    Token model for storing JWT tokens
    Used for token blacklist and token management
    """
    __tablename__ = 'tokens'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    token = Column(String(500))
    token_type = Column(String(20), default='access')
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    invalidated_at = Column(DateTime, default=None)
    
    def __repr__(self):
        return f"<Token(user_id={self.user_id}, id={self.id})>"
    
    def is_valid(self) -> bool:
        """Check if token is still valid"""
        if self.invalidated_at:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


class UserSession(Base):
    """
    User session model for tracking active sessions
    """
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    token = Column(String(500))
    user_agent = Column(String(255))
    ip_address = Column(String(45))  # IPv6 support
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=None)
    invalidated_at = Column(DateTime, default=None)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, ip={self.ip_address})>"
    
    def is_active(self) -> bool:
        """Check if session is still active"""
        if self.invalidated_at:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


class AuthConfig(Base):
    """
    Authentication configuration model
    Stores settings for authentication (enable/disable, rate limiting, etc.)
    """
    __tablename__ = 'auth_config'
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, index=True)
    value = Column(String(500))
    description = Column(String(255))
    is_encrypted = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AuthConfig(key={self.key})>"
    
    def get_value(self):
        """Get value (decrypt if needed)"""
        return self.value
    
    def set_value(self, value):
        """Set value (encrypt if needed)"""
        self.value = value


def get_auth_config(session, key: str) -> str:
    """Get authentication configuration value"""
    config = session.query(AuthConfig).filter_by(key=key).first()
    return config.get_value() if config else None


def set_auth_config(session, key: str, value: str, description: str = '', encrypted: bool = False):
    """Set authentication configuration value"""
    config = session.query(AuthConfig).filter_by(key=key).first()
    if config:
        config.set_value(value)
        config.description = description
        config.is_encrypted = encrypted
    else:
        config = AuthConfig(
            key=key,
            value=value,
            description=description,
            is_encrypted=encrypted
        )
    session.add(config)
    session.commit()