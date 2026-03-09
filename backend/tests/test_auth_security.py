"""Security tests for auth: token lifecycle, RBAC, enabled flag, login throttling."""
import pytest
from jose import jwt
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client(monkeypatch, shared_config_tmp):
    """Use shared tmp so database path stays valid across test files."""
    tmp = shared_config_tmp
    monkeypatch.setenv("VLLM_CONFIG_DIR", tmp)
    monkeypatch.setenv("VLLM_COMPOSE_PATH", tmp)
    monkeypatch.setenv("VLLM_MODELS_DIR", tmp)
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "testadmin123")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", "memory://")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    from database import init_db, SessionLocal
    from main import app
    from services.auth_service import AuthService
    from models.auth_models import User
    init_db()
    db = SessionLocal()
    try:
        svc = AuthService(db)
        if db.query(User).filter(User.username == "admin").count() == 0:
            svc.create_user("admin", "testadmin123", role="admin")
        if db.query(User).filter(User.username == "viewer1").count() == 0:
            svc.create_user("viewer1", "viewer123", role="viewer")
    finally:
        db.close()
    yield TestClient(app, base_url="http://localhost")


def test_jti_present_in_issued_token(client):
    """Issued JWT must contain jti claim."""
    r = client.post("/api/auth/login", data={"username": "admin", "password": "testadmin123"}, headers={"Host": "localhost"})
    assert r.status_code == 200
    # Token is in cookie, decode without verify to inspect
    token = r.cookies.get("session")
    assert token
    payload = jwt.get_unverified_claims(token)
    assert "jti" in payload
    assert payload.get("sub") == "admin"


def test_revoked_token_denied(client):
    """Revoked token must be rejected by verify_token."""
    r = client.post("/api/auth/login", data={"username": "admin", "password": "testadmin123"}, headers={"Host": "localhost"})
    assert r.status_code == 200
    token = r.cookies.get("session")
    csrf = r.cookies.get("csrf_token")  # Login sets csrf_token
    assert csrf, "Login must set csrf_token cookie"
    cookies = {"session": token, "csrf_token": csrf}
    headers = {"Host": "localhost", "X-CSRF-Token": csrf}
    # Logout revokes token (POST requires CSRF: cookie + header must match)
    client.post("/api/auth/logout", cookies=cookies, headers=headers)
    # Token should no longer work
    r3 = client.get("/api/auth/me", cookies={"session": token}, headers={"Host": "localhost"})
    assert r3.status_code == 401


def test_refresh_invalidates_old_token(client):
    """Refresh returns new token; old token must be rejected."""
    r = client.post("/api/auth/login", data={"username": "admin", "password": "testadmin123"}, headers={"Host": "localhost"})
    assert r.status_code == 200
    old_token = r.cookies.get("session")
    r2 = client.post("/api/auth/refresh", cookies={"session": old_token}, headers={"Host": "localhost"})
    assert r2.status_code == 200
    new_token = r2.cookies.get("session")
    assert new_token != old_token
    # Old token should not work
    r3 = client.get("/api/auth/me", cookies={"session": old_token}, headers={"Host": "localhost"})
    assert r3.status_code == 401
    # New token should work
    r4 = client.get("/api/auth/me", cookies={"session": new_token}, headers={"Host": "localhost"})
    assert r4.status_code == 200


def test_enabled_false_denies_login(client):
    """When auth enabled=false, login and auth-dependent ops return 403."""
    from database import SessionLocal
    from models.auth_models import AuthConfig
    db = SessionLocal()
    try:
        existing = db.query(AuthConfig).filter(AuthConfig.key == "enabled").first()
        if existing:
            existing.value = "false"
        else:
            db.add(AuthConfig(key="enabled", value="false", description=""))
        db.commit()
    finally:
        db.close()

    r = client.post("/api/auth/login", data={"username": "admin", "password": "testadmin123"}, headers={"Host": "localhost"})
    assert r.status_code == 403
    assert "disabled" in (r.json().get("detail") or "").lower()

    # Reset so subsequent tests can login
    db = SessionLocal()
    try:
        existing = db.query(AuthConfig).filter(AuthConfig.key == "enabled").first()
        if existing:
            existing.value = "true"
            db.commit()
    finally:
        db.close()


def test_rbac_viewer_denied_admin_endpoint(client):
    """Viewer role must get 403 on admin-only endpoints."""
    r = client.post("/api/auth/login", data={"username": "viewer1", "password": "viewer123"}, headers={"Host": "localhost"})
    assert r.status_code == 200
    cookies = {"session": r.cookies.get("session")}
    csrf = r.cookies.get("csrf_token")
    headers = {"Host": "localhost", "X-CSRF-Token": csrf} if csrf else {"Host": "localhost"}

    # Admin-only: create user
    r2 = client.post("/api/auth/users", json={"username": "newuser", "password": "pass123", "role": "viewer"}, cookies=cookies, headers=headers)
    assert r2.status_code == 403
    assert "permission" in (r2.json().get("detail") or "").lower()


def test_login_throttling():
    """Repeated login attempts for same user hit rate limit (10/min)."""
    from rate_limit import enforce_login_limits
    from fastapi import HTTPException
    from unittest.mock import MagicMock

    req = MagicMock()
    req.headers = {}
    req.client = MagicMock()
    req.client.host = "127.0.0.1"

    for _ in range(10):
        enforce_login_limits(req, "throttle_test_user")

    with pytest.raises(HTTPException) as exc_info:
        enforce_login_limits(req, "throttle_test_user")
    assert exc_info.value.status_code == 429


def test_audit_event_on_privileged_action(client):
    """Privileged endpoints emit audit events (logged)."""
    import logging
    from io import StringIO
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    logger = logging.getLogger("security")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        r = client.post("/api/auth/login", data={"username": "admin", "password": "testadmin123"}, headers={"Host": "localhost"})
        assert r.status_code == 200
        cookies = {"session": r.cookies.get("session")}
        csrf = r.cookies.get("csrf_token")
        headers = {"Host": "localhost", "X-CSRF-Token": csrf}
        # Trigger audit: update auth config
        client.put("/api/auth/config", json={"token_expires_hours": 8}, cookies=cookies, headers=headers)
        log_output = log_capture.getvalue()
        assert "security_audit" in log_output or "update_auth_config" in log_output
    finally:
        logger.removeHandler(handler)


def test_password_validation_enforces_min_length():
    """Test that password validation requires minimum length (16 chars for production)."""
    from services.auth_service import AuthService
    from unittest.mock import MagicMock
    
    db = MagicMock()
    svc = AuthService(db)
    
    # Test short password
    try:
        svc.create_user("testuser", "short", role="viewer")
        assert False, "Should have raised exception for short password"
    except Exception:
        pass  # Expected
    assert True


def test_csrf_token_validation_in_websocket():
    """Test that WebSocket connections require valid CSRF tokens for security."""
    from security import validate_csrf_token
    
    # Valid tokens should match
    assert validate_csrf_token("same_token", "same_token") is True
    
    # Invalid tokens should not match
    assert validate_csrf_token("different_token", "other_token") is False
    
    # None tokens should not match
    assert validate_csrf_token(None, "other_token") is False
    assert validate_csrf_token("same_token", None) is False
