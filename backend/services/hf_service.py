"""
Hugging Face service for model management
"""

from huggingface_hub import HfApi, list_repo_refs
from typing import Dict, Any, List, Optional
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class HuggingFaceService:
    def __init__(self):
        self.api = HfApi()
        self.models_dir = os.environ.get("VLLM_MODELS_DIR", "/models")
        self.config_dir = os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")
        
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
    
    def download_model(
        self,
        model_name: str,
        revision: Optional[str] = None,
        local_dir: Optional[str] = None
    ) -> str:
        """Download a model from Hugging Face Hub"""
        if not local_dir:
            local_dir = os.path.join(self.models_dir, model_name)
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(local_dir, exist_ok=True)
            
            # Download model
            self.api.snapshot_download(
                repo_id=model_name,
                revision=revision,
                local_dir=local_dir,
                local_dir_use_symlinks=False,
                resume_download=True
            )
            
            return f"Model {model_name} downloaded successfully to {local_dir}"
        except Exception as e:
            raise Exception(f"Failed to download model: {str(e)}")

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
                                    "size_human": self._format_size(size),
                                    "is_valid": True
                                })
                                continue
                
                # Check if this is a direct model directory (not HF cache)
                is_valid = self._is_valid_model_dir(model_path)
                
                if is_valid:
                    # This is a model directory
                    size = self._get_directory_size(model_path)
                    
                    # Determine model name (relative to models_dir)
                    rel_path = os.path.relpath(model_path, self.models_dir)
                    
                    models.append({
                        "name": rel_path,
                        "path": model_path,
                        "size": size,
                        "size_human": self._format_size(size),
                        "is_valid": True
                    })
                elif depth < max_depth:
                    # Not a model, but might contain models (e.g., org folder)
                    self._scan_for_models(model_path, models, depth + 1, max_depth)
        except PermissionError:
            pass
    
    def delete_model(self, model_path: str) -> str:
        """Delete a model"""
        try:
            if not os.path.exists(model_path):
                raise Exception(f"Model path {model_path} does not exist")
            
            # Remove directory
            import shutil
            shutil.rmtree(model_path)
            
            return f"Model at {model_path} deleted successfully"
        except Exception as e:
            raise Exception(f"Failed to delete model: {str(e)}")
    
    def rename_model(self, old_path: str, new_path: str) -> str:
        """Rename a model"""
        try:
            if not os.path.exists(old_path):
                raise Exception(f"Model path {old_path} does not exist")
            
            # Rename directory
            os.rename(old_path, new_path)
            
            return f"Model renamed from {old_path} to {new_path}"
        except Exception as e:
            raise Exception(f"Failed to rename model: {str(e)}")
    
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
    
    def _format_size(self, size: int) -> str:
        """Format size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
