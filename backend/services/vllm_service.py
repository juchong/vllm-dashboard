"""
vLLM service for managing the vLLM inference server
"""

import os
import re
import json
import shutil
import logging
import yaml
from typing import Dict, Any, List, Optional
from services.docker_service import DockerService

logger = logging.getLogger(__name__)


class VLLMService:
    def __init__(self, docker_service: DockerService):
        self.docker_service = docker_service
        self.configs_dir = os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")
        self.compose_path = os.environ.get("VLLM_COMPOSE_PATH", "/vllm-compose")
        self.active_config_path = os.path.join(self.configs_dir, "active.yaml")
        self.active_env_path = os.path.join(self.configs_dir, "env.active")
        self.container_name = "vllm"
        self.proxy_container_name = "vllm-proxy"
    
    def list_configs(self) -> List[Dict[str, Any]]:
        """List all available vLLM configurations"""
        configs = []
        
        try:
            for filename in os.listdir(self.configs_dir):
                if filename.endswith('.yaml') and filename not in ['active.yaml']:
                    filepath = os.path.join(self.configs_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            config = yaml.safe_load(f)
                        
                        try:
                            model_type = self._detect_model_type(config)
                        except ValueError:
                            logger.warning(f"Skipping config {filename}: invalid model_type")
                            continue
                        configs.append({
                            "filename": filename,
                            "name": config.get("served_model_name", filename),
                            "model": config.get("model", "unknown"),
                            "model_type": model_type,
                            "max_model_len": config.get("max_model_len", 0),
                            "tensor_parallel_size": config.get("tensor_parallel_size", 1),
                        })
                    except (yaml.YAMLError, IOError) as e:
                        logger.warning(f"Failed to read config {filename}: {e}")
            
            configs.sort(key=lambda x: x["name"])
            
        except Exception as e:
            logger.error(f"Failed to list configs: {e}")
            raise
        
        return configs
    
    def get_active_config(self) -> Optional[Dict[str, Any]]:
        """Get the currently active configuration"""
        try:
            if not os.path.exists(self.active_config_path):
                return None
            
            with open(self.active_config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Find which config file this matches
            config_filename = None
            for filename in os.listdir(self.configs_dir):
                if filename.endswith('.yaml') and filename != 'active.yaml':
                    filepath = os.path.join(self.configs_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            candidate = yaml.safe_load(f)
                        if candidate.get("model") == config.get("model"):
                            config_filename = filename
                            break
                    except (yaml.YAMLError, IOError, OSError):
                        pass
            
            return {
                "config": config,
                "filename": config_filename,
                "model_type": self._detect_model_type(config),
            }
            
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
        return img

    def switch_config(self, config_filename: str) -> Dict[str, Any]:
        """Switch to a different configuration"""
        self._validate_config_filename(config_filename)
        config_path = os.path.join(self.configs_dir, config_filename)
        
        if not os.path.exists(config_path):
            raise ValueError(f"Config file not found: {config_filename}")
        
        real_path = os.path.realpath(config_path)
        real_configs_dir = os.path.realpath(self.configs_dir)
        if not real_path.startswith(real_configs_dir):
            raise ValueError("Invalid config filename")
        
        try:
            # Read the new config
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            model_type = self._detect_model_type(config)
            env_overrides = config.get("env_overrides", {})
            vllm_image = self._validate_vllm_image(config.get("vllm_image"))
            
            # Process config: convert nested dicts to JSON strings, strip dashboard-only fields
            processed_config = self._process_config_for_vllm(config)
            
            # Write the processed active config
            with open(self.active_config_path, 'w') as f:
                yaml.dump(processed_config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Processed and wrote {config_filename} to active.yaml")
            
            # Write the active env file (hardware + model-type + per-model overrides)
            self._write_env_file(model_type, env_overrides)
            logger.info(f"Updated env.active for model_type={model_type}")
            
            # Persist the active image so restarts use the same image
            active_image_path = os.path.join(self.configs_dir, "active.image")
            with open(active_image_path, 'w') as f:
                f.write(vllm_image or "")
            
            # Restart vLLM and ensure proxy is running
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
    
    def get_vllm_status(self) -> Dict[str, Any]:
        """Get the status of the vLLM container"""
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
        """Restart the vLLM container"""
        return self._restart_vllm_container()
    
    def stop_vllm(self) -> Dict[str, Any]:
        """Stop the vLLM container"""
        try:
            container = self.docker_service.client.containers.get(self.container_name)
            container.stop(timeout=30)
            return {"success": True, "message": "vLLM container stopped"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def start_vllm(self) -> Dict[str, Any]:
        """Start the vLLM container. Uses force-recreate to ensure env_file is re-read."""
        return self._restart_vllm_container()
    
    def get_proxy_status(self) -> Dict[str, Any]:
        """Get the status of the vLLM proxy container"""
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
    
    # Environment file management methods
    
    def list_env_files(self) -> List[Dict[str, Any]]:
        """List all environment files with metadata"""
        env_files = []
        
        # Define the env files we care about
        env_file_info = {
            "env.hardware": {"description": "Hardware-specific settings (NCCL tuning)", "editable": True},
            "env.moe-fp8": {"description": "FP8 MoE model optimizations", "editable": True},
            "env.moe-fp4": {"description": "FP4 MoE model optimizations", "editable": True},
            "env.dense": {"description": "Dense model settings", "editable": True},
            "env.active": {"description": "Active configuration (auto-generated)", "editable": False},
        }
        
        for filename, info in env_file_info.items():
            filepath = os.path.join(self.configs_dir, filename)
            exists = os.path.exists(filepath)
            
            env_files.append({
                "filename": filename,
                "description": info["description"],
                "editable": info["editable"],
                "exists": exists,
            })
        
        return env_files
    
    def get_env_file(self, filename: str) -> str:
        """Get contents of a specific environment file"""
        # Only allow reading known env files
        allowed_files = ["env.hardware", "env.moe-fp8", "env.moe-fp4", "env.dense", "env.active"]
        if filename not in allowed_files:
            raise FileNotFoundError(f"Unknown env file: {filename}")
        
        filepath = os.path.join(self.configs_dir, filename)
        
        if not os.path.exists(filepath):
            # Return empty content for non-existent files
            return ""
        
        with open(filepath, 'r') as f:
            return f.read()
    
    def update_env_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Update contents of a specific environment file"""
        # Only allow editing certain env files
        editable_files = ["env.hardware", "env.moe-fp8", "env.moe-fp4", "env.dense"]
        if filename not in editable_files:
            raise ValueError(f"Cannot edit {filename}")
        
        filepath = os.path.join(self.configs_dir, filename)
        
        # Write the file
        with open(filepath, 'w') as f:
            f.write(content)
        
        logger.info(f"Updated env file: {filename}")
        
        return {
            "success": True,
            "filename": filename,
            "message": f"Successfully updated {filename}",
        }
    
    def get_env_preview(self, config_filename: str) -> Dict[str, Any]:
        """Get a layered preview of env vars that would be set for a given config."""
        self._validate_config_filename(config_filename)
        config_path = os.path.join(self.configs_dir, config_filename)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_filename}")
        real_path = os.path.realpath(config_path)
        real_configs_dir = os.path.realpath(self.configs_dir)
        if not real_path.startswith(real_configs_dir):
            raise ValueError("Invalid config filename")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        model_type = self._detect_model_type(config)
        model_type_filename = f"env.{model_type.replace('_', '-')}"
        
        hardware_env = self._read_env_file("env.hardware")
        model_type_env = self._read_env_file(model_type_filename)
        overrides = config.get("env_overrides", {})
        
        inherited = {}
        inherited_sources = {}
        for key, value in hardware_env.items():
            inherited[key] = value
            inherited_sources[key] = "env.hardware"
        for key, value in model_type_env.items():
            inherited[key] = value
            inherited_sources[key] = model_type_filename
        
        merged = {**inherited, **{str(k): str(v) for k, v in overrides.items()}}
        
        return {
            "model_type": model_type,
            "model_type_filename": model_type_filename,
            "inherited": inherited,
            "inherited_sources": inherited_sources,
            "overrides": {str(k): str(v) for k, v in overrides.items()},
            "merged": merged,
        }

    # Fields used by the dashboard but not valid vLLM config keys
    DASHBOARD_ONLY_KEYS = {'model_type', 'env_overrides', 'vllm_image'}

    def _process_config_for_vllm(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process config for writing to active.yaml:
        - Strip dashboard-only fields (model_type, env_overrides)
        - Convert nested dicts to JSON strings for keys vLLM expects as JSON
        """
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
    
    ALLOWED_MODEL_TYPES = frozenset({"dense", "moe_fp8", "moe_fp4"})

    def _detect_model_type(self, config: Dict[str, Any]) -> str:
        """Detect the model type from config. Prefers explicit model_type field, falls back to heuristic."""
        if "model_type" in config:
            mt = config["model_type"]
            if mt not in self.ALLOWED_MODEL_TYPES:
                raise ValueError("Invalid model_type")
            return mt
        
        model = config.get("model", "").lower()
        
        # FP4 MoE models
        if ("fp4" in model or "nvfp4" in model) and ("moe" in model or "a3b" in model or "scout" in model or "m2" in model):
            return "moe_fp4"
        if config.get("enable_expert_parallel") and ("fp4" in model or "nvfp4" in model):
            return "moe_fp4"
        
        # FP8 MoE models
        if "fp8" in model and ("moe" in model or "a3b" in model or "coder" in model):
            return "moe_fp8"
        if "a3b" in model or ("moe" in model and "fp4" not in model):
            return "moe_fp8"
        
        return "dense"
    
    def _read_env_file(self, filename: str) -> Dict[str, str]:
        """Read an env file and parse into dict"""
        filepath = os.path.join(self.configs_dir, filename)
        env_vars = {}
        
        if not os.path.exists(filepath):
            return env_vars
        
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        return env_vars
    
    def _write_env_file(self, model_type: str, env_overrides: Dict[str, str] | None = None) -> None:
        """Write the active environment file by combining hardware + model-type + per-model overrides."""
        hardware_env = self._read_env_file("env.hardware")
        
        model_type_filename = f"env.{model_type.replace('_', '-')}"
        model_type_env = self._read_env_file(model_type_filename)
        
        sources = [f"env.hardware + {model_type_filename}"]
        if env_overrides:
            sources.append("env_overrides")
        
        lines = [
            "# Active vLLM environment configuration",
            "# Managed by vllm-dashboard - DO NOT EDIT MANUALLY",
            f"# Generated from: {' + '.join(sources)}",
            "",
            "# Hardware-specific settings (from env.hardware)",
        ]
        
        for key, value in hardware_env.items():
            lines.append(f"{key}={value}")
        
        if model_type_env:
            lines.append("")
            lines.append(f"# Model-type settings (from {model_type_filename})")
            for key, value in model_type_env.items():
                lines.append(f"{key}={value}")
        else:
            lines.append("")
            lines.append(f"# Model type: {model_type} (no additional env vars)")
        
        if env_overrides:
            lines.append("")
            lines.append("# Per-model overrides (from config env_overrides)")
            for key, value in env_overrides.items():
                lines.append(f"{key}={value}")
        
        with open(self.active_env_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
    
    def _restart_vllm_container(self, vllm_image: str | None = None) -> Dict[str, Any]:
        """Restart the vLLM and proxy containers using docker compose.
        Injects VLLM_IMAGE into the subprocess env so compose resolves ${VLLM_IMAGE:-default}."""
        import subprocess
        
        env = {**self.docker_service._subprocess_env}
        
        # Use provided image, or fall back to persisted active.image
        image = vllm_image
        if not image:
            active_image_path = os.path.join(self.configs_dir, "active.image")
            if os.path.exists(active_image_path):
                raw = open(active_image_path).read().strip()
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
