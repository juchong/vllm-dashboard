"""Tests for vLLM image update functionality."""
import os
import pytest
from unittest.mock import MagicMock, patch
from services.vllm_service import VLLMService


@pytest.fixture
def configs_dir(tmp_path):
    d = tmp_path / "configs"
    d.mkdir()
    return str(d)


@pytest.fixture
def vllm_service(configs_dir, tmp_path, monkeypatch):
    compose_path = tmp_path / "compose"
    compose_path.mkdir()
    monkeypatch.setenv("VLLM_CONFIG_DIR", configs_dir)
    monkeypatch.setenv("VLLM_COMPOSE_PATH", str(compose_path))
    mock_docker = MagicMock()
    mock_docker._subprocess_env = os.environ.copy()
    mock_hf = MagicMock()
    service = VLLMService(docker_service=mock_docker, hf_service=mock_hf)
    service.configs_dir = configs_dir
    service.compose_path = str(compose_path)
    return service


class TestUpdateImage:
    """Tests for update_image functionality."""

    def test_update_image_reads_active_image(self, vllm_service):
        """update_image should read the active.image file and use it for pull."""
        active_image_path = os.path.join(vllm_service.configs_dir, "active.image")
        with open(active_image_path, "w") as f:
            f.write("vllm/vllm-openai:nightly")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            vllm_service.update_image()

            calls = mock_run.call_args_list
            assert len(calls) >= 1
            pull_call = calls[0]
            env = pull_call.kwargs.get("env", {})
            assert env.get("VLLM_IMAGE") == "vllm/vllm-openai:nightly"

    def test_update_image_calls_docker_compose_pull(self, vllm_service):
        """update_image should call docker compose pull."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            vllm_service.update_image()

            pull_call = mock_run.call_args_list[0]
            cmd = pull_call.args[0]
            assert "docker" in cmd
            assert "compose" in cmd
            assert "pull" in cmd
            assert "vllm" in cmd

    def test_update_image_restarts_after_pull(self, vllm_service):
        """update_image should restart container after successful pull."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = vllm_service.update_image()

            assert len(mock_run.call_args_list) == 2
            restart_call = mock_run.call_args_list[1]
            cmd = restart_call.args[0]
            assert "up" in cmd
            assert "--force-recreate" in cmd

    def test_update_image_returns_error_on_pull_failure(self, vllm_service):
        """update_image should return error if pull fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, 
                stdout="", 
                stderr="Error: pull failed"
            )
            result = vllm_service.update_image()

            assert result["success"] is False
            assert "Pull failed" in result["message"]
            assert mock_run.call_count == 1

    def test_update_image_without_active_image_file(self, vllm_service):
        """update_image should work even without active.image file."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = vllm_service.update_image()

            pull_call = mock_run.call_args_list[0]
            env = pull_call.kwargs.get("env", {})
            assert "VLLM_IMAGE" not in env or env.get("VLLM_IMAGE") is None

    def test_update_image_validates_image_name(self, vllm_service):
        """update_image should validate and reject invalid image names."""
        active_image_path = os.path.join(vllm_service.configs_dir, "active.image")
        with open(active_image_path, "w") as f:
            f.write("evil;rm -rf /")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            vllm_service.update_image()

            pull_call = mock_run.call_args_list[0]
            env = pull_call.kwargs.get("env", {})
            assert "VLLM_IMAGE" not in env


class TestUpdateImageAPI:
    """Tests for /api/vllm/update-image endpoint."""

    @pytest.fixture
    def client(self, monkeypatch, shared_config_tmp):
        """Test client with mocked services."""
        monkeypatch.setenv("VLLM_CONFIG_DIR", shared_config_tmp)
        monkeypatch.setenv("VLLM_COMPOSE_PATH", shared_config_tmp)
        monkeypatch.setenv("VLLM_MODELS_DIR", shared_config_tmp)
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
            if db.query(User).filter(User.username == "operator").count() == 0:
                svc.create_user("operator", "operator123", role="operator")
        finally:
            db.close()

        from fastapi.testclient import TestClient
        yield TestClient(app, base_url="http://localhost")

    def test_update_image_requires_admin(self, client):
        """update-image endpoint requires admin role."""
        r = client.post(
            "/api/auth/login",
            data={"username": "operator", "password": "operator123"},
            headers={"Host": "localhost"}
        )
        assert r.status_code == 200
        cookies = {"session": r.cookies.get("session")}
        csrf = r.cookies.get("csrf_token")
        headers = {"Host": "localhost", "X-CSRF-Token": csrf}

        r2 = client.post(
            "/api/vllm/update-image",
            cookies=cookies,
            headers=headers
        )
        assert r2.status_code == 403

    def test_update_image_requires_authentication(self, client):
        """update-image endpoint requires authentication (CSRF or auth rejection)."""
        with pytest.raises(Exception):
            client.post(
                "/api/vllm/update-image",
                headers={"Host": "localhost"}
            )
