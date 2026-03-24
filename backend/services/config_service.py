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

from utils import ensure_within_dir
from services.instance_registry import atomic_write_yaml

logger = logging.getLogger(__name__)


def sanitize_config_filename(model_name: str) -> str:
    """Convert a model name (e.g. 'Qwen/Qwen3-Coder-30B') to a safe filename."""
    return re.sub(r'[<>:"/\\|?*]', '--', model_name)


class ConfigService:
    def __init__(self, config_dir: str | None = None):
        self.config_dir = config_dir or os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")

    def save_config(self, model_name: str, config: Dict[str, Any]) -> str:
        """Save configuration for a model. Returns the config file path."""
        safe_name = sanitize_config_filename(model_name)
        config_path = os.path.join(self.config_dir, f"{safe_name}.yaml")

        atomic_write_yaml(config_path, config)

        return config_path

    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """Get configuration for a specific model by scanning config files."""
        safe_name = sanitize_config_filename(model_name)
        exact_path = os.path.join(self.config_dir, f"{safe_name}.yaml")
        if os.path.exists(exact_path):
            try:
                with open(exact_path, 'r') as f:
                    config = yaml.safe_load(f)
                return {"config": config, "config_path": exact_path}
            except (yaml.YAMLError, IOError, OSError):
                pass

        for filename in os.listdir(self.config_dir):
            if not filename.endswith('.yaml') or filename in ('active.yaml', 'instances.yaml'):
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
        """Associate a model with a configuration file."""
        raw = config_path.strip()
        if not raw:
            raise ValueError("Config path cannot be empty")
        config_path = os.path.normpath(raw)
        if not os.path.isabs(config_path):
            config_path = os.path.join(self.config_dir, config_path)
        try:
            real_path = ensure_within_dir(self.config_dir, config_path)
        except OSError:
            raise ValueError(f"Config path does not exist: {config_path}")
        if not os.path.exists(real_path):
            raise ValueError(f"Config path does not exist: {config_path}")
        if not os.path.isfile(real_path) or not real_path.endswith((".yaml", ".yml")):
            raise ValueError("Config path must be a YAML file")
        try:
            with open(real_path, "r") as f:
                config = yaml.safe_load(f)
            if not config:
                config = {}
            config["model"] = model_name
            short_name = model_name.split("/")[-1] if "/" in model_name else model_name
            config["served_model_name"] = config.get("served_model_name", short_name)
            atomic_write_yaml(real_path, config)
        except (yaml.YAMLError, IOError, OSError) as e:
            raise ValueError(f"Failed to update config: {e}")
        return f"Associated {model_name} with {config_path}"

    def list_config_pairs(self) -> List[Dict[str, str]]:
        """List all configs with their model names by scanning YAML files."""
        pairs = []
        for filename in os.listdir(self.config_dir):
            if not filename.endswith('.yaml') or filename in ('active.yaml', 'instances.yaml'):
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
        Reads config.json from model_dir for authoritative metadata.
        Returns the config file path, or None if generation fails."""
        from services.hf_service import HuggingFaceService, derive_model_type

        safe_name = sanitize_config_filename(model_name)
        config_path = os.path.join(self.config_dir, f"{safe_name}.yaml")

        if os.path.exists(config_path):
            logger.info(f"Config already exists for {model_name}, skipping auto-generation")
            return config_path

        arch = ""
        num_experts = 0
        quant_method = None

        config_json_path = os.path.join(model_dir, "config.json")
        meta = HuggingFaceService._read_config_json(config_json_path)
        weights_type = None
        weights_bits = None
        if meta:
            arch = meta["architecture"]
            num_experts = meta["num_experts"]
            quant_method = meta["quant_method"]
            weights_type = meta.get("weights_type")
            weights_bits = meta.get("weights_bits")

        model_type = derive_model_type(num_experts, quant_method, weights_type, weights_bits)
        is_moe = num_experts > 0
        is_fp4 = quant_method and "fp4" in quant_method.lower() if quant_method else False
        is_quantized = quant_method is not None

        short_name = model_name.split('/')[-1] if '/' in model_name else model_name

        gpu_count = int(os.environ.get("VLLM_DEFAULT_GPU_COUNT", "1"))
        gpu_ids = os.environ.get("VLLM_DEFAULT_GPU_IDS", ",".join(str(i) for i in range(gpu_count)))

        config: Dict[str, Any] = {
            "model": model_name,
            "model_type": model_type,
            "served_model_name": short_name,
            "host": "0.0.0.0",
            "download_dir": "/root/.cache/huggingface",
            "dtype": "auto" if is_quantized else "bfloat16",
            "tensor_parallel_size": gpu_count,
            "gpu_memory_utilization": 0.90,
            "max_num_seqs": 16,
            "max_num_batched_tokens": 16384,
            "swap_space": 8,
            "enable_chunked_prefill": True,
            "enable_prefix_caching": True,
            "trust_remote_code": True,
        }

        env_vars: Dict[str, str] = {
            "SAFETENSORS_FAST_GPU": "1",
            "CUDA_VISIBLE_DEVICES": gpu_ids,
        }

        if is_moe:
            config["enable_expert_parallel"] = True
            env_vars["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:False"

        if is_moe and is_fp4:
            env_vars["VLLM_USE_FLASHINFER_MOE_FP4"] = "1"
            env_vars["VLLM_USE_FLASHINFER_MOE_FP8"] = "1"

        config["env_vars"] = env_vars

        name_lower = model_name.lower()
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
            atomic_write_yaml(config_path, config)
            logger.info(f"Auto-generated config for {model_name} at {config_path} (type={model_type})")
            return config_path
        except Exception as e:
            logger.error(f"Failed to auto-generate config for {model_name}: {e}")
            return None

    def regenerate_config_for_model(self, model_name: str, model_dir: str) -> Optional[str]:
        """Delete existing config and regenerate from model metadata."""
        safe_name = sanitize_config_filename(model_name)
        config_path = os.path.join(self.config_dir, f"{safe_name}.yaml")
        if os.path.exists(config_path):
            os.remove(config_path)
            logger.info(f"Removed existing config for {model_name} before regeneration")
        return self.generate_config_for_model(model_name, model_dir)
