"""
vLLM service for managing the vLLM inference server
"""

import os
import re
import json
import logging
import yaml
from typing import Dict, Any, List, Optional
from services.docker_service import DockerService
from services.hf_service import HuggingFaceService, derive_model_type
from utils import ensure_within_dir

logger = logging.getLogger(__name__)


class VLLMService:
    DASHBOARD_ONLY_KEYS = {'model_type', 'env_vars', 'env_overrides', 'vllm_image'}
    ALLOWED_MODEL_TYPES = frozenset({
        "dense_full", "dense_fp8", "dense_int8", "dense_int4",
        "moe_full", "moe_fp8", "moe_fp4",
    })
    # Map legacy model_type values to new ones
    LEGACY_MODEL_TYPE_MAP = {
        "dense": "dense_full",
        "moe": "moe_full",
    }

    def __init__(self, docker_service: DockerService, hf_service: HuggingFaceService):
        self.docker_service = docker_service
        self.hf_service = hf_service
        self.configs_dir = os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")
        self.compose_path = os.environ.get("VLLM_COMPOSE_PATH", "/vllm-compose")
        self.active_config_path = os.path.join(self.configs_dir, "active.yaml")
        self.active_env_path = os.path.join(self.configs_dir, "env.active")
        self.container_name = "vllm"
        self.proxy_container_name = "vllm-proxy"
    
    def list_configs(self) -> List[Dict[str, Any]]:
        """List all available vLLM configurations."""
        configs = []
        
        try:
            for filename in os.listdir(self.configs_dir):
                if filename.endswith('.yaml') and filename not in ['active.yaml']:
                    filepath = os.path.join(self.configs_dir, filename)
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
            for filename in os.listdir(self.configs_dir):
                if filename.endswith('.yaml') and filename != 'active.yaml':
                    filepath = os.path.join(self.configs_dir, filename)
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
        """Reject path traversal and invalid filenames."""
        if not name or ".." in name or "/" in name or "\\" in name:
            raise ValueError("Invalid config filename")
        if not name.endswith(".yaml") or name == "active.yaml":
            raise ValueError("Invalid config filename")

    def _validate_vllm_image(self, image: str | None) -> str | None:
        """Validate Docker image name to prevent injection."""
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
        """Switch to a different configuration."""
        self._validate_config_filename(config_filename)
        config_path = os.path.join(self.configs_dir, config_filename)
        
        if not os.path.exists(config_path):
            raise ValueError(f"Config file not found: {config_filename}")
        
        real_path = ensure_within_dir(self.configs_dir, config_path)
        
        try:
            with open(real_path, 'r') as f:
                config = yaml.safe_load(f)
            
            model_type = self._resolve_model_type(config)
            env_vars = config.get("env_vars") or config.get("env_overrides") or {}
            vllm_image = self._validate_vllm_image(config.get("vllm_image"))
            
            processed_config = self._process_config_for_vllm(config)
            
            with open(self.active_config_path, 'w') as f:
                yaml.dump(processed_config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Processed and wrote {config_filename} to active.yaml")
            
            self._write_env_file(env_vars)
            logger.info(f"Updated env.active from config env_vars")
            
            active_image_path = os.path.join(self.configs_dir, "active.image")
            with open(active_image_path, 'w') as f:
                f.write(vllm_image or "")
            
            restart_result = self._restart_vllm_container(vllm_image=vllm_image)
            
            return {
                "success": True,
                "config_filename": config_filename,
                "model": config.get("model"),
                "model_type": model_type,
                "restart_result": restart_result,
            }
            
        except Exception as e:
            logger.error(f"Failed to switch config: {e}")
            raise

    def reload_active_config(self) -> Dict[str, Any]:
        """Re-read the source YAML for the active model, regenerate active.yaml + env.active,
        and force-recreate the container."""
        active = self.get_active_config()
        if not active or not active.get("filename"):
            raise ValueError("No active configuration found to reload")
        return self.switch_config(active["filename"])
    
    def get_vllm_status(self) -> Dict[str, Any]:
        """Get the status of the vLLM container."""
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
        """Restart the vLLM container."""
        return self._restart_vllm_container()
    
    def stop_vllm(self) -> Dict[str, Any]:
        """Stop the vLLM container."""
        try:
            container = self.docker_service.client.containers.get(self.container_name)
            container.stop(timeout=30)
            return {"success": True, "message": "vLLM container stopped"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def start_vllm(self) -> Dict[str, Any]:
        """Start the vLLM container. Uses force-recreate to ensure env_file is re-read."""
        return self._restart_vllm_container()

    def update_image(self) -> Dict[str, Any]:
        """Pull latest vLLM image and restart container."""
        import subprocess

        env = {**self.docker_service._subprocess_env}

        active_image_path = os.path.join(self.configs_dir, "active.image")
        if os.path.exists(active_image_path):
            with open(active_image_path) as f:
                image = f.read().strip()
            if image:
                try:
                    image = self._validate_vllm_image(image)
                    env["VLLM_IMAGE"] = image
                    logger.info(f"Pulling vLLM image: {image}")
                except ValueError:
                    pass

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

            logger.info("Image pulled, restarting container")
            return self._restart_vllm_container()

        except subprocess.TimeoutExpired:
            return {"success": False, "message": "Image pull timed out"}
        except Exception as e:
            return {"success": False, "message": f"Update failed: {str(e)}"}

    def get_proxy_status(self) -> Dict[str, Any]:
        """Get the status of the vLLM proxy container."""
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
        """Get contents of env.active."""
        if filename != "env.active":
            raise FileNotFoundError(f"Unknown env file: {filename}")
        
        filepath = os.path.join(self.configs_dir, filename)
        if not os.path.exists(filepath):
            return ""
        
        with open(filepath, 'r') as f:
            return f.read()
    
    def get_env_preview(self, config_filename: str) -> Dict[str, Any]:
        """Get env var preview for a given config."""
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
        """Strip dashboard-only fields and convert nested dicts to JSON strings."""
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
                logger.debug(f"Converted {key} to JSON string")
            else:
                processed[key] = value
        
        return processed

    def _resolve_model_type(self, config: Dict[str, Any]) -> str:
        """Resolve model type from explicit field or HuggingFace config.json metadata."""
        if "model_type" in config:
            mt = config["model_type"]
            # Handle legacy model_type values
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
        """Write the active environment file directly from config env_vars."""
        lines = [
            "# Active vLLM environment configuration",
            "# Managed by vllm-dashboard - DO NOT EDIT MANUALLY",
            "# Generated from model config env_vars",
            "",
        ]
        
        if env_vars:
            for key, value in env_vars.items():
                lines.append(f"{key}={value}")
        
        with open(self.active_env_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
    
    def _restart_vllm_container(self, vllm_image: str | None = None) -> Dict[str, Any]:
        """Restart the vLLM and proxy containers using docker compose."""
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
            logger.info(f"Using vLLM image: {image}")
        
        try:
            result = subprocess.run(
                ["docker", "compose", "-p", "ai", "up", "-d", "--force-recreate", "--pull", "missing", "vllm", "vllm-proxy"],
                cwd=self.compose_path,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "vLLM and proxy containers restarted",
                    "output": result.stdout,
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to restart containers",
                    "error": result.stderr,
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "Restart timed out",
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Restart failed: {str(e)}",
            }
