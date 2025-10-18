"""
Simple HTTP server for RepoRadar
"""

import os
import json
import html
import datetime
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Tuple, Optional, Callable

from src.scanner import scan_directory
from src.monitor import RepositoryMonitor
from src.git_utils import get_repo_status


# Initialize the repository monitor
monitor = RepositoryMonitor()


class RepoRadarHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for RepoRadar
    """

    def do_GET(self):
        """
        Handle GET requests
        """
        # Parse the URL
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Route the request
        if path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.render_index().encode())
        elif path == '/scan':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.render_scan().encode())
        elif path == '/repositories':
            # Check for filter parameter
            query_params = urllib.parse.parse_qs(parsed_url.query)
            filter_status = query_params.get('filter', [''])[0]

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.render_repositories(filter_status).encode())
        elif path == '/recheck':
            # Re-check all repositories
            monitor.update_all_repositories()
            self.send_response(303)  # See Other
            self.send_header('Location', '/repositories?message=All+repositories+have+been+re-checked')
            self.end_headers()
        elif path.startswith('/rescan/'):
            # Rescan a directory
            scan_dir = urllib.parse.unquote(path[8:])
            max_depth = 5  # Default max depth

            # Check for max_depth parameter
            query_params = urllib.parse.parse_qs(parsed_url.query)
            if 'max_depth' in query_params:
                try:
                    max_depth = int(query_params['max_depth'][0])
                except (ValueError, IndexError):
                    pass

            # Check if this is a confirmation step
            is_confirmation = 'confirm' in query_params

            if not is_confirmation:
                # First step: scan and show results with checkboxes
                try:
                    # Scan for repositories
                    from src.scanner import scan_directory
                    repos = scan_directory(scan_dir, max_depth)

                    # Show confirmation page
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(self.render_scan_confirmation(scan_dir, repos).encode())
                except Exception as e:
                    # Redirect to scan page with error message
                    message = f"Error rescanning {scan_dir}: {str(e)}"
                    self.send_response(303)  # See Other
                    self.send_header('Location', f'/scan?message={urllib.parse.quote(message)}')
                    self.end_headers()
            else:
                # Second step: process selected repositories from query parameters
                try:
                    # Get the selected repositories
                    selected_repos = []
                    for key, value in query_params.items():
                        if key.startswith('repo_') and value[0] == 'on':
                            repo_path = key[5:]  # Remove 'repo_' prefix
                            selected_repos.append(urllib.parse.unquote(repo_path))

                    # Add the selected repositories
                    added = monitor.add_repositories(selected_repos, scan_dir)

                    # Redirect to scan page
                    message = f"Rescanned {scan_dir}: found {len(selected_repos)} repositories, added {added} new ones"
                    self.send_response(303)  # See Other
                    self.send_header('Location', f'/scan?message={urllib.parse.quote(message)}')
                    self.end_headers()
                except Exception as e:
                    # Redirect to scan page with error message
                    message = f"Error adding repositories: {str(e)}"
                    self.send_response(303)  # See Other
                    self.send_header('Location', f'/scan?message={urllib.parse.quote(message)}')
                    self.end_headers()
            return
        elif path.startswith('/repository/'):
            repo_path = urllib.parse.unquote(path[12:])
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.render_repository_details(repo_path).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>404 Not Found</h1>')

    def do_POST(self):
        """
        Handle POST requests
        """
        # Parse the URL
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Get the form data
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode()
        form_data = urllib.parse.parse_qs(post_data)

        # Route the request
        if path == '/scan':
            directory = form_data.get('directory', [''])[0]
            max_depth = int(form_data.get('max_depth', ['5'])[0])

            # Check if this is the first scan or the confirmation step
            is_confirmation = 'confirm' in form_data

            if directory and not is_confirmation:
                try:
                    # First step: scan and show results with checkboxes
                    repos = scan_directory(directory, max_depth)

                    # Store the scan results in a session
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()

                    # Render the confirmation page with checkboxes
                    self.wfile.write(self.render_scan_confirmation(directory, repos).encode())
                    return
                except Exception as e:
                    message = f'Error scanning directory: {str(e)}'
            elif directory and is_confirmation:
                # Second step: process selected repositories
                try:
                    # Get the selected repositories
                    selected_repos = []
                    for key, value in form_data.items():
                        if key.startswith('repo_') and value[0] == 'on':
                            repo_path = key[5:]  # Remove 'repo_' prefix
                            selected_repos.append(urllib.parse.unquote(repo_path))

                    # Add the selected repositories
                    added = monitor.add_repositories(selected_repos, directory)
                    message = f'Found {len(selected_repos)} repositories, added {added} new ones'
                except Exception as e:
                    message = f'Error adding repositories: {str(e)}'
            else:
                message = 'Please enter a directory to scan'

            # Redirect to repositories page
            self.send_response(303)
            self.send_header('Location', f'/repositories?message={urllib.parse.quote(message)}')
            self.end_headers()
        elif path.startswith('/repository/remove/') or path.startswith('/repository/unfollow/'):
            # Support both old and new route patterns
            if path.startswith('/repository/remove/'):
                repo_path = urllib.parse.unquote(path[18:])
            else:  # /repository/unfollow/
                repo_path = urllib.parse.unquote(path[20:])

            if monitor.remove_repository(repo_path):
                message = 'Repository unfollowed successfully'
            else:
                message = 'Error unfollowing repository'

            # Redirect to repositories page
            self.send_response(303)
            self.send_header('Location', f'/repositories?message={urllib.parse.quote(message)}')
            self.end_headers()
        elif path.startswith('/repository/follow/'):
            repo_path = urllib.parse.unquote(path[18:])

            if monitor.add_repository(repo_path, "monitored"):
                message = 'Repository followed successfully'
            else:
                message = 'Error following repository'

            # Redirect to repositories page
            self.send_response(303)
            self.send_header('Location', f'/repositories?message={urllib.parse.quote(message)}')
            self.end_headers()
        elif path.startswith('/repository/status/'):
            repo_path = urllib.parse.unquote(path[18:])
            status = form_data.get('status', ['monitored'])[0]

            if monitor.set_repository_status(repo_path, status):
                message = f'Repository status changed to {status}'
            else:
                message = 'Error changing repository status'

            # Redirect to repository details page
            self.send_response(303)
            self.send_header('Location', f'/repository/{urllib.parse.quote(repo_path)}?message={urllib.parse.quote(message)}')
            self.end_headers()
        elif path.startswith('/repository/recheck/'):
            repo_path = urllib.parse.unquote(path[19:])

            if monitor.update_repository(repo_path):
                message = 'Repository has been re-checked'
            else:
                message = 'Error re-checking repository'

            # Get the referer to determine where to redirect
            referer = self.headers.get('Referer', '')

            # If the request came from the repositories page, redirect back there
            if '/repositories' in referer:
                self.send_response(303)
                self.send_header('Location', f'/repositories?message={urllib.parse.quote(message)}')
                self.end_headers()
            else:
                # Otherwise redirect to repository details page
                self.send_response(303)
                self.send_header('Location', f'/repository/{urllib.parse.quote(repo_path)}?message={urllib.parse.quote(message)}')
                self.end_headers()
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>404 Not Found</h1>')

    def render_template(self, title: str, content: str, include_datatables: bool = False, include_fuzzy_search: bool = False) -> str:
        """
        Render a template with the given title and content

        Args:
            title: Page title
            content: Page content
            include_datatables: Whether to include DataTables library
            include_fuzzy_search: Whether to include fuzzy search functionality

        Returns:
            HTML string
        """
        # Get the message from the query string
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        message = query_params.get('message', [''])[0]

        # Get theme preference from query parameters or default to light
        theme = query_params.get('theme', ['light'])[0]
        is_dark_theme = theme == 'dark'

        # Render the message
        message_html = f'<div class="message">{html.escape(message)}</div>' if message else ''

        # Include necessary libraries
        libraries_html = ''
        if include_datatables:
            libraries_html += '''
    <!-- DataTables CSS and JS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.min.css">
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js"></script>
'''

        if include_fuzzy_search:
            libraries_html += '''
    <!-- Fuse.js for fuzzy search -->
    <script src="https://cdn.jsdelivr.net/npm/fuse.js@6.6.2"></script>
'''

        # Theme toggle script
        theme_toggle_script = '''
    <script>
        function toggleTheme() {
            const currentTheme = document.body.classList.contains('dark-theme') ? 'dark' : 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            // Update URL with new theme parameter
            const url = new URL(window.location.href);
            url.searchParams.set('theme', newTheme);
            window.location.href = url.toString();
        }
    </script>
'''

        # Theme-specific CSS
        theme_css = '''
        /* Light theme (default) */
        :root {
            --bg-color: #ffffff;
            --text-color: #333333;
            --header-bg: #f8f9fa;
            --border-color: #dee2e6;
            --link-color: #0366d6;
            --link-hover-color: #0056b3;
            --button-bg: #0366d6;
            --button-color: white;
            --table-header-bg: #f6f8fa;
            --table-row-hover: #f8f9fa;
            --message-bg: #f8f9fa;
            --message-border: #0366d6;
            --input-bg: #ffffff;
            --input-border: #ced4da;
        }

        /* Dark theme */
        body.dark-theme {
            --bg-color: #1e1e1e;
            --text-color: #e0e0e0;
            --header-bg: #252525;
            --border-color: #444444;
            --link-color: #58a6ff;
            --link-hover-color: #79b8ff;
            --button-bg: #2ea043;
            --button-color: white;
            --table-header-bg: #252525;
            --table-row-hover: #2d2d2d;
            --message-bg: #252525;
            --message-border: #58a6ff;
            --input-bg: #2d2d2d;
            --input-border: #444444;
        }
'''

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RepoRadar - {html.escape(title)}</title>
{libraries_html}
    <style>
{theme_css}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background-color: var(--bg-color);
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            transition: background-color 0.3s, color 0.3s;
        }}

        header {{
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            background-color: var(--header-bg);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .header-content {{
            display: flex;
            align-items: center;
        }}

        nav ul {{
            list-style: none;
            padding: 0;
            display: flex;
            gap: 20px;
        }}

        nav ul li a {{
            text-decoration: none;
            color: var(--link-color);
        }}

        nav ul li a:hover {{
            color: var(--link-hover-color);
        }}

        .theme-toggle {{
            background: none;
            border: none;
            cursor: pointer;
            font-size: 1.5rem;
            color: var(--text-color);
            padding: 5px;
        }}

        .message {{
            padding: 10px;
            margin-bottom: 10px;
            background-color: var(--message-bg);
            border-left: 4px solid var(--message-border);
        }}

        .search-container {{
            margin-bottom: 20px;
        }}

        .search-input {{
            padding: 8px;
            width: 100%;
            max-width: 400px;
            border: 1px solid var(--input-border);
            border-radius: 4px;
            background-color: var(--input-bg);
            color: var(--text-color);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}

        table th, table td {{
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}

        table th {{
            background-color: var(--table-header-bg);
            cursor: pointer;
        }}

        table th:hover {{
            background-color: var(--table-row-hover);
        }}

        table tr:hover {{
            background-color: var(--table-row-hover);
        }}

        .status-clean {{
            color: #28a745;
        }}

        .status-warning {{
            color: #ffc107;
        }}

        .status-error {{
            color: #dc3545;
        }}

        form {{
            margin-bottom: 20px;
        }}

        input, button, select {{
            padding: 8px;
            margin-bottom: 10px;
            background-color: var(--input-bg);
            color: var(--text-color);
            border: 1px solid var(--input-border);
            border-radius: 4px;
        }}

        input[type="text"], select {{
            width: 100%;
            max-width: 400px;
        }}

        button {{
            background-color: var(--button-bg);
            color: var(--button-color);
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}

        button:hover {{
            opacity: 0.9;
        }}

        a.button {{
            display: inline-block;
            padding: 8px;
            background-color: var(--button-bg);
            color: var(--button-color);
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
        }}

        a.button:hover {{
            opacity: 0.9;
        }}

        .stats-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}

        .stat-card-link {{
            text-decoration: none;
            color: inherit;
            display: block;
        }}

        .stat-card {{
            background-color: var(--header-bg);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 15px;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }}

        .stat-card.active {{
            border: 2px solid var(--link-color);
            box-shadow: 0 0 10px rgba(3, 102, 214, 0.3);
        }}

        .stat-value {{
            font-size: 2rem;
            font-weight: bold;
            margin: 10px 0;
        }}

        .stat-label {{
            font-size: 0.9rem;
            color: var(--text-color);
            opacity: 0.8;
        }}

        /* DataTables customization */
        .dataTables_wrapper {{
            color: var(--text-color);
        }}

        .dataTables_wrapper .dataTables_length,
        .dataTables_wrapper .dataTables_filter,
        .dataTables_wrapper .dataTables_info,
        .dataTables_wrapper .dataTables_processing,
        .dataTables_wrapper .dataTables_paginate {{
            color: var(--text-color);
        }}

        .dataTables_wrapper .dataTables_filter input {{
            background-color: var(--input-bg);
            color: var(--text-color);
            border: 1px solid var(--input-border);
        }}

        .dataTables_wrapper .dataTables_paginate .paginate_button {{
            color: var(--link-color) !important;
        }}

        .dataTables_wrapper .dataTables_paginate .paginate_button.current {{
            background: var(--button-bg) !important;
            color: var(--button-color) !important;
            border: 1px solid var(--button-bg) !important;
        }}
    </style>
{theme_toggle_script}
</head>
<body class="{"dark-theme" if is_dark_theme else ""}">
    <header>
        <div class="header-content">
            <h1>RepoRadar</h1>
            <nav>
                <ul>
                    <li><a href="/">Home</a></li>
                    <li><a href="/scan">Scan</a></li>
                    <li><a href="/repositories">Repositories</a></li>
                </ul>
            </nav>
        </div>
        <button class="theme-toggle" onclick="toggleTheme()">{"🌙" if not is_dark_theme else "☀️"}</button>
    </header>

    {message_html}

    <main>
        {content}
    </main>
</body>
</html>'''

    def render_index(self) -> str:
        """
        Render the index page

        Returns:
            HTML string
        """
        # Get repositories for statistics
        repos = monitor.get_all_repositories()

        # Calculate statistics
        total_repos = len(repos)
        clean_repos = 0
        problem_repos = 0

        for repo in repos:
            git_status = get_repo_status(repo['path'])
            if git_status == 'CLEAN':
                clean_repos += 1
            else:
                problem_repos += 1

        # Generate statistics HTML
        stats_html = ''
        if total_repos > 0:
            stats_html = f'''
            <div class="stats-container">
                <div class="stat-card">
                    <div class="stat-label">Total Repositories</div>
                    <div class="stat-value">{total_repos}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Clean Repositories</div>
                    <div class="stat-value" style="color: #28a745;">{clean_repos}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Repositories Needing Attention</div>
                    <div class="stat-value" style="color: #ffc107;">{problem_repos}</div>
                </div>
            </div>
            '''

        content = f'''
        <h2>Welcome to RepoRadar</h2>

        <p>
            RepoRadar is a tool to monitor your git repositories and make sure your work is saved online.
        </p>

        {stats_html}

        <div style="display: flex; gap: 20px; margin: 30px 0;">
            <a href="/scan" style="text-decoration: none;">
                <div class="stat-card" style="cursor: pointer; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                    <h3>Scan for Repositories</h3>
                    <p>Find git repositories in a directory</p>
                </div>
            </a>

            <a href="/repositories" style="text-decoration: none;">
                <div class="stat-card" style="cursor: pointer; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                    <h3>View Repositories</h3>
                    <p>Monitor and manage your repositories</p>
                </div>
            </a>
        </div>

        <h3>Features</h3>

        <ul>
            <li>Scan directories for git repositories</li>
            <li>Monitor repository status</li>
            <li>Track uncommitted changes</li>
            <li>Identify unpushed changes</li>
            <li>Find branches without remote counterparts</li>
            <li>Light and dark theme support</li>
            <li>Advanced filtering and sorting</li>
        </ul>
        '''

        return self.render_template('Home', content)

    def render_scan_confirmation(self, directory: str, repos: List[str]) -> str:
        """
        Render the scan confirmation page with checkboxes for repositories found

        Args:
            directory: Directory that was scanned
            repos: List of repositories found

        Returns:
            HTML string
        """
        # Generate HTML for repository checkboxes
        repos_html = ''

        if repos:
            repos_html += '''
            <form method="post" action="/scan">
                <input type="hidden" name="directory" value="''' + html.escape(directory) + '''">
                <input type="hidden" name="confirm" value="true">

                <div class="stat-card" style="margin-bottom: 20px;">
                    <h3>Select repositories to add</h3>
                    <p>Found ''' + str(len(repos)) + ''' repositories in ''' + html.escape(directory) + '''</p>

                    <div style="margin: 10px 0;">
                        <button type="button" onclick="selectAll(true)">Select All</button>
                        <button type="button" onclick="selectAll(false)">Deselect All</button>
                    </div>

                    <div style="max-height: 400px; overflow-y: auto; margin: 10px 0; border: 1px solid var(--border-color); padding: 10px;">
            '''

            for repo_path in repos:
                # Get repository name (directory name)
                name = os.path.basename(os.path.abspath(repo_path))

                # Check if repository is already monitored
                is_monitored = monitor.get_repository(repo_path) is not None

                # Create checkbox (checked by default if not already monitored)
                checked = "" if is_monitored else "checked"
                status = "(already monitored)" if is_monitored else ""

                repos_html += f'''
                <div style="margin-bottom: 5px;">
                    <label>
                        <input type="checkbox" name="repo_{urllib.parse.quote(repo_path)}" {checked}>
                        {html.escape(name)} <span style="color: var(--text-color); opacity: 0.7;">{html.escape(repo_path)} {status}</span>
                    </label>
                </div>
                '''

            repos_html += '''
                    </div>

                    <div style="margin-top: 10px;">
                        <button type="submit">Add Selected Repositories</button>
                        <a href="/scan" class="button" style="background-color: #6c757d;">Cancel</a>
                    </div>
                </div>
            </form>

            <script>
                function selectAll(select) {
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = select;
                    });
                }
            </script>
            '''
        else:
            repos_html = '''
            <div class="stat-card">
                <p>No repositories found in ''' + html.escape(directory) + '''</p>
                <a href="/scan" class="button">Back to Scan</a>
            </div>
            '''

        content = f'''
        <h2>Scan Results</h2>

        {repos_html}
        '''

        return self.render_template('Scan Results', content)

    def render_scan(self) -> str:
        """
        Render the scan page

        Returns:
            HTML string
        """
        # Get current directory as default
        current_dir = os.getcwd()

        # Get scan history
        scan_history = monitor.get_scan_history()

        # Generate scan history HTML
        scan_history_html = ''
        if scan_history:
            scan_history_html = '''
            <h3>Scan History</h3>
            <table class="display">
                <thead>
                    <tr>
                        <th>Directory</th>
                        <th>Date</th>
                        <th>Repositories Found</th>
                        <th>Repositories Added</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
            '''

            # Sort scan history by date (newest first)
            scan_history.sort(key=lambda x: x.get('scan_date', ''), reverse=True)

            for entry in scan_history:
                scan_dir = entry.get('scan_dir', '')
                scan_date = entry.get('scan_date', '')
                repos_found = entry.get('repos_found', 0)
                repos_added = entry.get('repos_added', 0)

                # Format the scan date
                if scan_date:
                    try:
                        # Convert ISO format to a more readable format
                        scan_date_obj = datetime.datetime.fromisoformat(scan_date)
                        scan_date_formatted = scan_date_obj.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        scan_date_formatted = scan_date
                else:
                    scan_date_formatted = 'Unknown'

                scan_history_html += f'''
                <tr>
                    <td>{html.escape(scan_dir)}</td>
                    <td>{html.escape(scan_date_formatted)}</td>
                    <td>{repos_found}</td>
                    <td>{repos_added}</td>
                    <td>
                        <a href="/rescan/{urllib.parse.quote(scan_dir)}" class="button">Re-scan</a>
                    </td>
                </tr>
                '''

            scan_history_html += '''
                </tbody>
            </table>
            '''

        content = f'''
        <h2>Scan for Git Repositories</h2>

        <div class="stat-card" style="margin-bottom: 20px;">
            <p>
                Scan a directory to find git repositories. RepoRadar will search through the directory and its subdirectories
                to find git repositories that you can then monitor.
            </p>
        </div>

        <form method="post" class="stat-card">
            <div style="margin-bottom: 15px;">
                <label for="directory">Directory to scan:</label>
                <input type="text" id="directory" name="directory" placeholder="Enter directory path" value="{html.escape(current_dir)}" required>
            </div>

            <div style="margin-bottom: 15px;">
                <label for="max_depth">Maximum depth:</label>
                <select id="max_depth" name="max_depth">
                    <option value="1">1 (current directory only)</option>
                    <option value="2">2</option>
                    <option value="3">3</option>
                    <option value="4">4</option>
                    <option value="5" selected>5</option>
                    <option value="10">10</option>
                    <option value="20">20</option>
                </select>
                <p style="font-size: 0.9em; opacity: 0.8; margin-top: 5px;">
                    The maximum depth determines how deep RepoRadar will search in the directory structure.
                    Higher values will search more subdirectories but may take longer.
                </p>
            </div>

            <button type="submit">Start Scan</button>
        </form>

        <div class="stat-card" style="margin-top: 20px;">
            <h3>What happens after scanning?</h3>
            <p>
                After scanning, RepoRadar will add all found repositories to your monitoring list.
                You can then view their status, check for uncommitted changes, and ensure your work is saved online.
            </p>
            <p>
                <strong>Note:</strong> Scanning a directory with many subdirectories may take some time.
            </p>
        </div>

        {scan_history_html}
        '''

        return self.render_template('Scan', content, include_datatables=bool(scan_history))

    def render_repositories(self, filter_status: str = "") -> str:
        """
        Render the repositories page

        Args:
            filter_status: Optional filter for repository status

        Returns:
            HTML string
        """
        # Update all repositories
        monitor.update_all_repositories()

        # Get all repositories
        repos = monitor.get_all_repositories()

        # Calculate statistics
        total_repos = len(repos)
        clean_repos = 0
        uncommitted_repos = 0
        unpushed_repos = 0
        branches_without_origin_repos = 0
        error_repos = 0
        monitored_repos = 0
        unmonitored_repos = 0

        # Sort repositories by status (problematic first)
        status_order = {
            'ERROR': 0,
            'UNCOMMITTED CHANGES': 1,
            'UNPUSHED CHANGES': 2,
            'BRANCHES WITHOUT ORIGIN': 3,
            'CLEAN': 4
        }

        for repo in repos:
            git_status = get_repo_status(repo['path'])
            repo['status'] = git_status

            # Count by git status
            if git_status == 'CLEAN':
                clean_repos += 1
            elif git_status == 'UNCOMMITTED CHANGES':
                uncommitted_repos += 1
            elif git_status == 'UNPUSHED CHANGES':
                unpushed_repos += 1
            elif git_status == 'BRANCHES WITHOUT ORIGIN':
                branches_without_origin_repos += 1
            elif git_status == 'ERROR':
                error_repos += 1

            # Count by monitor status
            monitor_status = repo.get('status', 'monitored')
            if monitor_status == 'monitored':
                monitored_repos += 1
            else:  # unmonitored
                unmonitored_repos += 1

        repos.sort(key=lambda r: status_order.get(r['status'], 5))

        # Apply filter if specified
        filtered_repos = repos
        filter_message = ""

        if filter_status:
            if filter_status == "CLEAN":
                filtered_repos = [r for r in repos if r['status'] == 'CLEAN']
                filter_message = "Showing only clean repositories"
            elif filter_status == "UNCOMMITTED CHANGES":
                filtered_repos = [r for r in repos if r['status'] == 'UNCOMMITTED CHANGES']
                filter_message = "Showing only repositories with uncommitted changes"
            elif filter_status == "UNPUSHED CHANGES":
                filtered_repos = [r for r in repos if r['status'] == 'UNPUSHED CHANGES']
                filter_message = "Showing only repositories with unpushed changes"
            elif filter_status == "BRANCHES WITHOUT ORIGIN":
                filtered_repos = [r for r in repos if r['status'] == 'BRANCHES WITHOUT ORIGIN']
                filter_message = "Showing only repositories with branches without origin"
            elif filter_status == "ERROR":
                filtered_repos = [r for r in repos if r['status'] == 'ERROR']
                filter_message = "Showing only repositories with errors"
            elif filter_status == "monitored":
                filtered_repos = [r for r in repos if r.get('status', 'monitored') == 'monitored']
                filter_message = "Showing only monitored repositories"
            elif filter_status == "unmonitored":
                filtered_repos = [r for r in repos if r.get('status', 'monitored') == 'unmonitored']
                filter_message = "Showing only unmonitored repositories"


        # Generate statistics HTML with clickable cards
        stats_html = f'''
        <div class="stats-container">
            <a href="/repositories" class="stat-card-link" title="Show all repositories">
                <div class="stat-card {"active" if not filter_status else ""}">
                    <div class="stat-label">Total Repositories</div>
                    <div class="stat-value">{total_repos}</div>
                </div>
            </a>
            <a href="/repositories?filter=CLEAN" class="stat-card-link" title="Show only clean repositories">
                <div class="stat-card {"active" if filter_status == "CLEAN" else ""}">
                    <div class="stat-label">Clean</div>
                    <div class="stat-value" style="color: #28a745;">{clean_repos}</div>
                </div>
            </a>
            <a href="/repositories?filter=UNCOMMITTED+CHANGES" class="stat-card-link" title="Show only repositories with uncommitted changes">
                <div class="stat-card {"active" if filter_status == "UNCOMMITTED CHANGES" else ""}">
                    <div class="stat-label">Uncommitted Changes</div>
                    <div class="stat-value" style="color: #ffc107;">{uncommitted_repos}</div>
                </div>
            </a>
            <a href="/repositories?filter=UNPUSHED+CHANGES" class="stat-card-link" title="Show only repositories with unpushed changes">
                <div class="stat-card {"active" if filter_status == "UNPUSHED CHANGES" else ""}">
                    <div class="stat-label">Unpushed Changes</div>
                    <div class="stat-value" style="color: #ffc107;">{unpushed_repos}</div>
                </div>
            </a>
            <a href="/repositories?filter=monitored" class="stat-card-link" title="Show only repositories you're following">
                <div class="stat-card {"active" if filter_status == "monitored" else ""}">
                    <div class="stat-label">Following</div>
                    <div class="stat-value">{monitored_repos}</div>
                </div>
            </a>
            <a href="/repositories?filter=unmonitored" class="stat-card-link" title="Show only repositories you're not following">
                <div class="stat-card {"active" if filter_status == "unmonitored" else ""}">
                    <div class="stat-label">Not Following</div>
                    <div class="stat-value">{unmonitored_repos}</div>
                </div>
            </a>
        </div>
        '''

        # Render the repositories
        if repos:
            # Add fuzzy search input
            search_html = '''
            <div class="search-container">
                <input type="text" id="repo-search" class="search-input" placeholder="Search repositories..." />
            </div>
            '''

            repos_html = '''
            <table id="repositories-table" class="display">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Location</th>
                        <th>Provider</th>
                        <th>Branch</th>
                        <th>Status</th>
                        <th>Last Check</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
            '''

            # Display filter message if applicable
            if filter_message:
                repos_html = f'''
                <div class="stat-card" style="margin-bottom: 20px;">
                    <p>{filter_message}</p>
                </div>
                ''' + repos_html

            # Use filtered repositories instead of all repositories
            for repo in filtered_repos:
                status_class = 'status-clean'
                if repo['status'] == 'ERROR':
                    status_class = 'status-error'
                elif repo['status'] != 'CLEAN':
                    status_class = 'status-warning'

                # Format the last check date
                last_check = repo.get('last_check', '')
                if last_check:
                    try:
                        # Convert ISO format to a more readable format
                        last_check_date = datetime.datetime.fromisoformat(last_check)
                        last_check_formatted = last_check_date.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        last_check_formatted = last_check
                else:
                    last_check_formatted = 'Never'

                # Get the monitor status
                monitor_status = repo.get('status', 'monitored')

                # Get the repository path
                repo_path = repo['path']

                # Format the location display - show only parent folder
                parent_dir = os.path.dirname(repo_path)
                location_display = html.escape(os.path.basename(parent_dir))

                # Determine if the repo is being followed
                is_followed = monitor_status == 'monitored'
                follow_action = 'Unfollow' if is_followed else 'Follow'
                follow_route = 'unfollow' if is_followed else 'follow'

                # Check if repo has merged branches that can be deleted
                has_merged_branches = repo.get('has_merged_branches', False)
                merged_indicator = ' 🔄' if has_merged_branches else ''

                # Get remote provider summary with icon
                provider_summary = repo.get('remote_provider_summary', 'N/A')
                provider_icon = ''
                if provider_summary == 'GitHub':
                    provider_icon = '🐙 '
                elif provider_summary == 'GitLab':
                    provider_icon = '🦊 '
                elif provider_summary == 'Bitbucket':
                    provider_icon = '🪣 '
                elif provider_summary == 'Azure DevOps':
                    provider_icon = '🔷 '
                elif provider_summary == 'Codeberg':
                    provider_icon = '🌊 '
                elif provider_summary == 'SourceForge':
                    provider_icon = '🔧 '
                elif provider_summary == 'Other':
                    provider_icon = '🔗 '
                elif provider_summary == 'None':
                    provider_icon = '❌ '

                provider_display = f'{provider_icon}{provider_summary}'

                repos_html += f'''
                <tr class="repo-row" data-href="/repository/{urllib.parse.quote(repo['path'])}" style="cursor: pointer;">
                    <td>{html.escape(repo['name'])}{merged_indicator}</td>
                    <td title="{html.escape(repo_path)}">{location_display}</td>
                    <td>{provider_display}</td>
                    <td>{html.escape(repo['current_branch'])}</td>
                    <td class="{status_class}">{html.escape(repo['status'])}</td>
                    <td>{html.escape(last_check_formatted)}</td>
                    <td onclick="event.stopPropagation();">
                        <div style="display: flex; gap: 5px;">
                            <form method="post" action="/repository/recheck/{urllib.parse.quote(repo['path'])}" style="display: inline; margin: 0;">
                                <button type="submit" title="Refresh repository" style="padding: 4px 8px;">🔄</button>
                            </form>
                            <form method="post" action="/repository/{follow_route}/{urllib.parse.quote(repo['path'])}" style="display: inline; margin: 0;">
                                <button type="submit" onclick="return confirm('Are you sure you want to {follow_action.lower()} this repository?')">{follow_action}</button>
                            </form>
                        </div>
                    </td>
                </tr>
                '''

            repos_html += '''
                </tbody>
            </table>

            <script>
                $(document).ready(function() {
                    // Initialize DataTables
                    const table = $('#repositories-table').DataTable({
                        paging: true,
                        searching: true,
                        ordering: true,
                        info: true,
                        pageLength: 25,
                        language: {
                            search: "Filter:"
                        }
                    });

                    // Custom fuzzy search
                    $('#repo-search').on('keyup', function() {
                        table.search(this.value).draw();
                    });

                    // Make rows clickable
                    $('.repo-row').on('click', function() {
                        window.location.href = $(this).data('href');
                    });
                });
            </script>
            '''
        else:
            search_html = ''
            repos_html = '''
            <p>No repositories are being monitored. <a href="/scan">Scan for repositories</a> to get started.</p>
            '''

        content = f'''
        <h2>Repositories</h2>

        {stats_html}

        <div style="margin-bottom: 20px;">
            <form method="get" action="/recheck">
                <button type="submit">Re-check All Repositories</button>
            </form>
        </div>

        {search_html}
        {repos_html}
        '''

        return self.render_template('Repositories', content, include_datatables=True, include_fuzzy_search=True)

    def render_repository_details(self, repo_path: str) -> str:
        """
        Render the repository details page

        Args:
            repo_path: Path to the repository

        Returns:
            HTML string
        """
        # Update repository
        monitor.update_repository(repo_path)

        # Get repository information
        repo = monitor.get_repository(repo_path)

        if not repo:
            content = '''
            <h2>Repository Not Found</h2>

            <p>The repository you requested could not be found.</p>

            <p><a href="/repositories">Back to Repositories</a></p>
            '''

            return self.render_template('Repository Not Found', content)

        # Render warnings
        warnings_html = ''

        if repo.get('has_uncommitted_changes', False):
            warnings_html += '''
            <div class="status-warning">
                <p><strong>Warning:</strong> This repository has uncommitted changes.</p>
            </div>
            '''

        if repo.get('has_unpushed_changes', False):
            warnings_html += '''
            <div class="status-warning">
                <p><strong>Warning:</strong> This repository has unpushed changes.</p>
            </div>
            '''

        if repo.get('branches_without_origin', False):
            warnings_html += '''
            <div class="status-warning">
                <p><strong>Warning:</strong> This repository has branches without remote counterparts.</p>
            </div>
            '''

        if repo.get('has_merged_branches', False):
            merged_branches = repo.get('merged_branches', [])
            merged_branches_str = ', '.join(merged_branches)
            warnings_html += f'''
            <div class="status-clean">
                <p><strong>Info:</strong> This repository has merged branches that can be deleted: {html.escape(merged_branches_str)}</p>
            </div>
            '''

        # Render branches
        branches_html = '''
        <h3>Branches</h3>

        <table>
            <thead>
                <tr>
                    <th>Branch</th>
                    <th>Has Remote</th>
                    <th>Unpushed Commits</th>
                    <th>Can Be Deleted</th>
                </tr>
            </thead>
            <tbody>
        '''

        for branch in repo.get('branches', []):
            current = ' (current)' if branch['name'] == repo['current_branch'] else ''
            has_origin_class = 'status-clean' if branch['has_origin'] else 'status-warning'
            has_origin_text = 'Yes' if branch['has_origin'] else 'No'
            unpushed_class = 'status-warning' if branch['unpushed_commits'] > 0 else 'status-clean'

            # Check if branch can be deleted (merged)
            can_be_deleted = branch.get('can_be_deleted', False)
            can_be_deleted_class = 'status-clean' if can_be_deleted else ''
            can_be_deleted_text = 'Yes (merged)' if can_be_deleted else 'No'

            branches_html += f'''
            <tr>
                <td>{html.escape(branch['name'])}{current}</td>
                <td class="{has_origin_class}">{has_origin_text}</td>
                <td class="{unpushed_class}">{branch['unpushed_commits']}</td>
                <td class="{can_be_deleted_class}">{can_be_deleted_text}</td>
            </tr>
            '''

        branches_html += '''
            </tbody>
        </table>
        '''

        # Render status
        git_status = get_repo_status(repo['path'])
        status_class = 'status-clean'
        if git_status == 'ERROR':
            status_class = 'status-error'
        elif git_status != 'CLEAN':
            status_class = 'status-warning'

        # Format the last check date
        last_check = repo.get('last_check', '')
        if last_check:
            try:
                # Convert ISO format to a more readable format
                last_check_date = datetime.datetime.fromisoformat(last_check)
                last_check_formatted = last_check_date.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                last_check_formatted = last_check
        else:
            last_check_formatted = 'Never'

        # Get the monitor status
        monitor_status = repo.get('status', 'monitored')

        content = f'''
        <h2>Repository: {html.escape(repo['name'])}</h2>

        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-label">Path</div>
                <div style="word-break: break-all;">{html.escape(repo['path'])}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Current Branch</div>
                <div>{html.escape(repo['current_branch'])}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Git Status</div>
                <div class="{status_class}">{html.escape(git_status)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Status</div>
                <div>{"Following" if monitor_status == "monitored" else "Not Following"}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Last Check</div>
                <div>{html.escape(last_check_formatted)}</div>
            </div>
        </div>

        <div style="display: flex; gap: 10px; margin-bottom: 20px;">
            <form method="post" action="/repository/recheck/{urllib.parse.quote(repo['path'])}">
                <button type="submit">Re-check Repository</button>
            </form>

            <form method="post" action="/repository/status/{urllib.parse.quote(repo['path'])}" style="display: flex; align-items: center; gap: 10px;">
                <select id="status" name="status">
                    <option value="monitored" {"selected" if monitor_status == "monitored" else ""}>Following</option>
                    <option value="unmonitored" {"selected" if monitor_status == "unmonitored" or monitor_status == "skipped" else ""}>Not Following</option>
                </select>
                <button type="submit">Update Status</button>
            </form>

            <form method="post" action="/repository/unfollow/{urllib.parse.quote(repo['path'])}">
                <button type="submit" onclick="return confirm('Are you sure you want to unfollow this repository?')" style="background-color: #dc3545;">Unfollow Repository</button>
            </form>
        </div>

        {warnings_html}

        {self.render_remotes_table(repo)}

        {branches_html}

        <p>
            <a href="/repositories">← Back to Repositories</a>
        </p>
        '''

        return self.render_template(repo['name'], content)

    def render_remotes_table(self, repo: Dict) -> str:
        """
        Render the remotes table for the repository details page

        Args:
            repo: Repository information dictionary

        Returns:
            HTML string for the remotes table
        """
        remotes_info = repo.get('remotes_info', [])

        if not remotes_info:
            return ""

        remotes_html = '''
        <h3>Remotes</h3>
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>URL</th>
                    <th>Provider</th>
                </tr>
            </thead>
            <tbody>
        '''

        for remote in remotes_info:
            provider = remote.get('provider', 'N/A')
            provider_icon = ''
            if provider == 'GitHub':
                provider_icon = '🐙 '
            elif provider == 'GitLab':
                provider_icon = '🦊 '
            elif provider == 'Bitbucket':
                provider_icon = '🪣 '
            elif provider == 'Azure DevOps':
                provider_icon = '🔷 '
            elif provider == 'Codeberg':
                provider_icon = '🌊 '
            elif provider == 'SourceForge':
                provider_icon = '🔧 '
            elif provider == 'Other':
                provider_icon = '🔗 '
            elif provider == 'Error':
                provider_icon = '❌ '

            provider_display = f'{provider_icon}{provider}'

            remotes_html += f'''
            <tr>
                <td>{html.escape(remote.get('name', 'N/A'))}</td>
                <td style="word-break: break-all;">{html.escape(remote.get('url', 'N/A'))}</td>
                <td>{provider_display}</td>
            </tr>
            '''

        remotes_html += '''
            </tbody>
        </table>
        '''
        return remotes_html


def run_server(host: str = '127.0.0.1', port: int = 8000):
    """
    Run the HTTP server

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    server_address = (host, port)
    httpd = HTTPServer(server_address, RepoRadarHandler)
    print(f'Starting server at http://{host}:{port}')
    print('Press Ctrl+C to stop the server')

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        httpd.server_close()
        print('Server stopped successfully')
