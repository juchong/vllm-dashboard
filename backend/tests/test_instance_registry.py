"""Tests for InstanceRegistry, multi-instance support, and resource locking."""
import os
import pytest
import yaml
from unittest.mock import MagicMock, patch

from services.instance_registry import (
    InstanceRegistry, atomic_write_yaml, atomic_write_text, DEFAULT_INSTANCE_ID,
)


@pytest.fixture
def config_dir(tmp_path):
    d = tmp_path / "configs"
    d.mkdir()
    return str(d)


@pytest.fixture
def mock_docker():
    svc = MagicMock()
    svc._subprocess_env = os.environ.copy()
    return svc


@pytest.fixture
def mock_hf():
    hf = MagicMock()
    hf.read_model_metadata.return_value = None
    return hf


@pytest.fixture
def registry(config_dir, mock_docker, mock_hf):
    return InstanceRegistry(config_dir=config_dir, docker_service=mock_docker, hf_service=mock_hf)


class TestAtomicWrites:
    def test_atomic_write_yaml_creates_file(self, tmp_path):
        path = str(tmp_path / "test.yaml")
        data = {"key": "value", "nested": {"a": 1}}
        atomic_write_yaml(path, data)
        with open(path) as f:
            loaded = yaml.safe_load(f)
        assert loaded == data

    def test_atomic_write_text_creates_file(self, tmp_path):
        path = str(tmp_path / "test.txt")
        atomic_write_text(path, "hello world\n")
        with open(path) as f:
            assert f.read() == "hello world\n"

    def test_atomic_write_yaml_replaces_existing(self, tmp_path):
        path = str(tmp_path / "test.yaml")
        atomic_write_yaml(path, {"old": True})
        atomic_write_yaml(path, {"new": True})
        with open(path) as f:
            loaded = yaml.safe_load(f)
        assert loaded == {"new": True}

    def test_atomic_write_text_replaces_existing(self, tmp_path):
        path = str(tmp_path / "test.txt")
        atomic_write_text(path, "old")
        atomic_write_text(path, "new")
        with open(path) as f:
            assert f.read() == "new"

    def test_atomic_write_yaml_no_leftover_temp(self, tmp_path):
        path = str(tmp_path / "test.yaml")
        atomic_write_yaml(path, {"ok": True})
        files = os.listdir(str(tmp_path))
        assert len(files) == 1
        assert files[0] == "test.yaml"


class TestInstanceRegistryInit:
    def test_creates_default_instance_on_first_run(self, registry, config_dir):
        instances = registry.list_instances()
        assert len(instances) == 1
        assert instances[0]["id"] == DEFAULT_INSTANCE_ID
        assert instances[0]["managed_by"] == "compose"
        assert os.path.exists(os.path.join(config_dir, "instances.yaml"))

    def test_loads_existing_instances_yaml(self, config_dir, mock_docker, mock_hf):
        data = {
            "instances": {
                "default": {
                    "display_name": "Primary",
                    "container_name": "vllm",
                    "proxy_container_name": "vllm-proxy",
                    "port": 8000,
                    "proxy_port": 4000,
                    "subdomain": "vllm",
                    "config_dir": ".",
                    "managed_by": "compose",
                    "gpu_device_ids": None,
                },
                "gpu1": {
                    "display_name": "GPU 1",
                    "container_name": "vllm-gpu1",
                    "proxy_container_name": "vllm-proxy-gpu1",
                    "port": 8001,
                    "proxy_port": 4001,
                    "subdomain": "vllm-gpu1",
                    "config_dir": "gpu1",
                    "managed_by": "sdk",
                    "gpu_device_ids": ["0"],
                },
            }
        }
        instances_path = os.path.join(config_dir, "instances.yaml")
        with open(instances_path, "w") as f:
            yaml.dump(data, f)

        reg = InstanceRegistry(config_dir=config_dir, docker_service=mock_docker, hf_service=mock_hf)
        instances = reg.list_instances()
        assert len(instances) == 2
        ids = {i["id"] for i in instances}
        assert ids == {"default", "gpu1"}


