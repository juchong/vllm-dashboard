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
    mock_hf = MagicMock()
    service = VLLMService(docker_service=mock_docker, hf_service=mock_hf)
    service.configs_dir = configs_dir
    service.active_config_path = os.path.join(configs_dir, "active.yaml")
    service.active_env_path = os.path.join(configs_dir, "env.active")
    return service


@pytest.fixture
def instance_vllm_service(configs_dir, monkeypatch):
    """VLLMService constructed with explicit instance_config."""
    monkeypatch.setenv("VLLM_COMPOSE_PATH", "/nonexistent")
    mock_docker = MagicMock()
    mock_hf = MagicMock()
    instance_config = {
        "id": "test-inst",
        "container_name": "vllm-test-inst",
        "proxy_container_name": "vllm-proxy-test-inst",
        "configs_dir": configs_dir,
        "port": 8001,
        "managed_by": "sdk",
    }
    return VLLMService(docker_service=mock_docker, hf_service=mock_hf,
                       instance_config=instance_config)


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
    with pytest.raises(ValueError, match="(Invalid config filename|escapes base directory)"):
        vllm_service.switch_config("evil_link.yaml")


def test_instance_config_sets_fields(instance_vllm_service):
    """VLLMService with instance_config should reflect the provided fields."""
    svc = instance_vllm_service
    assert svc.instance_id == "test-inst"
    assert svc.container_name == "vllm-test-inst"
    assert svc.proxy_container_name == "vllm-proxy-test-inst"
    assert svc.port == 8001
    assert svc.managed_by == "sdk"


def test_default_constructor_sets_compose_defaults(vllm_service):
    """VLLMService without instance_config should default to compose settings."""
    assert vllm_service.instance_id == "default"
    assert vllm_service.container_name == "vllm"
    assert vllm_service.managed_by == "compose"


def test_op_lock_exists(vllm_service):
    """VLLMService should have an operation lock."""
    assert hasattr(vllm_service, '_op_lock')
