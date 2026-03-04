"""Security tests for HuggingFaceService delete_model and rename_model (path traversal)."""
import os
import tempfile
import pytest
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


def test_delete_model_rejects_path_outside_models_dir(hf_service, tmp_path):
    """Path traversal: delete /etc via .. should be rejected."""
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "secret"
    outside_file.write_text("secret")
    path = os.path.join(hf_service.models_dir, "..", "outside")
    with pytest.raises(Exception, match="outside models directory"):
        hf_service.delete_model(path)


def test_delete_model_rejects_symlink_outside_models_dir(hf_service, tmp_path):
    """Symlink traversal: symlink pointing outside models_dir should be rejected."""
    outside = tmp_path / "outside"
    outside.mkdir()
    link_inside = os.path.join(hf_service.models_dir, "evil_link")
    os.symlink(outside, link_inside)
    with pytest.raises(Exception, match="outside models directory"):
        hf_service.delete_model(link_inside)


def test_delete_model_allows_valid_path(hf_service):
    """Valid path within models_dir should succeed."""
    valid_dir = os.path.join(hf_service.models_dir, "valid_model")
    os.makedirs(valid_dir)
    try:
        result = hf_service.delete_model(valid_dir)
        assert "deleted successfully" in result
        assert not os.path.exists(valid_dir)
    finally:
        if os.path.exists(valid_dir):
            import shutil
            shutil.rmtree(valid_dir, ignore_errors=True)


def test_rename_model_rejects_old_path_outside_models_dir(hf_service, tmp_path):
    """Path traversal: rename from path outside models_dir should be rejected."""
    outside = tmp_path / "outside"
    outside.mkdir()
    target = os.path.join(hf_service.models_dir, "target")
    path = os.path.join(hf_service.models_dir, "..", "outside")
    with pytest.raises(Exception, match="outside models directory"):
        hf_service.rename_model(path, target)


def test_rename_model_rejects_new_path_outside_models_dir(hf_service):
    """Path traversal: rename to path outside models_dir should be rejected."""
    valid_dir = os.path.join(hf_service.models_dir, "valid_model")
    os.makedirs(valid_dir, exist_ok=True)
    try:
        evil_target = os.path.join(hf_service.models_dir, "..", "etc", "pwned")
        with pytest.raises(Exception, match="outside models directory"):
            hf_service.rename_model(valid_dir, evil_target)
    finally:
        import shutil
        shutil.rmtree(valid_dir, ignore_errors=True)


def test_rename_model_rejects_symlink_old_path_outside(hf_service, tmp_path):
    """Symlink traversal: symlink as old_path pointing outside should be rejected."""
    outside = tmp_path / "outside"
    outside.mkdir()
    link_inside = os.path.join(hf_service.models_dir, "evil_link")
    os.symlink(outside, link_inside)
    target = os.path.join(hf_service.models_dir, "target")
    with pytest.raises(Exception, match="outside models directory"):
        hf_service.rename_model(link_inside, target)