class TestInstanceCRUD:
    def test_create_instance(self, registry, config_dir):
        inst = registry.create_instance(
            instance_id="test1",
            display_name="Test 1",
            port=8001,
            proxy_port=4001,
            subdomain="test1",
        )
        assert inst["id"] == "test1"
        assert inst["container_name"] == "vllm-test1"
        assert inst["proxy_container_name"] == "litellm"
        assert inst["managed_by"] == "sdk"
        assert os.path.isdir(os.path.join(config_dir, "test1"))

    def test_create_duplicate_raises(self, registry):
        registry.create_instance("dup", "Dup", 8002, 4002, "dup")
        with pytest.raises(ValueError, match="already exists"):
            registry.create_instance("dup", "Dup2", 8003, 4003, "dup2")

    def test_create_duplicate_port_raises(self, registry):
        registry.create_instance("a", "A", 8010, 4010, "a")
        with pytest.raises(ValueError, match="Port 8010"):
            registry.create_instance("b", "B", 8010, 4011, "b")

    def test_create_duplicate_proxy_port_raises(self, registry):
        registry.create_instance("a", "A", 8020, 4020, "a")
        with pytest.raises(ValueError, match="Proxy port 4020"):
            registry.create_instance("b", "B", 8021, 4020, "b")

    def test_create_invalid_id_raises(self, registry):
        with pytest.raises(ValueError, match="Invalid instance ID"):
            registry.create_instance("../evil", "Evil", 8030, 4030, "evil")
        with pytest.raises(ValueError, match="Invalid instance ID"):
            registry.create_instance("", "Empty", 8031, 4031, "empty")
        with pytest.raises(ValueError, match="Invalid instance ID"):
            registry.create_instance("has space", "Spaces", 8032, 4032, "spaces")
        with pytest.raises(ValueError, match="Invalid instance ID"):
            registry.create_instance("semi;colon", "Semi", 8033, 4033, "semi")
        with pytest.raises(ValueError, match="Invalid instance ID"):
            registry.create_instance("back\\slash", "Back", 8034, 4034, "back")

    def test_get_instance(self, registry):
        registry.create_instance("get-me", "Get Me", 8040, 4040, "getme")
        inst = registry.get_instance("get-me")
        assert inst is not None
        assert inst["display_name"] == "Get Me"

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get_instance("nonexistent") is None

    def test_update_instance(self, registry):
        registry.create_instance("upd", "Original", 8050, 4050, "upd")
        updated = registry.update_instance("upd", display_name="Updated")
        assert updated["display_name"] == "Updated"

    def test_update_nonexistent_raises(self, registry):
        with pytest.raises(ValueError, match="not found"):
            registry.update_instance("nope", display_name="X")

    def test_delete_instance(self, registry, mock_docker):
        registry.create_instance("del-me", "Delete", 8060, 4060, "delme")
        assert registry.get_instance("del-me") is not None
        registry.delete_instance("del-me")
        assert registry.get_instance("del-me") is None
        assert mock_docker.remove_container.call_count >= 1

    def test_delete_default_raises(self, registry):
        with pytest.raises(ValueError, match="Cannot delete the default"):
            registry.delete_instance(DEFAULT_INSTANCE_ID)

    def test_delete_nonexistent_raises(self, registry):
        with pytest.raises(ValueError, match="not found"):
            registry.delete_instance("ghost")

    def test_list_instances_returns_all(self, registry):
        registry.create_instance("x", "X", 8070, 4070, "x")
        registry.create_instance("y", "Y", 8071, 4071, "y")
        instances = registry.list_instances()
        ids = {i["id"] for i in instances}
        assert "default" in ids
        assert "x" in ids
        assert "y" in ids
        assert len(instances) == 3

    def test_create_invalid_port_raises(self, registry):
        with pytest.raises(ValueError, match="Port must be between"):
            registry.create_instance("lowport", "Low", 80, 4080, "lowport")
        with pytest.raises(ValueError, match="Proxy port must be between"):
            registry.create_instance("lowproxy", "Low", 8080, 80, "lowproxy")
        with pytest.raises(ValueError, match="Port and proxy port must be different"):
            registry.create_instance("sameport", "Same", 8080, 8080, "sameport")

    def test_create_invalid_subdomain_raises(self, registry):
        with pytest.raises(ValueError, match="Invalid subdomain"):
            registry.create_instance("badsub", "Bad", 8081, 4081, "not valid!")
        with pytest.raises(ValueError, match="Invalid subdomain"):
            registry.create_instance("badsub2", "Bad", 8082, 4082, "-starts-with-dash")

    def test_create_invalid_display_name_raises(self, registry):
        with pytest.raises(ValueError, match="Invalid display name"):
            registry.create_instance("badname", "<script>", 8083, 4083, "badname")

    def test_create_invalid_gpu_ids_raises(self, registry):
        with pytest.raises(ValueError, match="Invalid GPU device ID"):
            registry.create_instance("badgpu", "Bad GPU", 8084, 4084, "badgpu", gpu_device_ids=["0", "abc"])
        with pytest.raises(ValueError, match="Invalid GPU device ID"):
            registry.create_instance("badgpu2", "Bad GPU", 8085, 4085, "badgpu2", gpu_device_ids=["0;rm -rf /"])


