# RepoRadar

A comprehensive tool to monitor git repositories and ensure your work is saved online. RepoRadar helps you track repository status, identify uncommitted changes, detect unpushed commits, and manage branches across multiple repositories.

## Features

- **Repository Scanning**: Recursively scan directories to discover git repositories
- **Status Monitoring**: Real-time monitoring of repository status
- **Change Detection**:
  - Track uncommitted changes
  - Identify unpushed commits
  - Find branches without remote counterparts
  - Detect merged branches ready for deletion
- **Web Interface**: User-friendly dashboard with:
  - Light and dark theme support
  - Advanced filtering and sorting
  - Repository details and branch information
  - Scan history tracking
  - Quick actions for repository management
- **Command Line Interface**: Full CLI support for automation and scripting
- **Repository Management**: Follow/unfollow repositories, update status, and manage monitoring

## Requirements

- Python 3.7+
- GitPython 3.1.40+

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd RepoRadar
   ```

2. Create a virtual environment and activate it:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Command Line Interface

#### Scan for repositories
Scan a directory and its subdirectories for git repositories:
```bash
python main.py scan /path/to/directory --max-depth 5
```

Options:
- `directory`: Path to scan (required)
- `--max-depth`: Maximum depth to scan (default: 5)

#### List monitored repositories
Display all monitored repositories with their current status:
```bash
python main.py list
```

This will show:
- Repository name and path
- Current branch
- Status (CLEAN, UNCOMMITTED CHANGES, UNPUSHED CHANGES, or BRANCHES WITHOUT ORIGIN)

### Web Interface

Start the web interface for a more user-friendly experience:

```bash
python main.py web [--host 127.0.0.1] [--port 8000]
```

Then open your browser and navigate to `http://127.0.0.1:8000`

#### Web Interface Features

- **Home**: Dashboard with repository statistics
- **Scan**: Discover and add new repositories
- **Repositories**: View all monitored repositories with filtering options
- **Repository Details**: Detailed view of individual repositories including branch information
- **Theme Toggle**: Switch between light and dark themes

## Project Structure

```
RepoRadar/
├── main.py                 # Entry point and CLI
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── LICENSE                # MIT License
├── .gitignore             # Git ignore rules
└── src/
    ├── __init__.py
    ├── git_utils.py       # Git operations and repository info
    ├── scanner.py         # Directory scanning for repositories
    ├── monitor.py         # Repository monitoring and state management
    └── web/
        ├── __init__.py
        └── server.py      # Web server and UI rendering
```

## Data Storage

RepoRadar stores monitored repositories and scan history in JSON files:
- `src/data/repositories.json`: Monitored repositories and their status
- `src/data/scan_history.json`: History of directory scans

These files are automatically created when you first scan or add repositories.

## Repository Status

RepoRadar tracks the following repository statuses:

- **CLEAN**: Repository is up-to-date with no uncommitted or unpushed changes
- **UNCOMMITTED CHANGES**: Repository has uncommitted changes in the working directory
- **UNPUSHED CHANGES**: Repository has commits that haven't been pushed to the remote
- **BRANCHES WITHOUT ORIGIN**: Repository has local branches without remote counterparts
- **ERROR**: An error occurred while checking the repository status

## Configuration

### Monitoring Status

Repositories can have different monitoring statuses:
- **monitored**: Repository is actively monitored (default)
- **unmonitored**: Repository is tracked but not actively monitored

You can change a repository's monitoring status through the web interface.

## Development

### Code Organization

The codebase is organized into logical modules:

- **git_utils.py**: Core git operations using GitPython
  - `is_git_repo()`: Check if a directory is a git repository
  - `get_repo_info()`: Retrieve detailed repository information
  - `get_repo_status()`: Get human-readable repository status
  - `get_merged_branches()`: Identify merged branches

- **scanner.py**: Directory scanning functionality
  - `scan_directory()`: Recursively scan for git repositories

- **monitor.py**: Repository state management
  - `RepositoryMonitor`: Main class for managing monitored repositories

- **web/server.py**: Web interface
  - `RepoRadarHandler`: HTTP request handler
  - Template rendering methods for various pages

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or suggestions, please open an issue on the repository.
