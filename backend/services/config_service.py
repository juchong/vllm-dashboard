"""
Configuration service for model configurations
"""

from typing import Dict, Any, List, Optional
import os
import yaml
from pathlib import Path


class ConfigService:
    def __init__(self):
        self.config_dir = os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs")
        self.templates_dir = os.path.join(self.config_dir, "templates")
        self.pairs_file = os.path.join(self.config_dir, "model_config_pairs.yaml")
        
        # Ensure directories exist
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Load or initialize pairs
        self.config_pairs = self._load_config_pairs()
    
    def get_config_templates(self) -> List[str]:
        """Get available configuration templates"""
        templates = []
        
        if os.path.exists(self.templates_dir):
            for item in os.listdir(self.templates_dir):
                if item.endswith('.yaml') or item.endswith('.yml'):
                    templates.append(item)
        
        return templates
    
    def save_config(self, model_name: str, config: Dict[str, Any]) -> str:
        """Save configuration for a model"""
        config_path = os.path.join(self.config_dir, f"{model_name}.yaml")
        
        try:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            # Update config pairs
            self.config_pairs[model_name] = config_path
            self._save_config_pairs()
            
            return f"Configuration saved to {config_path}"
        except Exception as e:
            raise Exception(f"Failed to save configuration: {str(e)}")
    
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """Get configuration for a specific model. Returns dict with 'config' and 'config_path' keys."""
        # Check if model has an associated config
        if model_name in self.config_pairs:
            config_path = self.config_pairs[model_name]
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    return {"config": config, "config_path": config_path}
                except Exception as e:
                    raise Exception(f"Failed to load configuration: {str(e)}")
        
        # Search config files by model name in their content
        for filename in os.listdir(self.config_dir):
            if filename.endswith('.yaml') and filename not in ['active.yaml', 'model_config_pairs.yaml']:
                config_path = os.path.join(self.config_dir, filename)
                try:
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    # Check if this config matches the model
                    config_model = config.get('model', '')
                    served_name = config.get('served_model_name', '')
                    
                    # Match by full model path or served name
                    if (model_name == config_model or 
                        model_name == served_name or
                        model_name.lower() in config_model.lower() or
                        config_model.lower() in model_name.lower()):
                        return {"config": config, "config_path": config_path}
                except:
                    continue
        
        # No config found - return expected path for new config
        expected_path = os.path.join(self.config_dir, f"{model_name}.yaml")
        return {"config": None, "config_path": expected_path}
    
    def associate_config(self, model_name: str, config_path: str) -> str:
        """Associate a model with a configuration file"""
        if not os.path.exists(config_path):
            raise Exception(f"Config file {config_path} does not exist")
        
        self.config_pairs[model_name] = config_path
        self._save_config_pairs()
        
        return f"Model {model_name} associated with config {config_path}"
    
    def list_config_pairs(self) -> List[Dict[str, str]]:
        """List all model+configuration pairs"""
        pairs = []
        
        for model_name, config_path in self.config_pairs.items():
            pairs.append({
                "model_name": model_name,
                "config_path": config_path
            })
        
        return pairs
    
    def _load_config_pairs(self) -> Dict[str, str]:
        """Load config pairs from file"""
        if not os.path.exists(self.pairs_file):
            return {}
        
        try:
            with open(self.pairs_file, 'r') as f:
                pairs = yaml.safe_load(f) or {}
            return pairs
        except Exception as e:
            raise Exception(f"Failed to load config pairs: {str(e)}")
    
    def _save_config_pairs(self) -> None:
        """Save config pairs to file"""
        try:
            with open(self.pairs_file, 'w') as f:
                yaml.dump(self.config_pairs, f, default_flow_style=False)
        except Exception as e:
            raise Exception(f"Failed to save config pairs: {str(e)}")
