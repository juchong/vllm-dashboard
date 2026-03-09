"""Phase 2 API tests: CSRF on /me, heavy API rate limits."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, shared_config_tmp):
    """Use shared tmp so database path stays valid across test files."""
    tmp = shared_config_tmp
    monkeypatch.setenv("VLLM_CONFIG_DIR", tmp)
    monkeypatch.setenv("VLLM_COMPOSE_PATH", tmp)
    monkeypatch.setenv("VLLM_MODELS_DIR", tmp)
    pwd = "testadmin123"
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", pwd)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDACT_CONTAINER_LOGS", "true")
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", "memory://")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    from database import init_db, SessionLocal
    from main import app
    from services.auth_service import AuthService
    init_db()
    db = SessionLocal()
    try:
        from models.auth_models import User
        if db.query(User).count() == 0:
            svc = AuthService(db)
            svc.create_user("admin", pwd, role="admin")
    finally:
        db.close()
    yield TestClient(app, base_url="http://localhost"), pwd


def test_get_me_sets_csrf_cookie(client):
    """GET /api/auth/me with valid session returns Set-Cookie: csrf_token=..."""
    client, pwd = client
    login = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": pwd},
        headers={"Host": "localhost"},
    )
    assert login.status_code == 200
    session_cookie = login.cookies.get("session")
    assert session_cookie

    # GET /me with session cookie
    r = client.get("/api/auth/me", cookies={"session": session_cookie}, headers={"Host": "localhost"})
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie") or ""
    assert "csrf_token=" in set_cookie


def test_heavy_api_rate_limit_enforcement():
    """Repeated heavy API calls hit rate limit after threshold (30/min)."""
    from rate_limit import enforce_heavy_api_limits
    from fastapi import HTTPException
    from unittest.mock import MagicMock

    req = MagicMock()
    req.headers = {}
    req.client = MagicMock()
    req.client.host = "127.0.0.1"

    for _ in range(30):
        enforce_heavy_api_limits(req, "container_control")

    with pytest.raises(HTTPException) as exc_info:
        enforce_heavy_api_limits(req, "container_control")
    assert exc_info.value.status_code == 429
