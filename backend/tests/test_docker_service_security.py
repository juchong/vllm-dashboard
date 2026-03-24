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
    with pytest.raises(ValueError, match="must be a vLLM or allowed proxy container"):
        _validate_container_name("postgres")
    with pytest.raises(ValueError, match="must be a vLLM or allowed proxy container"):
        _validate_container_name("redis")


def test_logs_allows_dashboard_proxy():
    """Log viewing allows dashboard/proxy (read-only); control ops still block them."""
    _validate_container_name("vllm-dashboard", allow_dashboard_proxy=True)
    _validate_container_name("vllm-proxy", allow_dashboard_proxy=True)


def test_accepts_multi_instance_names():
    """Multi-instance container names like vllm-{id} should be accepted."""
    _validate_container_name("vllm-default")
    _validate_container_name("vllm-gpu0")
    _validate_container_name("vllm-inference-2")


def test_rejects_multi_instance_proxy_on_control():
    """Proxy containers for instances should be rejected for control operations."""
    with pytest.raises(ValueError, match="dashboard or proxy"):
        _validate_container_name("vllm-proxy-default")
    with pytest.raises(ValueError, match="dashboard or proxy"):
        _validate_container_name("vllm-proxy-gpu0")


def test_allows_multi_instance_proxy_for_logs():
    """Proxy containers should be allowed when allow_dashboard_proxy=True (log viewing)."""
    _validate_container_name("vllm-proxy-default", allow_dashboard_proxy=True)
    _validate_container_name("vllm-proxy-gpu0", allow_dashboard_proxy=True)
