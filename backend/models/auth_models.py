"""Authentication models for vllm-dashboard.

Token lifecycle:
- JWTs include jti; Token table stores jti for revocation.
- Logout and refresh invalidate the old token (invalidated_at set).
- verify_token rejects tokens whose jti is revoked or invalidated.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(255))
    role = Column(String(20), default='viewer')
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
    

class Token(Base):
    """Token revocation record. token column stores JWT jti; invalidated_at set on logout/refresh."""
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


class AuthConfig(Base):
    """Authentication configuration storage."""
    __tablename__ = 'auth_config'
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, index=True)
    value = Column(String(500))
    description = Column(String(255))
    is_encrypted = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AuthConfig(key={self.key})>"
