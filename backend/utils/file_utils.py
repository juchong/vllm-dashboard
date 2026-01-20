"""
File utility functions
"""

import os
from typing import Optional


def ensure_directory_exists(path: str) -> None:
    """Ensure directory exists, create if not"""
    os.makedirs(path, exist_ok=True)


def get_file_size(path: str) -> Optional[int]:
    """Get file size in bytes"""
    if not os.path.exists(path):
        return None
    return os.path.getsize(path)


def get_directory_size(path: str) -> int:
    """Get size of directory in bytes"""
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_directory_size(entry.path)
    return total
