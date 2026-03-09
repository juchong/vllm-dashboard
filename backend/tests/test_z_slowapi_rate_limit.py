"""Slowapi rate limit test. Runs last (z_ prefix) so 201 requests don't exhaust limit for other tests."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, shared_config_tmp):
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
    from models.auth_models import User
    from services.auth_service import AuthService
    init_db()
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            svc = AuthService(db)
            svc.create_user("admin", "testadmin123", role="admin")
    finally:
        db.close()
    yield TestClient(app, base_url="http://localhost")


def test_slowapi_rate_limit_returns_429(client):
    """Exceeding slowapi default limit returns 429."""
    for _ in range(200):
        r = client.get("/", headers={"Host": "localhost"})
        assert r.status_code == 200
    r = client.get("/", headers={"Host": "localhost"})
    assert r.status_code == 429
    body = r.json()
    msg = (body.get("detail") or body.get("error") or "").lower()
    assert "rate limit" in msg
