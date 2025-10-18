"""
RepoRadar - A tool to monitor git repositories and ensure your work is saved online.

This package provides utilities for scanning, monitoring, and managing git repositories
across multiple directories. It includes:

- git_utils: Core git operations and repository information retrieval
- scanner: Directory scanning to discover git repositories
- monitor: Repository state management and monitoring
- web: Web interface for user interaction

Example:
    Basic usage from command line:

    >>> python main.py scan /path/to/directory
    >>> python main.py list
    >>> python main.py web
"""

__version__ = '0.1.0'
__author__ = 'RepoRadar Contributors'
__license__ = 'MIT'
