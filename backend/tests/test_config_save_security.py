"""Security tests for ConfigService save_config and sanitize_config_filename."""
import os
import pytest
from services.config_service import ConfigService, sanitize_config_filename


@pytest.fixture
def config_service(tmp_path, monkeypatch):
    d = tmp_path / "configs"
    d.mkdir()
    monkeypatch.setenv("VLLM_CONFIG_DIR", str(d))
    return ConfigService()


def test_sanitize_removes_path_chars():
    assert "/" not in sanitize_config_filename("org/model")
    assert "\\" not in sanitize_config_filename("org\\model")
    assert ":" not in sanitize_config_filename("C:\\path")


def test_save_config_stays_in_config_dir(config_service):
    """save_config must not escape config_dir regardless of model_name."""
    path = config_service.save_config("../../../../etc/evil", {"model": "evil"})
    real_path = os.path.realpath(path)
    real_config_dir = os.path.realpath(config_service.config_dir)
    assert real_path.startswith(real_config_dir), f"Path {path} escaped config_dir"
