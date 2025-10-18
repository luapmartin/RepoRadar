#!/usr/bin/env python3
"""
RepoRadar - A tool to monitor git repositories and ensure your work is saved online.

This module provides the command-line interface for RepoRadar. It supports three main commands:

1. scan: Scan a directory for git repositories
2. list: List all monitored repositories and their status
3. web: Start the web interface

Usage:
    python main.py scan /path/to/directory [--max-depth 5]
    python main.py list
    python main.py web [--host 127.0.0.1] [--port 8000]
"""

import argparse

from src.scanner import scan_directory
from src.monitor import RepositoryMonitor
from src.web.server import run_server


def main():
    """
    Main entry point
    """
    parser = argparse.ArgumentParser(description="RepoRadar - A tool to monitor git repositories")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for git repositories")
    scan_parser.add_argument("directory", help="Directory to scan")
    scan_parser.add_argument("--max-depth", type=int, default=5, help="Maximum depth to scan")

    # List command
    list_parser = subparsers.add_parser("list", help="List monitored repositories")

    # Web command
    web_parser = subparsers.add_parser("web", help="Start web interface")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    web_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")

    args = parser.parse_args()

    # Initialize the repository monitor
    monitor = RepositoryMonitor()

    if args.command == "scan":
        # Scan for repositories
        print(f"Scanning {args.directory} (max depth: {args.max_depth})...")
        repos = scan_directory(args.directory, args.max_depth)

        print(f"Found {len(repos)} repositories:")
        for repo in repos:
            print(f"  {repo}")

        # Add repositories to the monitor
        added = monitor.add_repositories(repos)
        print(f"Added {added} new repositories to monitoring")

    elif args.command == "list":
        # Update all repositories
        monitor.update_all_repositories()

        # Get all repositories
        repos = monitor.get_all_repositories()

        if not repos:
            print("No repositories are being monitored")
            return

        print(f"Monitoring {len(repos)} repositories:")
        for repo in repos:
            status = "CLEAN"
            if repo.get("has_uncommitted_changes", False):
                status = "UNCOMMITTED CHANGES"
            elif repo.get("has_unpushed_changes", False):
                status = "UNPUSHED CHANGES"
            elif repo.get("branches_without_origin", False):
                status = "BRANCHES WITHOUT ORIGIN"

            print(f"  {repo['name']} ({repo['path']})")
            print(f"    Branch: {repo['current_branch']}")
            print(f"    Status: {status}")
            print()

    elif args.command == "web":
        # Start web interface
        print(f"Starting web interface at http://{args.host}:{args.port}")
        run_server(host=args.host, port=args.port)

    else:
        # No command specified, show help
        parser.print_help()


if __name__ == "__main__":
    main()
