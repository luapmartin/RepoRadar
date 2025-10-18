"""
Repository monitor for RepoRadar.

This module provides the RepositoryMonitor class for managing and tracking
git repositories. It includes:

- Repository state persistence (JSON-based storage)
- Repository status tracking and updates
- Scan history management
- Repository filtering and retrieval

The monitor maintains two data files:
- repositories.json: Monitored repositories and their current status
- scan_history.json: History of directory scans performed

All data is stored in src/data/ directory and automatically created as needed.
"""

import os
import json
import datetime
from typing import Dict, List, Optional, Literal

from src.git_utils import get_repo_info, get_repo_status

# Repository status types
RepoStatusType = Literal["monitored", "unmonitored"]


class RepositoryMonitor:
    """
    Monitor git repositories and track their state
    """

    def __init__(self, data_file: str = "src/data/repositories.json", scan_history_file: str = "src/data/scan_history.json"):
        """
        Initialize the repository monitor

        Args:
            data_file: Path to the data file
            scan_history_file: Path to the scan history file
        """
        self.data_file = data_file
        self.scan_history_file = scan_history_file
        self.repositories = self._load_repositories()
        self.scan_history = self._load_scan_history()

    def _load_repositories(self) -> Dict[str, Dict]:
        """
        Load repositories from the data file

        Returns:
            Dictionary of repositories
        """
        if not os.path.exists(self.data_file):
            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            return {}

        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _load_scan_history(self) -> List[Dict]:
        """
        Load scan history from the scan history file

        Returns:
            List of scan history entries
        """
        if not os.path.exists(self.scan_history_file):
            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(self.scan_history_file), exist_ok=True)
            return []

        try:
            with open(self.scan_history_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_repositories(self):
        """
        Save repositories to the data file
        """
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)

        with open(self.data_file, 'w') as f:
            json.dump(self.repositories, f, indent=2)

    def _save_scan_history(self):
        """
        Save scan history to the scan history file
        """
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(self.scan_history_file), exist_ok=True)

        with open(self.scan_history_file, 'w') as f:
            json.dump(self.scan_history, f, indent=2)

    def add_repository(self, repo_path: str, status: RepoStatusType = "monitored") -> bool:
        """
        Add a repository to the monitor

        Args:
            repo_path: Path to the repository
            status: Repository status (monitored, unmonitored, or skipped)

        Returns:
            True if the repository was added, False otherwise
        """
        repo_path = os.path.abspath(repo_path)

        # Check if the repository is already in the list
        if repo_path in self.repositories:
            # Update the status if it's different
            if self.repositories[repo_path].get("status") != status:
                self.repositories[repo_path]["status"] = status
                self._save_repositories()
            return True

        # Get repository information
        repo_info = get_repo_info(repo_path)

        # Check if there was an error
        if "error" in repo_info:
            return False

        # Add status and last check date
        repo_info["status"] = status
        repo_info["last_check"] = datetime.datetime.now().isoformat()

        # Add the repository
        self.repositories[repo_path] = repo_info
        self._save_repositories()

        return True

    def remove_repository(self, repo_path: str) -> bool:
        """
        Remove a repository from the monitor

        Args:
            repo_path: Path to the repository

        Returns:
            True if the repository was removed, False otherwise
        """
        repo_path = os.path.abspath(repo_path)

        # Check if the repository is monitored
        if repo_path not in self.repositories:
            return False

        # Remove the repository
        del self.repositories[repo_path]
        self._save_repositories()

        return True

    def update_repository(self, repo_path: str) -> bool:
        """
        Update repository information

        Args:
            repo_path: Path to the repository

        Returns:
            True if the repository was updated, False otherwise
        """
        repo_path = os.path.abspath(repo_path)

        # Check if the repository is in the list
        if repo_path not in self.repositories:
            return False

        # Skip repositories with status "unmonitored"
        if self.repositories[repo_path].get("status") == "unmonitored":
            return True

        # Get repository information
        repo_info = get_repo_info(repo_path)

        # Check if there was an error
        if "error" in repo_info:
            return False

        # Preserve the status and update the last check date
        repo_info["status"] = self.repositories[repo_path].get("status", "monitored")
        repo_info["last_check"] = datetime.datetime.now().isoformat()

        # Update the repository
        self.repositories[repo_path] = repo_info
        self._save_repositories()

        return True

    def update_all_repositories(self):
        """
        Update information for all repositories
        """
        for repo_path in list(self.repositories.keys()):
            # Check if the repository still exists
            if not os.path.exists(repo_path):
                del self.repositories[repo_path]
                continue

            # Skip repositories with status "unmonitored"
            if self.repositories[repo_path].get("status") == "unmonitored":
                continue

            # Update repository information
            repo_info = get_repo_info(repo_path)

            # Preserve the status and update the last check date
            repo_info["status"] = self.repositories[repo_path].get("status", "monitored")
            repo_info["last_check"] = datetime.datetime.now().isoformat()

            self.repositories[repo_path] = repo_info

        self._save_repositories()

    def get_repository(self, repo_path: str) -> Optional[Dict]:
        """
        Get information about a repository

        Args:
            repo_path: Path to the repository

        Returns:
            Repository information or None if not found
        """
        repo_path = os.path.abspath(repo_path)
        return self.repositories.get(repo_path)

    def get_all_repositories(self) -> List[Dict]:
        """
        Get information about all repositories

        Returns:
            List of repository information
        """
        return list(self.repositories.values())

    def set_repository_status(self, repo_path: str, status: RepoStatusType) -> bool:
        """
        Set the status of a repository

        Args:
            repo_path: Path to the repository
            status: New status (monitored, unmonitored, or skipped)

        Returns:
            True if the status was set, False otherwise
        """
        repo_path = os.path.abspath(repo_path)

        # Check if the repository is in the list
        if repo_path not in self.repositories:
            return False

        # Set the status
        self.repositories[repo_path]["status"] = status
        self._save_repositories()

        return True

    def add_repositories(self, repo_paths: List[str], scan_dir: str = "", status: RepoStatusType = "monitored") -> int:
        """
        Add multiple repositories to the monitor

        Args:
            repo_paths: List of repository paths
            scan_dir: Directory that was scanned (for history)
            status: Repository status (monitored, unmonitored, or skipped)

        Returns:
            Number of repositories added
        """
        added = 0

        for repo_path in repo_paths:
            if self.add_repository(repo_path, status):
                added += 1

        # Record scan history if repositories were found
        if repo_paths and scan_dir:
            scan_entry = {
                "scan_dir": scan_dir,
                "scan_date": datetime.datetime.now().isoformat(),
                "repos_found": len(repo_paths),
                "repos_added": added
            }
            self.scan_history.append(scan_entry)
            self._save_scan_history()

        return added

    def get_scan_history(self) -> List[Dict]:
        """
        Get the scan history

        Returns:
            List of scan history entries
        """
        return self.scan_history

    def rescan_directory(self, scan_dir: str, max_depth: int = 5) -> Dict:
        """
        Rescan a directory that was previously scanned

        Args:
            scan_dir: Directory to rescan
            max_depth: Maximum depth to scan

        Returns:
            Dictionary with scan results
        """
        from src.scanner import scan_directory

        # Scan for repositories
        repo_paths = scan_directory(scan_dir, max_depth)

        # Add repositories
        added = self.add_repositories(repo_paths, scan_dir)

        return {
            "scan_dir": scan_dir,
            "repos_found": len(repo_paths),
            "repos_added": added
        }
