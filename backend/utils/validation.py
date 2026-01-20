"""
Validation utility functions
"""

from typing import Dict, Any
import re


def validate_model_name(name: str) -> bool:
    """Validate model name format"""
    # Hugging Face model names follow org/model-name format
    # Allows letters, numbers, underscores, hyphens, and dots
    pattern = r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$'
    return bool(re.match(pattern, name))


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration structure"""
    required_fields = ['model', 'dtype']
    
    for field in required_fields:
        if field not in config:
            return False
    
    return True


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to remove invalid characters"""
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"\/\|\?\*]', '_', filename)
    return sanitized
