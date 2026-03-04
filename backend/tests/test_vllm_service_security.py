"""Security tests for VLLMService config filename and path validation."""
import os
import pytest
from unittest.mock import MagicMock
from services.vllm_service import VLLMService


@pytest.fixture
def configs_dir(tmp_path):
    d = tmp_path / "configs"
    d.mkdir()
    return str(d)


@pytest.fixture
def vllm_service(configs_dir, monkeypatch):
    monkeypatch.setenv("VLLM_CONFIG_DIR", configs_dir)
    monkeypatch.setenv("VLLM_COMPOSE_PATH", "/nonexistent")
    mock_docker = MagicMock()
    service = VLLMService(docker_service=mock_docker)
    service.configs_dir = configs_dir
    service.active_config_path = os.path.join(configs_dir, "active.yaml")
    service.active_env_path = os.path.join(configs_dir, "env.active")
    return service


def test_validate_config_filename_rejects_path_traversal(vllm_service):
    with pytest.raises(ValueError, match="Invalid config filename"):
        vllm_service._validate_config_filename("../etc/passwd.yaml")
    with pytest.raises(ValueError, match="Invalid config filename"):
        vllm_service._validate_config_filename("..\\evil.yaml")


def test_validate_config_filename_rejects_active(vllm_service):
    with pytest.raises(ValueError, match="Invalid config filename"):
        vllm_service._validate_config_filename("active.yaml")


def test_validate_config_filename_rejects_non_yaml(vllm_service):
    with pytest.raises(ValueError, match="Invalid config filename"):
        vllm_service._validate_config_filename("config.txt")


def test_validate_config_filename_accepts_valid(vllm_service):
    vllm_service._validate_config_filename("my-model.yaml")
    vllm_service._validate_config_filename("Qwen--Qwen3-Coder.yaml")


def test_switch_config_rejects_symlink_outside_configs_dir(vllm_service, tmp_path):
    """Symlink inside configs pointing outside should be rejected."""
    outside = tmp_path / "outside"
    outside.mkdir()
    evil_yaml = outside / "evil.yaml"
    evil_yaml.write_text("model: evil\n")
    link_inside = os.path.join(vllm_service.configs_dir, "evil_link.yaml")
    os.symlink(evil_yaml, link_inside)
    with pytest.raises(ValueError, match="Invalid config filename"):
        vllm_service.switch_config("evil_link.yaml")