class TestVLLMServiceFactory:
    def test_get_vllm_service_returns_cached(self, registry):
        svc1 = registry.get_vllm_service("default")
        svc2 = registry.get_vllm_service("default")
        assert svc1 is svc2

    def test_get_vllm_service_nonexistent_raises(self, registry):
        with pytest.raises(ValueError, match="not found"):
            registry.get_vllm_service("nope")

    def test_get_vllm_service_sets_instance_fields(self, registry):
        registry.create_instance("svc-test", "Svc Test", 8080, 4080, "svctest")
        svc = registry.get_vllm_service("svc-test")
        assert svc.instance_id == "svc-test"
        assert svc.container_name == "vllm-svc-test"
        assert svc.managed_by == "sdk"


class TestGetAllContainerNames:
    def test_returns_all_names(self, registry):
        registry.create_instance("cn1", "CN1", 8090, 4090, "cn1")
        names = registry.get_all_container_names()
        assert "vllm" in names
        assert "litellm" in names
        assert "vllm-cn1" in names


class TestResourceLocking:
    def test_model_in_use_guard_blocks_delete(self):
        """_check_model_in_use should raise HTTPException when model is active."""
        from api.models import _check_model_in_use
        from fastapi import HTTPException

        mock_registry = MagicMock()
        mock_registry.get_instances_using_model.return_value = ["default"]
        mock_request = MagicMock()
        mock_request.app.state.instance_registry = mock_registry
        mock_request.app.state.download_manager = MagicMock(is_downloading=MagicMock(return_value=False))

        with pytest.raises(HTTPException) as exc_info:
            _check_model_in_use(mock_request, "org/model")
        assert exc_info.value.status_code == 400
        assert "in use" in str(exc_info.value.detail)

    def test_model_in_use_guard_blocks_downloading(self):
        """_check_model_in_use should raise HTTPException when model is being downloaded."""
        from api.models import _check_model_in_use
        from fastapi import HTTPException

        mock_registry = MagicMock()
        mock_registry.get_instances_using_model.return_value = []
        mock_download = MagicMock()
        mock_download.is_downloading.return_value = True
        mock_request = MagicMock()
        mock_request.app.state.instance_registry = mock_registry
        mock_request.app.state.download_manager = mock_download

        with pytest.raises(HTTPException) as exc_info:
            _check_model_in_use(mock_request, "org/model")
        assert exc_info.value.status_code == 400
        assert "downloaded" in str(exc_info.value.detail).lower()

    def test_model_in_use_guard_passes_when_free(self):
        """_check_model_in_use should not raise when model is not in use."""
        from api.models import _check_model_in_use

        mock_registry = MagicMock()
        mock_registry.get_instances_using_model.return_value = []
        mock_download = MagicMock()
        mock_download.is_downloading.return_value = False
        mock_request = MagicMock()
        mock_request.app.state.instance_registry = mock_registry
        mock_request.app.state.download_manager = mock_download

        _check_model_in_use(mock_request, "org/model")

    def test_model_in_use_guard_handles_no_registry(self):
        """_check_model_in_use should pass gracefully when registry is not set."""
        from api.models import _check_model_in_use

        mock_request = MagicMock()
        mock_request.app.state = MagicMock(spec=[])

        _check_model_in_use(mock_request, "org/model")

    def test_get_instances_using_model(self, registry, config_dir):
        active_yaml = os.path.join(config_dir, "active.yaml")
        active_config = {"model": "org/test-model", "dtype": "bfloat16"}
        atomic_write_yaml(active_yaml, active_config)

        result = registry.get_instances_using_model("org/test-model")
        assert "default" in result

    def test_get_instances_using_model_no_match(self, registry, config_dir):
        active_yaml = os.path.join(config_dir, "active.yaml")
        active_config = {"model": "org/other-model", "dtype": "bfloat16"}
        atomic_write_yaml(active_yaml, active_config)

        result = registry.get_instances_using_model("org/test-model")
        assert len(result) == 0


class TestInstancePersistence:
    def test_changes_persist_to_yaml(self, config_dir, mock_docker, mock_hf):
        reg1 = InstanceRegistry(config_dir=config_dir, docker_service=mock_docker, hf_service=mock_hf)
        reg1.create_instance("persist", "Persist", 9000, 5000, "persist")

        reg2 = InstanceRegistry(config_dir=config_dir, docker_service=mock_docker, hf_service=mock_hf)
        inst = reg2.get_instance("persist")
        assert inst is not None
        assert inst["display_name"] == "Persist"

    def test_delete_persists(self, config_dir, mock_docker, mock_hf):
        reg1 = InstanceRegistry(config_dir=config_dir, docker_service=mock_docker, hf_service=mock_hf)
        reg1.create_instance("temp", "Temp", 9010, 5010, "temp")
        reg1.delete_instance("temp")

        reg2 = InstanceRegistry(config_dir=config_dir, docker_service=mock_docker, hf_service=mock_hf)
        assert reg2.get_instance("temp") is None
