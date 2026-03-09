"""
Instance registry for managing multiple vLLM instances.
Persists instance definitions to instances.yaml and provides
a VLLMService factory with caching.
"""

import os
import copy
import logging
import threading
import tempfile
from typing import Dict, Any, List, Optional

import yaml

import re

logger = logging.getLogger(__name__)

SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')
SAFE_SUBDOMAIN_PATTERN = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$')
SAFE_GPU_ID_PATTERN = re.compile(r'^[0-9]+$')
SAFE_DISPLAY_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9 _-]*$')

DEFAULT_INSTANCE_ID = "default"


def atomic_write_yaml(path: str, data: Any) -> None:
    """Write YAML atomically: write to temp file then os.replace()."""
    dir_name = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_text(path: str, text: str) -> None:
    """Write text file atomically."""
    dir_name = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class InstanceRegistry:
    """Manages vLLM instance definitions and provides VLLMService instances."""

    def __init__(self, config_dir: str, docker_service, hf_service):
        self.config_dir = config_dir
        self.docker_service = docker_service
        self.hf_service = hf_service
        self._instances_path = os.path.join(config_dir, "instances.yaml")
        self._instances: Dict[str, Dict[str, Any]] = {}
        self._vllm_services: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._compose_dir = os.environ.get("VLLM_COMPOSE_PATH", "/vllm-compose")
        self._load_or_create()

    def _load_or_create(self) -> None:
        """Load instances.yaml or auto-generate from existing single-instance setup."""
        if os.path.exists(self._instances_path):
            try:
                with open(self._instances_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                self._instances = data.get("instances", {})
                logger.info(f"Loaded {len(self._instances)} instance(s) from instances.yaml")
                return
            except (yaml.YAMLError, IOError) as e:
                logger.warning(f"Failed to read instances.yaml, regenerating: {e}")

        self._instances = {
            DEFAULT_INSTANCE_ID: {
                "display_name": "Primary",
                "container_name": "vllm",
                "proxy_container_name": "vllm-proxy",
                "port": 8000,
                "proxy_port": 4000,
                "subdomain": "vllm",
                "config_dir": ".",
                "managed_by": "compose",
                "gpu_device_ids": None,
            }
        }
        self._save()
        logger.info("Generated default instances.yaml from existing single-instance setup")

    def _save(self) -> None:
        atomic_write_yaml(self._instances_path, {"instances": self._instances})

    def _resolve_config_dir(self, instance_id: str) -> str:
        """Return the absolute config directory for an instance."""
        raw = self._instances[instance_id].get("config_dir", instance_id)
        if raw == ".":
            return self.config_dir
        return os.path.join(self.config_dir, raw)

    def _read_compose_defaults(self) -> Dict[str, Any]:
        """Parse compose.yaml + .env to extract live settings for the default instance."""
        result: Dict[str, Any] = {}
        compose_path = os.path.join(self._compose_dir, "compose.yaml")
        env_path = os.path.join(self._compose_dir, ".env")

        env_vars: Dict[str, str] = {}
        try:
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            env_vars[k.strip()] = v.strip()
        except Exception as e:
            logger.debug(f"Could not read compose .env: {e}")

        result["has_api_key"] = bool(env_vars.get("VLLM_API_KEY"))

        try:
            if not os.path.exists(compose_path):
                return result
            with open(compose_path, "r") as f:
                compose = yaml.safe_load(f) or {}
        except Exception as e:
            logger.debug(f"Could not parse compose.yaml: {e}")
            return result

        services = compose.get("services", {})

        vllm_svc = services.get("vllm", {})
        ports = vllm_svc.get("ports", [])
        result["expose_port"] = len(ports) > 0

        try:
            devices = vllm_svc.get("deploy", {}).get("resources", {}).get("reservations", {}).get("devices", [])
            if devices:
                dev = devices[0]
                ids = dev.get("device_ids")
                if isinstance(ids, list):
                    result["gpu_device_ids"] = [str(i) for i in ids]
        except Exception:
            pass

        proxy_svc = services.get("vllm-proxy", {})
        raw_labels = proxy_svc.get("labels", [])
        if isinstance(raw_labels, list):
            labels: Dict[str, str] = {}
            for lbl in raw_labels:
                lbl = str(lbl).strip()
                if "=" in lbl:
                    k, v = lbl.split("=", 1)
                    labels[k.strip()] = v.strip()
            result["labels"] = labels
        elif isinstance(raw_labels, dict):
            result["labels"] = {str(k): str(v) for k, v in raw_labels.items()}

        return result

    def _enrich_default_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Overlay compose-derived settings onto a default instance entry."""
        if entry.get("id") != DEFAULT_INSTANCE_ID:
            return entry
        try:
            compose_info = self._read_compose_defaults()
            if "has_api_key" in compose_info:
                entry["has_api_key"] = compose_info["has_api_key"]
            if "expose_port" in compose_info:
                entry["expose_port"] = compose_info["expose_port"]
            if "gpu_device_ids" in compose_info:
                entry["gpu_device_ids"] = compose_info["gpu_device_ids"]
            if "labels" in compose_info:
                entry["labels"] = compose_info["labels"]
        except Exception as e:
            logger.debug(f"Failed to enrich default instance from compose: {e}")
        return entry

    def list_instances(self) -> List[Dict[str, Any]]:
        with self._lock:
            result = []
            for inst_id, inst in self._instances.items():
                entry = {"id": inst_id, **copy.deepcopy(inst)}
                entry["configs_dir"] = self._resolve_config_dir(inst_id)
                entry["has_api_key"] = bool(inst.get("api_key"))
                entry.pop("api_key", None)
                entry = self._enrich_default_entry(entry)
                result.append(entry)
            return result

    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            inst = self._instances.get(instance_id)
            if inst is None:
                return None
            entry = {"id": instance_id, **copy.deepcopy(inst)}
            entry["configs_dir"] = self._resolve_config_dir(instance_id)
            entry["has_api_key"] = bool(inst.get("api_key"))
            entry.pop("api_key", None)
            return self._enrich_default_entry(entry)

    def create_instance(
        self,
        instance_id: str,
        display_name: str,
        port: int,
        proxy_port: int,
        subdomain: str,
        gpu_device_ids: Optional[List[str]] = None,
        api_key: Optional[str] = None,
        expose_port: bool = False,
        labels: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            if instance_id in self._instances:
                raise ValueError(f"Instance '{instance_id}' already exists")

            if not instance_id or len(instance_id) > 64 or not SAFE_ID_PATTERN.match(instance_id):
                raise ValueError("Invalid instance ID: must be 1-64 alphanumeric, hyphens, or underscores")

            if not display_name or len(display_name) > 128 or not SAFE_DISPLAY_NAME_PATTERN.match(display_name):
                raise ValueError("Invalid display name: must be 1-128 alphanumeric chars, spaces, hyphens, or underscores")

            if not subdomain or len(subdomain) > 63 or not SAFE_SUBDOMAIN_PATTERN.match(subdomain):
                raise ValueError("Invalid subdomain: must be a valid DNS label (1-63 alphanumeric and hyphens)")

            if not (1024 <= port <= 65535):
                raise ValueError("Port must be between 1024 and 65535")
            if not (1024 <= proxy_port <= 65535):
                raise ValueError("Proxy port must be between 1024 and 65535")
            if port == proxy_port:
                raise ValueError("Port and proxy port must be different")

            if gpu_device_ids is not None:
                if not isinstance(gpu_device_ids, list) or len(gpu_device_ids) > 16:
                    raise ValueError("gpu_device_ids must be a list of up to 16 GPU IDs")
                for gid in gpu_device_ids:
                    if not SAFE_GPU_ID_PATTERN.match(str(gid)):
                        raise ValueError(f"Invalid GPU device ID: {gid}")

            for iid, inst in self._instances.items():
                if inst["port"] == port:
                    raise ValueError(f"Port {port} already used by instance '{iid}'")
                if inst.get("proxy_port") == proxy_port:
                    raise ValueError(f"Proxy port {proxy_port} already used by instance '{iid}'")

            config_subdir = os.path.join(self.config_dir, instance_id)
            os.makedirs(config_subdir, exist_ok=True)

            self._instances[instance_id] = {
                "display_name": display_name,
                "container_name": f"vllm-{instance_id}",
                "proxy_container_name": f"vllm-proxy-{instance_id}",
                "port": port,
                "proxy_port": proxy_port,
                "subdomain": subdomain,
                "config_dir": instance_id,
                "managed_by": "sdk",
                "gpu_device_ids": gpu_device_ids,
                "api_key": api_key or None,
                "expose_port": bool(expose_port),
                "labels": labels or {},
            }
            self._save()
            logger.info(f"Created instance '{instance_id}' (port={port})")
            return self.get_instance(instance_id)

    def update_instance(self, instance_id: str, **kwargs) -> Dict[str, Any]:
        with self._lock:
            inst = self._instances.get(instance_id)
            if inst is None:
                raise ValueError(f"Instance '{instance_id}' not found")

            allowed = {"display_name", "subdomain", "gpu_device_ids", "api_key", "expose_port", "labels"}
            for key, value in kwargs.items():
                if key in allowed:
                    inst[key] = value

            if instance_id in self._vllm_services:
                del self._vllm_services[instance_id]

            self._save()
            return self.get_instance(instance_id)

    def delete_instance(self, instance_id: str) -> None:
        with self._lock:
            if instance_id == DEFAULT_INSTANCE_ID:
                raise ValueError("Cannot delete the default instance")
            if instance_id not in self._instances:
                raise ValueError(f"Instance '{instance_id}' not found")

            inst = self._instances[instance_id]
            for cname in (inst["container_name"], inst.get("proxy_container_name")):
                if cname:
                    try:
                        self.docker_service.remove_container(cname)
                    except Exception as e:
                        logger.warning(f"Failed to remove container {cname}: {e}")

            svc = self._vllm_services.pop(instance_id, None)

            del self._instances[instance_id]
            self._save()
            logger.info(f"Deleted instance '{instance_id}'")

    def get_vllm_service(self, instance_id: str):
        """Return a cached VLLMService for the given instance."""
        from services.vllm_service import VLLMService

        with self._lock:
            if instance_id in self._vllm_services:
                return self._vllm_services[instance_id]

            inst = self._instances.get(instance_id)
            if inst is None:
                raise ValueError(f"Instance '{instance_id}' not found")

            instance_config = {
                "id": instance_id,
                "container_name": inst["container_name"],
                "proxy_container_name": inst.get("proxy_container_name", ""),
                "configs_dir": self._resolve_config_dir(instance_id),
                "shared_configs_dir": self.config_dir,
                "port": inst["port"],
                "managed_by": inst.get("managed_by", "sdk"),
                "gpu_device_ids": inst.get("gpu_device_ids"),
                "api_key": inst.get("api_key"),
                "expose_port": inst.get("expose_port", False),
                "labels": inst.get("labels", {}),
            }

            svc = VLLMService(self.docker_service, self.hf_service, instance_config)
            self._vllm_services[instance_id] = svc
            return svc

    def get_instances_using_model(self, model_path: str) -> List[str]:
        """Return instance IDs that have this model as their active config."""
        result = []
        normalized = model_path.rstrip("/")
        for inst_id in list(self._instances.keys()):
            try:
                svc = self.get_vllm_service(inst_id)
                active = svc.get_active_config()
                if active and active.get("config", {}).get("model", "").rstrip("/") == normalized:
                    result.append(inst_id)
            except Exception:
                pass
        return result

    def get_all_container_names(self) -> set:
        """Return all known vLLM container names (vllm + proxy) across instances."""
        names = set()
        with self._lock:
            for inst in self._instances.values():
                names.add(inst["container_name"])
                if inst.get("proxy_container_name"):
                    names.add(inst["proxy_container_name"])
        return names
