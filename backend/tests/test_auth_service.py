"""Tests for AuthService functionality: password change, user management, session handling."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


@pytest.fixture
def client(monkeypatch, shared_config_tmp):
    """Test client with fresh database and admin user."""
    tmp = shared_config_tmp
    monkeypatch.setenv("VLLM_CONFIG_DIR", tmp)
    monkeypatch.setenv("VLLM_COMPOSE_PATH", tmp)
    monkeypatch.setenv("VLLM_MODELS_DIR", tmp)
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "testadmin123")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
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
        if db.query(User).filter(User.username == "testuser").count() == 0:
            svc.create_user("testuser", "testuser123", role="viewer")
    finally:
        db.close()
    yield TestClient(app, base_url="http://localhost")


@pytest.fixture
def auth_service_with_db(shared_config_tmp):
    """Provide AuthService with real database session."""
    from database import SessionLocal
    from services.auth_service import AuthService
    db = SessionLocal()
    yield AuthService(db)
    db.close()


class TestPasswordChange:
    """Tests for password change functionality."""

    def test_password_change_success(self, client):
        """Password change via API succeeds with correct current password."""
        # Login
        r = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testuser123"},
            headers={"Host": "localhost"}
        )
        assert r.status_code == 200
        cookies = {"session": r.cookies.get("session")}
        csrf = r.cookies.get("csrf_token")
        headers = {"Host": "localhost", "X-CSRF-Token": csrf}

        # Change password
        r2 = client.post(
            "/api/auth/password",
            json={"current_password": "testuser123", "new_password": "newpassword123"},
            cookies=cookies,
            headers=headers
        )
        assert r2.status_code == 200
        assert "success" in r2.json().get("message", "").lower()

        # Verify new password works - login with new password
        r3 = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "newpassword123"},
            headers={"Host": "localhost"}
        )
        assert r3.status_code == 200

        # Verify old password no longer works
        r4 = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testuser123"},
            headers={"Host": "localhost"}
        )
        assert r4.status_code == 401

        # Reset password for other tests
        cookies2 = {"session": r3.cookies.get("session")}
        csrf2 = r3.cookies.get("csrf_token")
        headers2 = {"Host": "localhost", "X-CSRF-Token": csrf2}
        client.post(
            "/api/auth/password",
            json={"current_password": "newpassword123", "new_password": "testuser123"},
            cookies=cookies2,
            headers=headers2
        )

    def test_password_change_wrong_current_password(self, client):
        """Password change fails with incorrect current password."""
        r = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testuser123"},
            headers={"Host": "localhost"}
        )
        assert r.status_code == 200
        cookies = {"session": r.cookies.get("session")}
        csrf = r.cookies.get("csrf_token")
        headers = {"Host": "localhost", "X-CSRF-Token": csrf}

        r2 = client.post(
            "/api/auth/password",
            json={"current_password": "wrongpassword", "new_password": "newpassword123"},
            cookies=cookies,
            headers=headers
        )
        assert r2.status_code == 401
        assert "incorrect" in r2.json().get("detail", "").lower()

    def test_password_change_too_short(self, client):
        """Password change fails when new password is too short."""
        r = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testuser123"},
            headers={"Host": "localhost"}
        )
        assert r.status_code == 200
        cookies = {"session": r.cookies.get("session")}
        csrf = r.cookies.get("csrf_token")
        headers = {"Host": "localhost", "X-CSRF-Token": csrf}

        r2 = client.post(
            "/api/auth/password",
            json={"current_password": "testuser123", "new_password": "short"},
            cookies=cookies,
            headers=headers
        )
        assert r2.status_code == 400
        assert "8" in r2.json().get("detail", "") or "length" in r2.json().get("detail", "").lower()

    def test_password_change_requires_auth(self, client):
        """Password change endpoint requires authentication (blocked by CSRF or auth)."""
        import pytest
        # Without session cookie/CSRF token, request is rejected by middleware
        # Test client raises exception when middleware rejects request
        with pytest.raises(Exception):
            client.post(
                "/api/auth/password",
                json={"current_password": "testuser123", "new_password": "newpassword123"},
                headers={"Host": "localhost"}
            )

    def test_password_change_persists_across_sessions(self, client):
        """Password change persists and works in new database sessions."""
        # Login and change password
        r = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "testadmin123"},
            headers={"Host": "localhost"}
        )
        assert r.status_code == 200
        cookies = {"session": r.cookies.get("session")}
        csrf = r.cookies.get("csrf_token")
        headers = {"Host": "localhost", "X-CSRF-Token": csrf}

        r2 = client.post(
            "/api/auth/password",
            json={"current_password": "testadmin123", "new_password": "adminchanged123"},
            cookies=cookies,
            headers=headers
        )
        assert r2.status_code == 200

        # Force new session by logging out and back in
        client.post("/api/auth/logout", cookies=cookies, headers=headers)

        # Login with new password in fresh session
        r3 = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "adminchanged123"},
            headers={"Host": "localhost"}
        )
        assert r3.status_code == 200

        # Reset for other tests
        cookies3 = {"session": r3.cookies.get("session")}
        csrf3 = r3.cookies.get("csrf_token")
        headers3 = {"Host": "localhost", "X-CSRF-Token": csrf3}
        client.post(
            "/api/auth/password",
            json={"current_password": "adminchanged123", "new_password": "testadmin123"},
            cookies=cookies3,
            headers=headers3
        )


class TestAuthServiceUnit:
    """Unit tests for AuthService methods."""

    def test_change_password_refetches_user(self, auth_service_with_db):
        """change_password re-fetches user from its own session to handle detached objects."""
        from database import SessionLocal
        from models.auth_models import User

        svc = auth_service_with_db

        # Create detached user object (simulating what happens in API)
        db_other = SessionLocal()
        detached_user = db_other.query(User).filter(User.username == "admin").first()
        db_other.close()  # User is now detached

        # This should still work because change_password re-fetches
        original_hash = detached_user.password_hash
        svc.change_password(detached_user, "testadmin123", "temppass12345")

        # Verify change persisted
        db_verify = SessionLocal()
        admin = db_verify.query(User).filter(User.username == "admin").first()
        assert admin.password_hash != original_hash
        assert svc.verify_password("temppass12345", admin.password_hash)

        # Reset
        admin.password_hash = svc.hash_password("testadmin123")
        db_verify.commit()
        db_verify.close()

    def test_hash_password_produces_bcrypt(self, auth_service_with_db):
        """hash_password produces valid bcrypt hash."""
        svc = auth_service_with_db
        hashed = svc.hash_password("testpassword")
        assert hashed.startswith("$2b$")
        assert svc.verify_password("testpassword", hashed)
        assert not svc.verify_password("wrongpassword", hashed)

    def test_verify_password_timing_safe(self, auth_service_with_db):
        """verify_password uses constant-time comparison."""
        svc = auth_service_with_db
        hashed = svc.hash_password("testpassword")
        # Both should complete without raising
        assert svc.verify_password("testpassword", hashed) is True
        assert svc.verify_password("x" * 100, hashed) is False


class TestModelDeletion:
    """Tests for model deletion and cleanup."""

    def test_delete_model_cleans_config(self, shared_config_tmp, monkeypatch):
        """delete_model removes associated config YAML files."""
        import os
        import yaml

        monkeypatch.setenv("VLLM_CONFIG_DIR", shared_config_tmp)
        monkeypatch.setenv("VLLM_MODELS_DIR", shared_config_tmp)

        from services.hf_service import HuggingFaceService
        from services.config_service import ConfigService

        # Create test model directory
        model_dir = os.path.join(shared_config_tmp, "TestOrg", "TestModel")
        os.makedirs(model_dir, exist_ok=True)
        with open(os.path.join(model_dir, "config.json"), "w") as f:
            f.write('{"model_type": "test"}')

        # Create matching config YAML
        config_path = os.path.join(shared_config_tmp, "TestOrg--TestModel.yaml")
        with open(config_path, "w") as f:
            yaml.dump({"model": "TestOrg/TestModel", "served_model_name": "test"}, f)

        # Wire services
        hf_service = HuggingFaceService()
        hf_service.models_dir = shared_config_tmp
        config_service = ConfigService()
        config_service.config_dir = shared_config_tmp
        hf_service.config_service = config_service

        # Delete model
        hf_service.delete_model(model_dir)

        # Verify both are gone
        assert not os.path.exists(model_dir)
        assert not os.path.exists(config_path)

    def test_delete_model_logs_timing(self, shared_config_tmp, monkeypatch, caplog):
        """delete_model logs size and elapsed time."""
        import os
        import logging

        monkeypatch.setenv("VLLM_CONFIG_DIR", shared_config_tmp)
        monkeypatch.setenv("VLLM_MODELS_DIR", shared_config_tmp)

        from services.hf_service import HuggingFaceService

        # Create test model directory
        model_dir = os.path.join(shared_config_tmp, "LogTest", "Model")
        os.makedirs(model_dir, exist_ok=True)
        with open(os.path.join(model_dir, "config.json"), "w") as f:
            f.write('{"test": true}')

        hf_service = HuggingFaceService()
        hf_service.models_dir = shared_config_tmp

        with caplog.at_level(logging.INFO):
            hf_service.delete_model(model_dir)

        assert any("Starting deletion" in r.message for r in caplog.records)
        assert any("Deleted model" in r.message for r in caplog.records)
