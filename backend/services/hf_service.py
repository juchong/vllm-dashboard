"""
Hugging Face service for model management
"""

import json
import shutil

from huggingface_hub import HfApi, list_repo_refs
from typing import Dict, Any, List, Optional
import os
import logging

from utils import ensure_within_dir, format_size

logger = logging.getLogger(__name__)


def derive_model_type(
    num_experts: int,
    quant_method: str | None,
    weights_type: str | None = None,
    weights_bits: int | None = None,
) -> str:
    """Derive dashboard model_type from HuggingFace config.json fields.
    
    Classifications:
    - dense_full: Dense, full precision (FP16/BF16)
    - dense_fp8: Dense, FP8 quantized
    - dense_int8: Dense, INT8 quantized
    - dense_int4: Dense, INT4/AWQ quantized
    - moe_full: MoE, full precision
    - moe_fp8: MoE, FP8 quantized
    - moe_fp4: MoE, FP4 quantized
    """
    is_moe = num_experts > 0
    qm = (quant_method or "").lower()
    
    # Detect quantization type
    is_fp8 = "fp8" in qm
    is_fp4 = "fp4" in qm or "modelopt" in qm or "nvfp4" in qm
    is_int4 = weights_type == "int" and weights_bits == 4
    is_int8 = weights_type == "int" and weights_bits == 8
    
    # Also check for FP8 in compressed-tensors with float type
    if weights_type == "float" and weights_bits == 8:
        is_fp8 = True
    
    if is_moe:
        if is_fp4:
            return "moe_fp4"
        elif is_fp8:
            return "moe_fp8"
        else:
            return "moe_full"
    else:
        if is_fp8:
            return "dense_fp8"
        elif is_int4:
            return "dense_int4"
        elif is_int8:
            return "dense_int8"
        else:
            return "dense_full"


