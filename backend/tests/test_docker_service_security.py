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
    # Compose-prefixed names (e.g. ai-vllm-1)
    _validate_container_name("ai-vllm-1")
    _validate_container_name("ai-vllm-mistral-1")


def test_rejects_non_vllm():
    with pytest.raises(ValueError, match="must be a vLLM container"):
        _validate_container_name("postgres")
    with pytest.raises(ValueError, match="must be a vLLM container"):
        _validate_container_name("redis")


def test_logs_allows_dashboard_proxy():
    """Log viewing allows dashboard/proxy (read-only); control ops still block them."""
    _validate_container_name("vllm-dashboard", allow_dashboard_proxy=True)
    _validate_container_name("vllm-proxy", allow_dashboard_proxy=True)
