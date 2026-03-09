"""Shared utilities for vllm-dashboard backend."""

import os


def ensure_within_dir(base_dir: str, target_path: str) -> str:
    """Verify target_path resolves inside base_dir. Raises ValueError on traversal."""
    real_base = os.path.realpath(base_dir)
    real_target = os.path.realpath(target_path)
    if os.path.commonpath([real_base, real_target]) != real_base:
        raise ValueError(f"Path escapes base directory: {target_path}")
    return real_target


def format_size(size: int) -> str:
    """Format byte count as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"
