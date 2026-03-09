"""Security tests for download path - model_name must not escape models_dir."""
import os
import pytest
from services.download_manager import _validate_model_path
from services.hf_service import HuggingFaceService


@pytest.fixture
def models_dir(tmp_path):
    d = tmp_path / "models"
    d.mkdir()
    return str(d)


@pytest.fixture
def hf_service(models_dir, monkeypatch):
    monkeypatch.setenv("VLLM_MODELS_DIR", models_dir)
    return HuggingFaceService()


def test_download_path_stays_in_models_dir(hf_service):
    """local_dir for model_name must resolve within models_dir."""
    model_name = "org/model-name"
    local_dir = os.path.join(hf_service.models_dir, model_name)
    real_local = os.path.realpath(local_dir)
    real_models = os.path.realpath(hf_service.models_dir)
    assert real_local.startswith(real_models), "Download path must stay in models_dir"


def test_download_path_rejects_traversal(models_dir):
    """model_name with .. must be rejected by path validation (runtime uses DownloadManager)."""
    evil_name = "../../../etc"
    local_dir = os.path.join(models_dir, evil_name)
    real_local = os.path.realpath(os.path.normpath(local_dir))
    real_models = os.path.realpath(models_dir)
    assert not real_local.startswith(real_models), "Path escapes - validation must reject"
    with pytest.raises(ValueError, match="Invalid model name"):
        _validate_model_path(models_dir, evil_name)
