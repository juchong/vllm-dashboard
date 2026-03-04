"""
Configuration service for model configurations.
Manages saving/loading per-model vLLM config YAML files.
"""

from typing import Dict, Any, List, Optional
import os
import re
import json
import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def sanitize_config_filename(model_name: str) -> str:
    """Convert a model name (e.g. 'Qwen/Qwen3-Coder-30B') to a safe filename."""
    return re.sub(r'[<>:"/\\|?*]', '--', model_name)


class ConfigService:
    def __init__(self):
        self.config_dir = os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")

    def save_config(self, model_name: str, config: Dict[str, Any]) -> str:
        """Save configuration for a model. Returns the config file path."""
        safe_name = sanitize_config_filename(model_name)
        config_path = os.path.join(self.config_dir, f"{safe_name}.yaml")

        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return config_path

    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """Get configuration for a specific model by scanning config files."""
        # Try exact filename match first
        safe_name = sanitize_config_filename(model_name)
        exact_path = os.path.join(self.config_dir, f"{safe_name}.yaml")
        if os.path.exists(exact_path):
            try:
                with open(exact_path, 'r') as f:
                    config = yaml.safe_load(f)
                return {"config": config, "config_path": exact_path}
            except (yaml.YAMLError, IOError, OSError):
                pass

        # Search config files by model name in their content
        for filename in os.listdir(self.config_dir):
            if not filename.endswith('.yaml') or filename in ('active.yaml',):
                continue
            config_path = os.path.join(self.config_dir, filename)
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                if not config:
                    continue

                config_model = config.get('model', '')
                served_name = config.get('served_model_name', '')

                if (model_name == config_model or
                    model_name == served_name or
                    model_name.lower() in config_model.lower() or
                    config_model.lower() in model_name.lower()):
                    return {"config": config, "config_path": config_path}
            except (yaml.YAMLError, IOError, OSError):
                continue

        return {"config": None, "config_path": exact_path}

    def get_config_templates(self) -> List[Dict[str, Any]]:
        """Return available configuration templates."""
        return [
            {"name": "dense", "description": "Standard dense model"},
            {"name": "moe_fp8", "description": "MoE model with FP8"},
            {"name": "moe_fp4", "description": "MoE model with FP4"},
        ]

    def associate_config(self, model_name: str, config_path: str) -> str:
        """Associate a model with a configuration file. Validates config_path is within config_dir."""
        raw = config_path.strip()
        if not raw:
            raise ValueError("Config path cannot be empty")
        config_path = os.path.normpath(raw)
        if not os.path.isabs(config_path):
            config_path = os.path.join(self.config_dir, config_path)
        real_config_dir = os.path.realpath(self.config_dir)
        try:
            real_path = os.path.realpath(config_path)
        except OSError:
            raise ValueError(f"Config path does not exist: {config_path}")
        if not os.path.exists(real_path):
            raise ValueError(f"Config path does not exist: {config_path}")
        if not real_path.startswith(real_config_dir):
            raise ValueError(f"Config path must be within {self.config_dir}")
        if not os.path.isfile(real_path) or not real_path.endswith((".yaml", ".yml")):
            raise ValueError("Config path must be a YAML file")
        # Update the config file's model field to associate with model_name
        try:
            with open(real_path, "r") as f:
                config = yaml.safe_load(f)
            if not config:
                config = {}
            config["model"] = model_name
            short_name = model_name.split("/")[-1] if "/" in model_name else model_name
            config["served_model_name"] = config.get("served_model_name", short_name)
            with open(real_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        except (yaml.YAMLError, IOError, OSError) as e:
            raise ValueError(f"Failed to update config: {e}")
        return f"Associated {model_name} with {config_path}"

    def list_config_pairs(self) -> List[Dict[str, str]]:
        """List all configs with their model names by scanning YAML files."""
        pairs = []
        for filename in os.listdir(self.config_dir):
            if not filename.endswith('.yaml') or filename in ('active.yaml',):
                continue
            config_path = os.path.join(self.config_dir, filename)
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                if config and 'model' in config:
                    pairs.append({
                        "model_name": config.get('served_model_name', config.get('model', filename)),
                        "config_path": config_path,
                    })
            except (yaml.YAMLError, IOError, OSError):
                continue
        return pairs

    def generate_config_for_model(self, model_name: str, model_dir: str) -> Optional[str]:
        """Auto-generate a vLLM config YAML for a newly downloaded model.
        Returns the config file path, or None if generation fails."""
        safe_name = sanitize_config_filename(model_name)
        config_path = os.path.join(self.config_dir, f"{safe_name}.yaml")

        if os.path.exists(config_path):
            logger.info(f"Config already exists for {model_name}, skipping auto-generation")
            return config_path

        config_json_path = os.path.join(model_dir, "config.json")
        arch = ""
        num_experts = 0
        model_type_hint = ""

        if os.path.exists(config_json_path):
            try:
                with open(config_json_path, 'r') as f:
                    model_config = json.load(f)
                architectures = model_config.get("architectures", [])
                arch = architectures[0] if architectures else ""
                num_experts = model_config.get("num_local_experts", 0) or model_config.get("num_experts", 0)
                model_type_hint = model_config.get("model_type", "")
            except (json.JSONDecodeError, IOError):
                pass

        name_lower = model_name.lower()
        is_moe = num_experts > 0 or "moe" in name_lower or "a3b" in name_lower
        is_fp8 = "fp8" in name_lower
        is_fp4 = "fp4" in name_lower or "nvfp4" in name_lower
        is_awq = "awq" in name_lower
        is_gptq = "gptq" in name_lower
        is_quantized = is_fp8 or is_fp4 or is_awq or is_gptq

        if is_moe and is_fp4:
            model_type = "moe_fp4"
        elif is_moe:
            model_type = "moe_fp8"
        else:
            model_type = "dense"

        short_name = model_name.split('/')[-1] if '/' in model_name else model_name

        config: Dict[str, Any] = {
            "model": model_name,
            "model_type": model_type,
            "served_model_name": short_name,
            "host": "0.0.0.0",
            "port": 8000,
            "download_dir": "/root/.cache/huggingface",
            "dtype": "auto" if is_quantized else "bfloat16",
            "tensor_parallel_size": 2,
            "gpu_memory_utilization": 0.90,
            "max_num_seqs": 16,
            "max_num_batched_tokens": 16384,
            "swap_space": 8,
            "enable_chunked_prefill": True,
            "enable_prefix_caching": True,
            "trust_remote_code": True,
        }

        if is_moe:
            config["enable_expert_parallel"] = True

        if "mistral" in arch.lower() or "mistral" in name_lower:
            config["tool_call_parser"] = "mistral"
            config["enable_auto_tool_choice"] = True
        elif "qwen" in name_lower and "coder" in name_lower:
            config["tool_call_parser"] = "qwen3_coder"
            config["enable_auto_tool_choice"] = True
        elif "hermes" in name_lower or "nous" in name_lower:
            config["tool_call_parser"] = "hermes"
            config["enable_auto_tool_choice"] = True

        try:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Auto-generated config for {model_name} at {config_path} (type={model_type})")
            return config_path
        except Exception as e:
            logger.error(f"Failed to auto-generate config for {model_name}: {e}")
            return None
