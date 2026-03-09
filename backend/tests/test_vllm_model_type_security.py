"""Security tests for model_type validation and image injection."""
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
    mock_hf.read_model_metadata.return_value = None
    service = VLLMService(docker_service=mock_docker, hf_service=mock_hf)
    service.configs_dir = configs_dir
    return service


def test_resolve_model_type_rejects_path_traversal(vllm_service):
    """model_type from config must be in allowlist."""
    with pytest.raises(ValueError, match="Invalid model_type"):
        vllm_service._resolve_model_type({"model_type": "../../../etc"})
    with pytest.raises(ValueError, match="Invalid model_type"):
        vllm_service._resolve_model_type({"model_type": "env.hardware"})


def test_resolve_model_type_accepts_valid(vllm_service):
    assert vllm_service._resolve_model_type({"model_type": "dense"}) == "dense"
    assert vllm_service._resolve_model_type({"model_type": "moe_fp8"}) == "moe_fp8"
    assert vllm_service._resolve_model_type({"model_type": "moe_fp4"}) == "moe_fp4"


def test_resolve_model_type_falls_back_to_dense(vllm_service):
    """Without explicit model_type and no config.json, falls back to dense."""
    assert vllm_service._resolve_model_type({"model": "some/unknown-model"}) == "dense"


def test_validate_vllm_image_rejects_shell_chars(vllm_service):
    with pytest.raises(ValueError, match="Invalid image name"):
        vllm_service._validate_vllm_image("vllm/vllm; rm -rf /")
    with pytest.raises(ValueError, match="Invalid image name"):
        vllm_service._validate_vllm_image("evil`id`")


def test_validate_vllm_image_accepts_valid(vllm_service):
    assert vllm_service._validate_vllm_image("vllm/vllm-openai:nightly") == "vllm/vllm-openai:nightly"
    assert vllm_service._validate_vllm_image("ghcr.io/org/image:tag") == "ghcr.io/org/image:tag"
