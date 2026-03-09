"""Shared test fixtures. Use session-scoped tmp so database module (imported once) keeps valid path."""
import os
import tempfile
import pytest

_shared_tmp = None


@pytest.fixture(scope="session")
def shared_config_tmp():
    """Single tmp dir for entire test session; database module caches path at first import."""
    global _shared_tmp
    if _shared_tmp is None:
        _shared_tmp = tempfile.mkdtemp(prefix="vllm_test_", dir="/tmp")
    return _shared_tmp


@pytest.fixture(scope="session", autouse=True)
def _set_env_before_db_import(shared_config_tmp):
    """Set env before any test imports database; prevents deleted-tmp readonly errors."""
    os.environ["VLLM_CONFIG_DIR"] = shared_config_tmp
    os.environ["VLLM_COMPOSE_PATH"] = shared_config_tmp
    os.environ["VLLM_MODELS_DIR"] = shared_config_tmp
    yield
