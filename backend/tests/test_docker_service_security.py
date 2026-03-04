"""Security tests for DockerService container name validation."""
import pytest
from services.docker_service import _validate_container_name


def test_rejects_empty():
    with pytest.raises(ValueError, match="Invalid container name"):
        _validate_container_name("")


def test_rejects_path_traversal():
    with pytest.raises(ValueError, match="Invalid container name"):
        _validate_container_name("../../../etc")


def test_rejects_dashboard():
    with pytest.raises(ValueError, match="dashboard or proxy"):
        _validate_container_name("vllm-dashboard")


def test_rejects_proxy():
    with pytest.raises(ValueError, match="dashboard or proxy"):
        _validate_container_name("vllm-proxy")


def test_accepts_valid():
    _validate_container_name("vllm")
    _validate_container_name("vllm-qwen")
    _validate_container_name("vllm-mistral")
