"""Security tests for ConfigService associate_config (path traversal)."""
import os
import tempfile
import pytest
import yaml
from services.config_service import ConfigService


@pytest.fixture
def config_dir(tmp_path):
    d = tmp_path / "configs"
    d.mkdir()
    return str(d)


@pytest.fixture
def config_service(config_dir, monkeypatch):
    monkeypatch.setenv("VLLM_CONFIG_DIR", config_dir)
    return ConfigService()


def test_associate_config_rejects_path_outside_config_dir(config_service, tmp_path):
    """Path traversal: config_path outside config_dir should be rejected."""
    outside = tmp_path / "outside"
    outside.mkdir()
    evil_yaml = outside / "evil.yaml"
    evil_yaml.write_text("model: evil\n")
    with pytest.raises(ValueError, match="must be within"):
        config_service.associate_config("model/name", str(evil_yaml))


def test_associate_config_rejects_symlink_outside_config_dir(config_service, tmp_path):
    """Symlink traversal: symlink pointing outside config_dir should be rejected."""
    outside = tmp_path / "outside"
    outside.mkdir()
    evil_yaml = outside / "evil.yaml"
    evil_yaml.write_text("model: evil\n")
    link_inside = os.path.join(config_service.config_dir, "evil_link.yaml")
    os.symlink(evil_yaml, link_inside)
    with pytest.raises(ValueError, match="must be within"):
        config_service.associate_config("model/name", link_inside)


def test_associate_config_rejects_empty_path(config_service):
    with pytest.raises(ValueError, match="cannot be empty"):
        config_service.associate_config("model/name", "   ")


def test_associate_config_rejects_nonexistent_path(config_service):
    """Non-existent file should be rejected."""
    with pytest.raises(ValueError, match="does not exist"):
        config_service.associate_config("model/name", "definitely_nonexistent_12345.yaml")


def test_associate_config_rejects_non_yaml_file(config_service):
    """Only .yaml/.yml files should be accepted."""
    txt_path = os.path.join(config_service.config_dir, "evil.txt")
    with open(txt_path, "w") as f:
        f.write("model: evil")
    with pytest.raises(ValueError, match="must be a YAML file"):
        config_service.associate_config("model/name", txt_path)


def test_associate_config_succeeds_valid_path(config_service):
    """Valid path within config_dir should succeed."""
    yaml_path = os.path.join(config_service.config_dir, "valid.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump({"model": "old", "dtype": "bfloat16"}, f)
    result = config_service.associate_config("org/new-model", yaml_path)
    assert "Associated" in result
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    assert data["model"] == "org/new-model"
    assert data["served_model_name"] == "new-model"


def test_get_config_templates_returns_list(config_service):
    """get_config_templates should return a list of templates."""
    templates = config_service.get_config_templates()
    assert isinstance(templates, list)
    assert len(templates) >= 3
    for t in templates:
        assert "name" in t
        assert "description" in t
