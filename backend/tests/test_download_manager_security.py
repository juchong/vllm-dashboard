"""Security tests for DownloadManager path validation and poisoned state."""
import os
import pytest
from services.download_manager import DownloadManager, _validate_model_path, DownloadTask, DownloadStatus
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


@pytest.fixture
def download_manager(hf_service, tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setenv("VLLM_CONFIG_DIR", str(state_dir))
    return DownloadManager(hf_service)


def test_validate_model_path_rejects_traversal(models_dir):
    with pytest.raises(ValueError, match="Invalid model name"):
        _validate_model_path(models_dir, "../../../etc")
    with pytest.raises(ValueError, match="Invalid model name"):
        _validate_model_path(models_dir, "org/../../../etc")


def test_start_download_rejects_traversal(download_manager):
    with pytest.raises(ValueError, match="Invalid model name"):
        download_manager.start_download("../../../etc")


def test_from_dict_rejects_poisoned_model_name(models_dir):
    task = DownloadTask.from_dict(
        {"id": "x", "model_name": "../../../etc", "status": "resumable"},
        models_dir=models_dir
    )
    assert task is None


def test_from_dict_handles_invalid_status(models_dir):
    task = DownloadTask.from_dict(
        {"id": "y", "model_name": "org/model", "status": "invalid_status"},
        models_dir=models_dir
    )
    assert task is not None
    assert task.status == DownloadStatus.FAILED