class HuggingFaceService:
    def __init__(self, config_service=None):
        self.api = HfApi()
        self.models_dir = os.environ.get("VLLM_MODELS_DIR", "/models")
        self.config_service = config_service
        
        # Files that indicate a valid HuggingFace model directory
        self.model_indicators = [
            "config.json",
            "model.safetensors",
            "model.safetensors.index.json",
            "pytorch_model.bin",
            "pytorch_model.bin.index.json",
            "model-00001-of-",
            "tokenizer.json",
            "tokenizer_config.json",
            # Mistral models use "consolidated" naming
            "consolidated.safetensors",
            "consolidated.safetensors.index.json",
            "consolidated-00001-of-",
            # Also catch params.json used by some models
            "params.json",
        ]
    
    def get_model_revisions(self, model_name: str) -> Dict[str, Any]:
        """Get available revisions (branches and tags) for a model"""
        try:
            refs = list_repo_refs(model_name)
            
            branches = [branch.name for branch in refs.branches] if refs.branches else []
            tags = [tag.name for tag in refs.tags] if refs.tags else []
            
            return {
                "branches": branches,
                "tags": tags,
                "default": "main" if "main" in branches else (branches[0] if branches else None)
            }
        except Exception as e:
            logger.warning(f"Failed to get revisions for {model_name}: {e}")
            return {"branches": ["main"], "tags": [], "default": "main"}

    def validate_model_name(self, model_name: str) -> Dict[str, Any]:
        """Validate a model name exists on HuggingFace"""
        try:
            model_info = self.api.model_info(model_name)
            return {
                "valid": True,
                "model_id": model_info.modelId,
                "private": model_info.private,
                "downloads": model_info.downloads,
                "likes": model_info.likes,
                "pipeline_tag": model_info.pipeline_tag
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _is_valid_model_dir(self, path: str) -> bool:
        """Check if a directory contains a valid HuggingFace model"""
        try:
            for item in os.scandir(path):
                # Follow symlinks when checking if file exists
                if item.is_file(follow_symlinks=True):
                    name = item.name.lower()
                    for indicator in self.model_indicators:
                        if indicator in name:
                            return True
            return False
        except Exception:
            return False
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all downloaded models (only valid model directories)"""
        models = []
        
        try:
            if not os.path.exists(self.models_dir):
                return models
            
            # Recursively find model directories (handles org/model structure)
            self._scan_for_models(self.models_dir, models, depth=0, max_depth=3)
            
            # Deduplicate by name, keeping the largest version (actual model vs metadata)
            model_map: Dict[str, Dict[str, Any]] = {}
            for model in models:
                name = model["name"]
                if name not in model_map or model["size"] > model_map[name]["size"]:
                    model_map[name] = model
            
            models = list(model_map.values())
            
            # Filter out very small entries (likely just metadata, < 100MB)
            models = [m for m in models if m["size"] > 100 * 1024 * 1024]  # > 100MB
            
            # Sort by name
            models.sort(key=lambda x: x["name"].lower())
            
        except Exception as e:
            raise Exception(f"Failed to list models: {str(e)}")
        
        return models

    def _parse_hf_cache_name(self, dir_name: str) -> Optional[str]:
        """Parse HuggingFace cache directory name to get model ID"""
        # HF cache format: models--org--model-name
        if dir_name.startswith('models--'):
            parts = dir_name[8:].split('--')  # Remove 'models--' prefix
            if len(parts) >= 2:
                return '/'.join(parts)
        return None

    def _scan_for_models(self, path: str, models: List, depth: int, max_depth: int):
        """Recursively scan for model directories"""
        try:
            for item in os.scandir(path):
                if not item.is_dir():
                    continue
                    
                # Skip hidden directories
                if item.name.startswith('.'):
                    continue
                
                model_path = item.path
                
                # Check if this is a HuggingFace cache directory
                hf_model_name = self._parse_hf_cache_name(item.name)
                if hf_model_name:
                    # Look for snapshots directory
                    snapshots_dir = os.path.join(model_path, 'snapshots')
                    if os.path.isdir(snapshots_dir):
                        # Find the latest snapshot
                        snapshot_dirs = [d for d in os.scandir(snapshots_dir) if d.is_dir()]
                        if snapshot_dirs:
                            # Use the first snapshot (they're usually just one)
                            snapshot_path = snapshot_dirs[0].path
                            if self._is_valid_model_dir(snapshot_path):
                                size = self._get_directory_size(snapshot_path)
                                models.append({
                                    "name": hf_model_name,
                                    "path": snapshot_path,
                                    "size": size,
                                    "size_human": format_size(size),
                                    "is_valid": True
                                })
                                continue
                
                # Check if this is a direct model directory (not HF cache)
                is_valid = self._is_valid_model_dir(model_path)
                
                if is_valid:
                    # This is a model directory
                    size = self._get_directory_size(model_path)
                    rel_path = os.path.relpath(model_path, self.models_dir)
                    
                    models.append({
                        "name": rel_path,
                        "path": model_path,
                        "size": size,
                        "size_human": format_size(size),
                        "is_valid": True
                    })
                elif depth < max_depth:
                    # Not a model, but might contain models (e.g., org folder)
                    self._scan_for_models(model_path, models, depth + 1, max_depth)
        except PermissionError:
            pass
    
    def resolve_model_dir(self, model_name: str) -> Optional[str]:
        """Resolve a HuggingFace model name to its on-disk directory containing config.json.
        Tries direct layout, hub/ cache, and top-level cache entries."""
        if not model_name:
            return None

        candidates = [
            os.path.join(self.models_dir, model_name),
        ]

        cache_name = "models--" + model_name.replace("/", "--")
        hub_cache = os.path.join(self.models_dir, "hub", cache_name, "snapshots")
        top_cache = os.path.join(self.models_dir, cache_name, "snapshots")
        for snapshots_dir in (hub_cache, top_cache):
            if os.path.isdir(snapshots_dir):
                try:
                    snapshot_dirs = sorted(os.scandir(snapshots_dir), key=lambda d: d.name, reverse=True)
                    for d in snapshot_dirs:
                        if d.is_dir():
                            candidates.append(d.path)
                except OSError:
                    pass

        for path in candidates:
            if os.path.isfile(os.path.join(path, "config.json")):
                return path
        return None

    def read_model_metadata(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Read structured metadata from a model's config.json.
        Returns dict with num_experts, quant_method, architecture, hf_model_type."""
        model_dir = self.resolve_model_dir(model_name)
        if not model_dir:
            return None
        return self._read_config_json(os.path.join(model_dir, "config.json"))

    @staticmethod
    def _read_config_json(config_json_path: str) -> Optional[Dict[str, Any]]:
        """Parse a config.json and extract model metadata."""
        try:
            with open(config_json_path, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError, OSError):
            return None

        architectures = data.get("architectures", [])
        num_experts = data.get("num_local_experts", 0) or data.get("num_experts", 0) or 0
        quant_cfg = data.get("quantization_config") or {}
        quant_method = quant_cfg.get("quant_method") if quant_cfg else None
        
        # Extract weights type and bits from quantization config
        # Handle compressed-tensors format (config_groups) and standard format
        weights_type = None
        weights_bits = None
        
        if quant_cfg:
            # Standard format: bits at top level
            weights_bits = quant_cfg.get("bits")
            
            # compressed-tensors format: config_groups -> group_X -> weights
            config_groups = quant_cfg.get("config_groups", {})
            for group_cfg in config_groups.values():
                w = group_cfg.get("weights", {})
                if isinstance(w, dict):
                    weights_type = w.get("type")
                    weights_bits = w.get("num_bits") or weights_bits
                    break  # Use first group

        return {
            "num_experts": num_experts,
            "quant_method": quant_method,
            "architecture": architectures[0] if architectures else "",
            "hf_model_type": data.get("model_type", ""),
            "weights_type": weights_type,
            "weights_bits": weights_bits,
        }

    def _cleanup_related_paths(self, model_name: str, deleted_path: str) -> List[str]:
        """Remove HF cache dirs and duplicate layouts related to a model name."""
        cleaned = []
        if not model_name:
            return cleaned

        cache_name = "models--" + model_name.replace("/", "--")
        related = [
            os.path.join(self.models_dir, "hub", cache_name),
            os.path.join(self.models_dir, cache_name),
            os.path.join(self.models_dir, model_name),
        ]
        for path in related:
            real = os.path.realpath(path)
            if real == os.path.realpath(deleted_path):
                continue
            if os.path.isdir(real):
                try:
                    ensure_within_dir(self.models_dir, real)
                    shutil.rmtree(real)
                    cleaned.append(real)
                    logger.info(f"Cleaned up related path: {real}")
                except (ValueError, OSError) as e:
                    logger.warning(f"Failed to clean related path {real}: {e}")
        return cleaned

    def _cleanup_config_yamls(self, model_name: str) -> List[str]:
        """Remove config YAMLs that reference the deleted model."""
        cleaned = []
        if not self.config_service:
            return cleaned

        import yaml
        config_dir = self.config_service.config_dir
        try:
            for filename in os.listdir(config_dir):
                if not filename.endswith('.yaml') or filename == 'active.yaml':
                    continue
                filepath = os.path.join(config_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        cfg = yaml.safe_load(f)
                    if cfg and cfg.get('model') == model_name:
                        os.remove(filepath)
                        cleaned.append(filename)
                        logger.info(f"Removed orphaned config: {filename}")
                except (yaml.YAMLError, IOError, OSError):
                    continue
        except OSError:
            pass
        return cleaned

    def delete_model(self, model_path: str) -> str:
        """Delete a model and clean up related cache dirs and config YAMLs."""
        import time
        start_time = time.time()
        
        if not model_path.startswith('/'):
            model_path = '/' + model_path

        if not os.path.exists(model_path):
            raise Exception(f"Model path {model_path} does not exist")

        real_path = ensure_within_dir(self.models_dir, model_path)

        rel = os.path.relpath(real_path, self.models_dir)
        hf_name = self._parse_hf_cache_name(rel.split(os.sep)[0])
        if not hf_name:
            hf_name = rel.split("/snapshots/")[0] if "/snapshots/" in rel else rel

        # Get size before deletion for logging
        try:
            size = self._get_directory_size(real_path)
            size_str = format_size(size)
        except Exception:
            size_str = "unknown size"
        
        logger.info(f"Starting deletion of {real_path} ({size_str})")
        shutil.rmtree(real_path)
        elapsed = time.time() - start_time
        logger.info(f"Deleted model at {real_path} ({size_str}) in {elapsed:.1f}s")

        cleaned_paths = self._cleanup_related_paths(hf_name, real_path)
        cleaned_configs = self._cleanup_config_yamls(hf_name)
        
        if cleaned_paths:
            logger.info(f"Cleaned up {len(cleaned_paths)} related paths")
        if cleaned_configs:
            logger.info(f"Cleaned up {len(cleaned_configs)} config files: {cleaned_configs}")

        return f"Model at {model_path} deleted successfully"
    
    def rename_model(self, old_path: str, new_path: str) -> str:
        """Rename a model directory."""
        if not old_path.startswith('/'):
            old_path = '/' + old_path
        if not new_path.startswith('/'):
            new_path = '/' + new_path

        if not os.path.exists(old_path):
            raise Exception(f"Model path {old_path} does not exist")

        real_old = ensure_within_dir(self.models_dir, old_path)
        real_new = ensure_within_dir(self.models_dir, new_path)

        new_parent = os.path.dirname(real_new)
        os.makedirs(new_parent, exist_ok=True)
        os.rename(real_old, real_new)

        return f"Model renamed from {old_path} to {new_path}"
    
    def _get_directory_size(self, path: str) -> int:
        """Get size of directory in bytes (follows symlinks)"""
        total = 0
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        # Follow symlinks to get actual file size
                        if entry.is_file(follow_symlinks=True):
                            total += entry.stat(follow_symlinks=True).st_size
                        elif entry.is_dir(follow_symlinks=True):
                            total += self._get_directory_size(entry.path)
                    except (OSError, FileNotFoundError):
                        # Skip broken symlinks
                        continue
        except PermissionError:
            pass
        return total
