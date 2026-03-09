"""
vLLM service for managing a single vLLM inference server instance.
Each instance of this class manages one vLLM container+proxy pair.
"""

import os
import re
import json
import logging
import threading
import yaml
from typing import Dict, Any, List, Optional
from services.docker_service import DockerService
from services.hf_service import HuggingFaceService, derive_model_type
from services.instance_registry import atomic_write_yaml, atomic_write_text
from utils import ensure_within_dir

logger = logging.getLogger(__name__)


class VLLMService:
    DASHBOARD_ONLY_KEYS = {'model_type', 'env_vars', 'env_overrides', 'vllm_image', 'port'}
    ALLOWED_MODEL_TYPES = frozenset({
        "dense_full", "dense_fp8", "dense_int8", "dense_int4",
        "moe_full", "moe_fp8", "moe_fp4",
    })
    LEGACY_MODEL_TYPE_MAP = {
        "dense": "dense_full",
        "moe": "moe_full",
    }

    def __init__(self, docker_service: DockerService, hf_service: HuggingFaceService,
                 instance_config: Optional[Dict[str, Any]] = None):
        self.docker_service = docker_service
        self.hf_service = hf_service
        self._op_lock = threading.Lock()

        if instance_config:
            self.instance_id = instance_config["id"]
            self.container_name = instance_config["container_name"]
            self.proxy_container_name = instance_config.get("proxy_container_name", "")
            self.configs_dir = instance_config["configs_dir"]
            self.port = instance_config.get("port", 8000)
            self.managed_by = instance_config.get("managed_by", "sdk")
            self.gpu_device_ids = instance_config.get("gpu_device_ids")
            self.shared_configs_dir = instance_config.get("shared_configs_dir", self.configs_dir)
            self.api_key = instance_config.get("api_key")
            self.expose_port = instance_config.get("expose_port", False)
            self.instance_labels = instance_config.get("labels", {})
        else:
            self.instance_id = "default"
            self.configs_dir = os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")
            self.container_name = "vllm"
            self.proxy_container_name = "vllm-proxy"
            self.port = 8000
            self.managed_by = "compose"
            self.gpu_device_ids = None
            self.shared_configs_dir = self.configs_dir
            self.api_key = None
            self.expose_port = False
            self.instance_labels = {}

        self.compose_path = os.environ.get("VLLM_COMPOSE_PATH", "/vllm-compose")
        self.active_config_path = os.path.join(self.configs_dir, "active.yaml")
        self.active_env_path = os.path.join(self.configs_dir, "env.active")

    def list_configs(self) -> List[Dict[str, Any]]:
        """List all available vLLM configurations from the shared config directory."""
        configs = []
        try:
            for filename in os.listdir(self.shared_configs_dir):
                if filename.endswith('.yaml') and filename not in ['active.yaml', 'instances.yaml']:
                    filepath = os.path.join(self.shared_configs_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            config = yaml.safe_load(f)

                        try:
                            model_type = self._resolve_model_type(config)
                        except ValueError:
                            logger.warning(f"Skipping config {filename}: invalid model_type")
                            continue

                        meta = self.hf_service.read_model_metadata(config.get("model", ""))
                        entry = {
                            "filename": filename,
                            "name": config.get("served_model_name", filename),
                            "model": config.get("model", "unknown"),
                            "model_type": model_type,
                            "max_model_len": config.get("max_model_len", 0),
                            "tensor_parallel_size": config.get("tensor_parallel_size", 1),
                        }
                        if meta:
                            entry["num_experts"] = meta["num_experts"]
                            entry["quant_method"] = meta["quant_method"]
                            entry["architecture"] = meta["architecture"]
                        configs.append(entry)
                    except (yaml.YAMLError, IOError) as e:
                        logger.warning(f"Failed to read config {filename}: {e}")

            configs.sort(key=lambda x: x["name"])
        except Exception as e:
            logger.error(f"Failed to list configs: {e}")
            raise
        return configs

    def get_active_config(self) -> Optional[Dict[str, Any]]:
        """Get the currently active configuration."""
        try:
            if not os.path.exists(self.active_config_path):
                return None

            with open(self.active_config_path, 'r') as f:
                config = yaml.safe_load(f)

            config_filename = None
            source_config = None
            for filename in os.listdir(self.shared_configs_dir):
                if filename.endswith('.yaml') and filename not in ('active.yaml', 'instances.yaml'):
                    filepath = os.path.join(self.shared_configs_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            candidate = yaml.safe_load(f)
                        if candidate.get("model") == config.get("model"):
                            config_filename = filename
                            source_config = candidate
                            break
                    except (yaml.YAMLError, IOError, OSError):
                        pass

            resolve_from = source_config if source_config else config
            model_type = self._resolve_model_type(resolve_from)

            result = {
                "config": config,
                "filename": config_filename,
                "model_type": model_type,
            }

            meta = self.hf_service.read_model_metadata(config.get("model", ""))
            if meta:
                result["num_experts"] = meta["num_experts"]
                result["quant_method"] = meta["quant_method"]
                result["architecture"] = meta["architecture"]

            return result
        except Exception as e:
            logger.error(f"Failed to get active config: {e}")
            raise

    def _validate_config_filename(self, name: str) -> None:
        if not name or ".." in name or "/" in name or "\\" in name:
            raise ValueError("Invalid config filename")
        if not name.endswith(".yaml") or name in ("active.yaml", "instances.yaml"):
            raise ValueError("Invalid config filename")

    def _validate_vllm_image(self, image: str | None) -> str | None:
        if not image or not image.strip():
            return None
        img = image.strip()
        if len(img) > 256:
            raise ValueError("Image name too long")
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._\-/:]*$", img):
            raise ValueError("Invalid image name")
        if any(c in img for c in (";", "$", "`", "|", "&", "<", ">", "\n", "\r")):
            raise ValueError("Invalid image name")
        allowed = os.environ.get("VLLM_ALLOWED_IMAGE_PREFIXES", "vllm/,ghcr.io/")
        allowed_prefixes = tuple([x.strip() for x in allowed.split(",") if x.strip()])
        if allowed_prefixes and not img.startswith(allowed_prefixes):
            raise ValueError("Image is not in allowlist")
        return img

    def switch_config(self, config_filename: str) -> Dict[str, Any]:
        """Switch to a different configuration (serialized per-instance)."""
        with self._op_lock:
            return self._switch_config_locked(config_filename)

    def _switch_config_locked(self, config_filename: str) -> Dict[str, Any]:
        self._validate_config_filename(config_filename)
        config_path = os.path.join(self.shared_configs_dir, config_filename)

        if not os.path.exists(config_path):
            raise ValueError(f"Config file not found: {config_filename}")

        real_path = ensure_within_dir(self.shared_configs_dir, config_path)

        try:
            with open(real_path, 'r') as f:
                config = yaml.safe_load(f)

            model_type = self._resolve_model_type(config)
            env_vars = config.get("env_vars") or config.get("env_overrides") or {}
            vllm_image = self._validate_vllm_image(config.get("vllm_image"))

            processed_config = self._process_config_for_vllm(config)

            processed_config["port"] = self.port

            atomic_write_yaml(self.active_config_path, processed_config)
            logger.info(f"[{self.instance_id}] Wrote {config_filename} to active.yaml")

            self._write_env_file(env_vars)

            active_image_path = os.path.join(self.configs_dir, "active.image")
            atomic_write_text(active_image_path, vllm_image or "")

            return {
                "success": True,
                "config_filename": config_filename,
                "model": config.get("model"),
                "model_type": model_type,
            }
        except Exception as e:
            logger.error(f"[{self.instance_id}] Failed to switch config: {e}")
            raise

    def reload_active_config(self) -> Dict[str, Any]:
        """Re-read the source YAML for the active model, regenerate active.yaml + env.active,
        and force-recreate the container."""
        active = self.get_active_config()
        if not active or not active.get("filename"):
            raise ValueError("No active configuration found to reload")
        return self.switch_config(active["filename"])

    def get_vllm_status(self) -> Dict[str, Any]:
        try:
            container = self.docker_service.client.containers.get(self.container_name)
            return {
                "status": container.status,
                "running": container.status == "running",
                "id": container.id[:12],
                "image": container.image.tags[0] if container.image.tags else str(container.image.id)[:12],
                "created": container.attrs.get("Created", ""),
                "health": container.attrs.get("State", {}).get("Health", {}).get("Status", "unknown"),
            }
        except Exception as e:
            return {
                "status": "not_found",
                "running": False,
                "error": str(e),
            }

    def restart_vllm(self) -> Dict[str, Any]:
        with self._op_lock:
            return self._restart_vllm_container()

    def stop_vllm(self) -> Dict[str, Any]:
        with self._op_lock:
            try:
                container = self.docker_service.client.containers.get(self.container_name)
                container.stop(timeout=30)
                return {"success": True, "message": f"Container {self.container_name} stopped"}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def start_vllm(self) -> Dict[str, Any]:
        with self._op_lock:
            return self._restart_vllm_container()

    def update_image(self) -> Dict[str, Any]:
        with self._op_lock:
            return self._update_image_locked()

    def _update_image_locked(self) -> Dict[str, Any]:
        import subprocess

        active_image_path = os.path.join(self.configs_dir, "active.image")
        image = None
        if os.path.exists(active_image_path):
            with open(active_image_path) as f:
                raw = f.read().strip()
            if raw:
                try:
                    image = self._validate_vllm_image(raw)
                except ValueError:
                    image = None

        if self.managed_by == "compose":
            env = {**self.docker_service._subprocess_env}
            if image:
                env["VLLM_IMAGE"] = image
                logger.info(f"[{self.instance_id}] Pulling vLLM image: {image}")

            try:
                result = subprocess.run(
                    ["docker", "compose", "-p", "ai", "pull", "vllm"],
                    cwd=self.compose_path,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    env=env,
                )
                if result.returncode != 0:
                    return {"success": False, "message": f"Pull failed: {result.stderr}"}
                logger.info(f"[{self.instance_id}] Image pulled, restarting container")
                return self._restart_vllm_container()
            except subprocess.TimeoutExpired:
                return {"success": False, "message": "Image pull timed out"}
            except Exception as e:
                return {"success": False, "message": f"Update failed: {str(e)}"}
        else:
            tag = image or "vllm/vllm-openai:nightly"
            try:
                self.docker_service.pull_image(tag)
                logger.info(f"[{self.instance_id}] SDK image pulled: {tag}")
                return self._restart_vllm_container(vllm_image=tag)
            except Exception as e:
                return {"success": False, "message": f"Update failed: {str(e)}"}

    def get_proxy_status(self) -> Dict[str, Any]:
        if not self.proxy_container_name:
            return {"status": "not_configured", "running": False}
        try:
            container = self.docker_service.client.containers.get(self.proxy_container_name)
            return {
                "status": container.status,
                "running": container.status == "running",
                "id": container.id[:12],
            }
        except Exception as e:
            return {
                "status": "not_found",
                "running": False,
                "error": str(e),
            }

    def get_env_file(self, filename: str) -> str:
        if filename != "env.active":
            raise FileNotFoundError(f"Unknown env file: {filename}")
        filepath = os.path.join(self.configs_dir, filename)
        if not os.path.exists(filepath):
            return ""
        with open(filepath, 'r') as f:
            return f.read()

    def get_env_preview(self, config_filename: str) -> Dict[str, Any]:
        self._validate_config_filename(config_filename)
        config_path = os.path.join(self.configs_dir, config_filename)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_filename}")
        real_path = ensure_within_dir(self.configs_dir, config_path)

        with open(real_path, 'r') as f:
            config = yaml.safe_load(f)

        model_type = self._resolve_model_type(config)
        env_vars = config.get("env_vars") or config.get("env_overrides") or {}
        merged = {str(k): str(v) for k, v in env_vars.items()}

        return {
            "model_type": model_type,
            "env_vars": merged,
            "merged": merged,
        }

    def _process_config_for_vllm(self, config: Dict[str, Any]) -> Dict[str, Any]:
        json_string_keys = {
            'compilation_config',
            'override_neuron_config',
            'hf_overrides',
            'pooling_type_config',
        }
        processed = {}
        for key, value in config.items():
            if key in self.DASHBOARD_ONLY_KEYS:
                continue
            if key in json_string_keys and isinstance(value, dict):
                processed[key] = json.dumps(value)
            else:
                processed[key] = value
        return processed

    def _resolve_model_type(self, config: Dict[str, Any]) -> str:
        if "model_type" in config:
            mt = config["model_type"]
            mt = self.LEGACY_MODEL_TYPE_MAP.get(mt, mt)
            if mt not in self.ALLOWED_MODEL_TYPES:
                raise ValueError("Invalid model_type")
            return mt

        model_name = config.get("model", "")
        meta = self.hf_service.read_model_metadata(model_name)
        if meta:
            return derive_model_type(
                meta["num_experts"],
                meta["quant_method"],
                meta.get("weights_type"),
                meta.get("weights_bits"),
            )
        return "dense_full"

    def _write_env_file(self, env_vars: Dict[str, str] | None = None) -> None:
        lines = [
            "# Active vLLM environment configuration",
            "# Managed by vllm-dashboard - DO NOT EDIT MANUALLY",
            "",
        ]
        if env_vars:
            for key, value in env_vars.items():
                lines.append(f"{key}={value}")
        atomic_write_text(self.active_env_path, '\n'.join(lines) + '\n')

    def _restart_vllm_container(self, vllm_image: str | None = None) -> Dict[str, Any]:
        """Restart the vLLM container. Method depends on managed_by."""
        if self.managed_by == "compose":
            return self._restart_compose(vllm_image)
        else:
            return self._restart_sdk(vllm_image)

    def _restart_compose(self, vllm_image: str | None = None) -> Dict[str, Any]:
        import subprocess

        env = {**self.docker_service._subprocess_env}
        image = vllm_image
        if not image:
            active_image_path = os.path.join(self.configs_dir, "active.image")
            if os.path.exists(active_image_path):
                with open(active_image_path) as f:
                    raw = f.read().strip()
                if raw:
                    try:
                        image = self._validate_vllm_image(raw)
                    except ValueError:
                        image = None
        if image:
            env["VLLM_IMAGE"] = image

        try:
            services = ["vllm"]
            if self.proxy_container_name:
                services.append("vllm-proxy")
            result = subprocess.run(
                ["docker", "compose", "-p", "ai", "up", "-d", "--force-recreate", "--pull", "missing"] + services,
                cwd=self.compose_path,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            if result.returncode == 0:
                return {"success": True, "message": "Containers restarted", "output": result.stdout}
            else:
                return {"success": False, "message": "Failed to restart containers", "error": result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "Restart timed out"}
        except Exception as e:
            return {"success": False, "message": f"Restart failed: {str(e)}"}

    def _restart_sdk(self, vllm_image: str | None = None) -> Dict[str, Any]:
        """Restart an SDK-managed instance by removing + recreating."""
        try:
            self.docker_service.remove_container(self.container_name)
        except Exception as e:
            logger.warning(f"[{self.instance_id}] Could not remove old container: {e}")

        image = vllm_image
        if not image:
            active_image_path = os.path.join(self.configs_dir, "active.image")
            if os.path.exists(active_image_path):
                with open(active_image_path) as f:
                    raw = f.read().strip()
                if raw:
                    try:
                        image = self._validate_vllm_image(raw)
                    except ValueError:
                        image = None
        if not image:
            image = "vllm/vllm-openai:nightly"

        env = self._build_sdk_env()
        command_str = self._build_sdk_command()
        volumes = self._build_sdk_volumes()

        try:
            from services.docker_service import InstanceContainerConfig
            port_mapping = {f"{self.port}/tcp": self.port} if self.expose_port else None
            config = InstanceContainerConfig(
                image=image,
                container_name=self.container_name,
                environment=env,
                volumes=volumes,
                command=command_str,
                gpu_device_ids=self.gpu_device_ids,
                network="traefik",
                port=self.port,
                labels=self._build_sdk_labels(),
                ports=port_mapping,
            )
            self.docker_service.create_vllm_container(config)
            return {"success": True, "message": f"Container {self.container_name} created"}
        except Exception as e:
            logger.error(f"[{self.instance_id}] SDK restart failed: {e}")
            return {"success": False, "message": f"Restart failed: {str(e)}"}

    def _build_sdk_env(self) -> Dict[str, str]:
        """Build environment dict for SDK container from env.active."""
        env = {}
        if os.path.exists(self.active_env_path):
            with open(self.active_env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        env[k] = v

        env.setdefault("VLLM_API_KEY", os.environ.get("VLLM_API_KEY", "local"))
        env.setdefault("HF_TOKEN", os.environ.get("HF_TOKEN", ""))
        return env

    def _build_sdk_command(self) -> str:
        api_key = self.api_key or os.environ.get("VLLM_API_KEY", "local")
        return f"--config /root/.cache/vllm/configs/active.yaml --api-key {api_key}"

    def _build_sdk_volumes(self) -> Dict[str, Dict[str, str]]:
        host_models = os.environ.get("VLLM_HOST_MODELS_DIR",
                                     os.environ.get("VLLM_MODELS_DIR", "/models"))
        host_vllm_data = os.environ.get("VLLM_HOST_DATA_DIR",
                                        os.environ.get("VLLM_DATA_DIR", "/mnt/tiny/docker/data/vllm"))
        host_config_root = os.environ.get("VLLM_HOST_CONFIG_DIR",
                                          os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs"))
        container_config_root = os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")

        if self.configs_dir == container_config_root:
            host_configs = host_config_root
        else:
            rel = os.path.relpath(self.configs_dir, container_config_root)
            host_configs = os.path.join(host_config_root, rel)

        return {
            host_models: {"bind": "/root/.cache/huggingface", "mode": "rw"},
            host_vllm_data: {"bind": "/root/.cache/vllm", "mode": "rw"},
            host_configs: {"bind": "/root/.cache/vllm/configs", "mode": "rw"},
        }

    def _build_sdk_labels(self) -> Dict[str, str]:
        base = {
            "managed_by": "vllm-dashboard",
            "vllm.instance": self.instance_id,
        }
        if self.instance_labels:
            base.update(self.instance_labels)
        return base
