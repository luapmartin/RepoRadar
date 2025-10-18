"""
Repository scanner for RepoRadar.

This module provides functionality to recursively scan directories and discover
git repositories. It includes:

- scan_directory: Main function to scan a directory tree for git repositories

The scanner respects maximum depth limits to avoid excessive scanning and
skips hidden directories (starting with '.') for efficiency.
"""

import os
from typing import List

from src.git_utils import is_git_repo


def scan_directory(root_dir: str, max_depth: int = 5) -> List[str]:
    """
    Scan a directory and its subdirectories for git repositories
    
    Args:
        root_dir: Root directory to scan
        max_depth: Maximum depth to scan (to avoid infinite recursion)
        
    Returns:
        List of paths to git repositories
    """
    repos = []
    
    def _scan_dir(current_dir: str, current_depth: int):
        if current_depth > max_depth:
            return
        
        try:
            # Check if the current directory is a git repository
            if is_git_repo(current_dir):
                repos.append(current_dir)
                return  # Don't scan subdirectories of a git repository
            
            # Scan subdirectories
            for item in os.listdir(current_dir):
                item_path = os.path.join(current_dir, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    _scan_dir(item_path, current_depth + 1)
        except (PermissionError, FileNotFoundError):
            # Skip directories we can't access
            pass
    
    _scan_dir(os.path.abspath(root_dir), 0)
    return repos
