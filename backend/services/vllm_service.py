"""
vLLM service for managing the vLLM inference server
"""

import os
import shutil
import logging
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
        
        # Hardware-specific env vars (constant for this system)
        self.hardware_env = {
            "NCCL_ALGO": "Ring",
            "NCCL_PROTO": "Simple",
            "NCCL_MIN_NCHANNELS": "4",
            "NCCL_MAX_NCHANNELS": "8",
            "NCCL_BUFFSIZE": "8388608",
            "NCCL_P2P_LEVEL": "PHB",
            "NCCL_DEBUG": "WARN",
            "NCCL_IB_DISABLE": "1",
            "TORCH_CUDA_ARCH_LIST": "12.0",
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
        }
        
        # Model-type specific env vars
        self.model_type_envs = {
            "moe_fp8": {
                "VLLM_USE_FLASHINFER_MOE_FP8": "1",
                "VLLM_FLASHINFER_MOE_BACKEND": "latency",
            },
            "dense": {
                # No special env vars for dense models
            },
        }
    
    def list_configs(self) -> List[Dict[str, Any]]:
        """List all available vLLM configurations"""
        import yaml
        configs = []
        
        try:
            for filename in os.listdir(self.configs_dir):
                if filename.endswith('.yaml') and filename not in ['active.yaml']:
                    filepath = os.path.join(self.configs_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            config = yaml.safe_load(f)
                        
                        configs.append({
                            "filename": filename,
                            "name": config.get("served_model_name", filename),
                            "model": config.get("model", "unknown"),
                            "model_type": self._detect_model_type(config),
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
        import yaml
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
                    except:
                        pass
            
            return {
                "config": config,
                "filename": config_filename,
                "model_type": self._detect_model_type(config),
            }
            
        except Exception as e:
            logger.error(f"Failed to get active config: {e}")
            raise
    
    def switch_config(self, config_filename: str) -> Dict[str, Any]:
        """Switch to a different configuration"""
        import yaml
        config_path = os.path.join(self.configs_dir, config_filename)
        
        if not os.path.exists(config_path):
            raise ValueError(f"Config file not found: {config_filename}")
        
        try:
            # Read the new config
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            model_type = self._detect_model_type(config)
            
            # Write the active config
            shutil.copy(config_path, self.active_config_path)
            logger.info(f"Copied {config_filename} to active.yaml")
            
            # Write the active env file
            self._write_env_file(model_type)
            logger.info(f"Updated env.active for model_type={model_type}")
            
            # Restart vLLM and ensure proxy is running
            restart_result = self._restart_vllm_container()
            
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
        """Start the vLLM container"""
        try:
            container = self.docker_service.client.containers.get(self.container_name)
            container.start()
            return {"success": True, "message": "vLLM container started"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
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
        allowed_files = ["env.hardware", "env.moe-fp8", "env.dense", "env.active"]
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
        editable_files = ["env.hardware", "env.moe-fp8", "env.dense"]
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
    
    def _detect_model_type(self, config: Dict[str, Any]) -> str:
        """Detect the model type from config"""
        model = config.get("model", "").lower()
        
        # FP8 MoE models
        if "fp8" in model and ("moe" in model or "a3b" in model or "coder" in model):
            return "moe_fp8"
        
        # Check for MoE indicators
        if "a3b" in model or "moe" in model:
            return "moe_fp8"  # Assume FP8 for MoE by default
        
        # Dense models
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
    
    def _write_env_file(self, model_type: str) -> None:
        """Write the active environment file by combining hardware + model-type env files"""
        # Read from actual env files instead of hardcoded values
        hardware_env = self._read_env_file("env.hardware")
        
        # Select the appropriate model-type env file
        model_type_filename = f"env.{model_type.replace('_', '-')}"  # e.g., "env.moe-fp8" or "env.dense"
        model_type_env = self._read_env_file(model_type_filename)
        
        lines = [
            "# Active vLLM environment configuration",
            "# Managed by vllm-dashboard - DO NOT EDIT MANUALLY",
            f"# Generated from: env.hardware + {model_type_filename}",
            "",
            "# Hardware-specific settings (from env.hardware)",
        ]
        
        for key, value in hardware_env.items():
            lines.append(f"{key}={value}")
        
        if model_type_env:
            lines.append("")
            lines.append(f"# Model-specific settings (from {model_type_filename})")
            for key, value in model_type_env.items():
                lines.append(f"{key}={value}")
        else:
            lines.append("")
            lines.append(f"# Model type: {model_type} (no additional env vars)")
        
        with open(self.active_env_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
    
    def _restart_vllm_container(self) -> Dict[str, Any]:
        """Restart the vLLM and proxy containers using docker compose"""
        import subprocess
        
        try:
            # Use docker compose to recreate both vllm and vllm-proxy
            # This ensures proxy is always running (required for external access)
            result = subprocess.run(
                ["docker", "compose", "up", "-d", "--force-recreate", "vllm", "vllm-proxy"],
                cwd=self.compose_path,
                capture_output=True,
                text=True,
                timeout=120,
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
