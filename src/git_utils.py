"""
Git utility functions for RepoRadar.

This module provides core git operations and repository information retrieval using GitPython.
It includes functions for:

- Checking if a directory is a git repository
- Retrieving detailed repository information (branches, remotes, status)
- Getting human-readable repository status
- Identifying merged branches that can be safely deleted
- Detecting remote providers (GitHub, GitLab, etc.)

All functions handle errors gracefully and return meaningful error information.
"""

import os
import git
import urllib.parse
from typing import Dict, List, Optional, Tuple, Set


def is_git_repo(path: str) -> bool:
    """
    Check if a directory is a git repository

    Args:
        path: Path to check

    Returns:
        True if the directory is a git repository, False otherwise
    """
    try:
        git.Repo(path)
        return True
    except git.exc.InvalidGitRepositoryError:
        return False


def get_repo_info(repo_path: str) -> Dict:
    """
    Get information about a git repository

    Args:
        repo_path: Path to the repository

    Returns:
        Dictionary with repository information
    """
    try:
        repo = git.Repo(repo_path)

        # Get repository name (directory name)
        name = os.path.basename(os.path.abspath(repo_path))

        # Get current branch
        try:
            current_branch = repo.active_branch.name
        except TypeError:
            # Detached HEAD state
            current_branch = "DETACHED HEAD"

        # Check for uncommitted changes
        has_uncommitted_changes = repo.is_dirty()

        # Get all branches and check for unpushed changes
        branches_info = []
        unpushed_changes = False

        for branch in repo.branches:
            branch_info = {
                "name": branch.name,
                "has_origin": False,
                "unpushed_commits": 0
            }

            # Check if branch has remote counterpart
            try:
                remote_branch = repo.remote().refs[branch.name]
                branch_info["has_origin"] = True

                # Check for unpushed commits
                commits_behind = sum(1 for _ in repo.iter_commits(f"{remote_branch.name}..{branch.name}"))
                branch_info["unpushed_commits"] = commits_behind

                if commits_behind > 0:
                    unpushed_changes = True
            except (IndexError, ValueError):
                # Branch doesn't have a remote counterpart
                pass

            branches_info.append(branch_info)

        # Check if any branch doesn't have an origin
        branches_without_origin = any(not b["has_origin"] for b in branches_info)

        # Get merged branches that can be deleted
        merged_branches = get_merged_branches(repo_path)
        has_merged_branches = len(merged_branches) > 0

        # Add merged status to branch info
        for branch_info in branches_info:
            branch_info["can_be_deleted"] = branch_info["name"] in merged_branches

        # Get remote information and detect provider
        # This helps identify where repositories are hosted (GitHub, GitLab, etc.)
        remotes_info = []
        remote_provider_summary = "None"
        if repo.remotes:
            providers = set()
            for remote in repo.remotes:
                try:
                    url = remote.url
                    parsed_url = urllib.parse.urlparse(url)
                    hostname = parsed_url.hostname
                    provider = "Other"

                    # Detect the git hosting provider based on hostname
                    if hostname:
                        hostname_lower = hostname.lower()
                        if 'github.com' in hostname_lower:
                            provider = "GitHub"
                        elif 'gitlab.com' in hostname_lower or 'gitlab.' in hostname_lower:
                            provider = "GitLab"
                        elif 'bitbucket.org' in hostname_lower or 'bitbucket.' in hostname_lower:
                            provider = "Bitbucket"
                        elif 'azure.com' in hostname_lower or 'visualstudio.com' in hostname_lower or 'dev.azure.com' in hostname_lower:
                            provider = "Azure DevOps"
                        elif 'codeberg.org' in hostname_lower:
                            provider = "Codeberg"
                        elif 'sourceforge.net' in hostname_lower:
                            provider = "SourceForge"

                    remotes_info.append({
                        "name": remote.name,
                        "url": url,
                        "provider": provider
                    })
                    providers.add(provider)
                except Exception:
                    # Handle cases where URL might be invalid or inaccessible
                    remotes_info.append({
                        "name": remote.name,
                        "url": "N/A",
                        "provider": "Error"
                    })
                    providers.add("Error")

            # Summarize providers: single provider, multiple, or none
            if len(providers) == 1:
                remote_provider_summary = providers.pop()
            elif len(providers) > 1:
                remote_provider_summary = "Multiple"
            elif not providers:
                # Defensive check: shouldn't happen if repo.remotes is not empty
                remote_provider_summary = "None"


        return {
            "name": name,
            "path": repo_path,
            "remote_provider_summary": remote_provider_summary,
            "remotes_info": remotes_info,
            "current_branch": current_branch,
            "has_uncommitted_changes": has_uncommitted_changes,
            "has_unpushed_changes": unpushed_changes,
            "branches_without_origin": branches_without_origin,
            "has_merged_branches": has_merged_branches,
            "merged_branches": merged_branches,
            "branches": branches_info
        }
    except Exception as e:
        return {
            "name": os.path.basename(os.path.abspath(repo_path)),
            "path": repo_path,
            "error": str(e)
        }


def get_repo_status(repo_path: str) -> str:
    """
    Get a human-readable status of a repository

    Args:
        repo_path: Path to the repository

    Returns:
        Status string
    """
    info = get_repo_info(repo_path)

    if "error" in info:
        return "ERROR"

    if info["has_uncommitted_changes"]:
        return "UNCOMMITTED CHANGES"

    if info["has_unpushed_changes"]:
        return "UNPUSHED CHANGES"

    if info["branches_without_origin"]:
        return "BRANCHES WITHOUT ORIGIN"

    return "CLEAN"



def get_merged_branches(repo_path: str) -> List[str]:
    """
    Get a list of branches that have been merged into the main branch
    and can be safely deleted

    Args:
        repo_path: Path to the repository

    Returns:
        List of branch names that can be deleted
    """
    try:
        repo = git.Repo(repo_path)

        # Skip if there's no remote
        if not repo.remotes:
            return []

        # Get the default branch (usually main or master)
        try:
            # Try to get the default branch from the remote
            default_branch = None
            for remote in repo.remotes:
                for ref in remote.refs:
                    if ref.name.endswith('/HEAD'):
                        try:
                            # The symbolic ref points to the default branch
                            default_branch = ref.reference.name.split('/')[-1]
                            break
                        except:
                            pass
                if default_branch:
                    break

            # If we couldn't determine the default branch, use common names
            if not default_branch:
                if 'main' in repo.branches:
                    default_branch = 'main'
                elif 'master' in repo.branches:
                    default_branch = 'master'
                else:
                    # Can't determine default branch
                    return []

            # Get the current branch
            try:
                current_branch = repo.active_branch.name
            except TypeError:
                # Detached HEAD state
                current_branch = None

            # Get merged branches
            merged_branches = []

            # Check each local branch
            for branch in repo.branches:
                # Skip the default branch and current branch
                if branch.name == default_branch or branch.name == current_branch:
                    continue

                # Check if the branch has been merged into the default branch
                try:
                    # If there are no commits in branch that aren't in default_branch,
                    # then the branch has been fully merged
                    commits_ahead = sum(1 for _ in repo.iter_commits(f"{default_branch}..{branch.name}"))
                    if commits_ahead == 0:
                        # Branch is fully merged
                        merged_branches.append(branch.name)
                except:
                    # Skip if there's an error comparing branches
                    pass

            return merged_branches

        except Exception:
            # Can't determine merged branches
            return []

    except Exception:
        # Error accessing repository
        return []
