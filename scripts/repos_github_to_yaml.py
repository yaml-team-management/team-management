# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml",
#   "requests",
# ]
# ///

# This script fetches repository permissions from GitHub
# and updates repos.yaml with write-level (and above) permissions.
# This is a READ-ONLY sync: GitHub -> repos.yaml

import os
from pathlib import Path

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://api.github.com"
API_VERSION = "2022-11-28"
PER_PAGE = 100
REQUEST_TIMEOUT = 60
COMMENT = "# AUTOMATICALLY UPDATED \u2014 DO NOT EDIT THE PERMISSIONS SECTION MANUALLY\n"
MARKER = "permissions:"

# Permission levels we care about (write and above)
TRACKED_PERMISSIONS = ["admin", "maintain", "write", "triage"]

# Retry configuration for API calls
RETRY_TOTAL = 3
RETRY_BACKOFF_FACTOR = 1
RETRY_STATUS_FORCELIST = [429, 500, 502, 503, 504]


def main():
    org = require_env("ORG")
    token = require_env("TOKEN")
    session = create_session(token)

    repos_path = Path("repos.yaml")
    tracked_repos = load_tracked_repos(repos_path)

    if not tracked_repos:
        print("No repositories are being tracked. Add repositories to tracked_repos in repos.yaml")
        return

    permissions_list = []
    
    for repo_name in tracked_repos:
        print(f"Fetching permissions for {org}/{repo_name}...")
        repo_permissions = fetch_repo_permissions(org, repo_name, session)
        
        if repo_permissions:
            permissions_list.append(repo_permissions)

    new_text = render_yaml(tracked_repos, permissions_list)
    repos_path.write_text(new_text, encoding="utf-8")

    print(f"Wrote repos.yaml with {len(tracked_repos)} tracked repositories and {len(permissions_list)} permission sets.")


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def auth_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }


def create_session(token):
    """Create a requests session with retry logic and exponential backoff."""
    session = requests.Session()
    retries = Retry(
        total=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_FORCELIST,
        respect_retry_after_header=True
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update(auth_headers(token))
    return session


def load_tracked_repos(path):
    """Load the list of repositories to track from repos.yaml"""
    try:
        text = path.read_text(encoding="utf-8")
        cfg = yaml.safe_load(text) or {}
    except FileNotFoundError:
        cfg = {}
    
    tracked = cfg.get("tracked_repos", [])
    if not isinstance(tracked, list):
        return []
    
    return [r.strip() for r in tracked if isinstance(r, str) and r.strip()]


def fetch_repo_permissions(org, repo_name, session):
    """Fetch permissions for a specific repository."""
    repo_data = {repo_name: {}}
    
    # Fetch team permissions
    team_permissions = fetch_team_permissions(org, repo_name, session)
    
    # Fetch collaborator permissions (individual users)
    user_permissions = fetch_collaborator_permissions(org, repo_name, session)
    
    # Organize by permission level
    for permission_level in TRACKED_PERMISSIONS:
        teams = team_permissions.get(permission_level, [])
        users = user_permissions.get(permission_level, [])
        
        # Only add the permission level if there are teams or users
        if teams or users:
            level_data = {}
            if teams:
                level_data["teams"] = sorted(teams)
            if users:
                level_data["users"] = sorted(users)
            repo_data[repo_name][permission_level] = level_data
    
    # Only return repo data if there are any permissions to track
    if repo_data[repo_name]:
        return repo_data
    return None


def fetch_team_permissions(org, repo_name, session):
    """Fetch team permissions for a repository."""
    permissions_by_level = {level: [] for level in TRACKED_PERMISSIONS}
    
    try:
        teams = paginate(f"{API}/repos/{org}/{repo_name}/teams", session)
        
        for team in teams:
            permission = team.get("permission")
            team_slug = team.get("slug")
            
            if permission in TRACKED_PERMISSIONS and team_slug:
                permissions_by_level[permission].append(team_slug)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Warning: Repository {org}/{repo_name} not found or not accessible")
        else:
            raise
    
    return permissions_by_level


def fetch_collaborator_permissions(org, repo_name, session):
    """Fetch direct collaborator (user) permissions for a repository."""
    permissions_by_level = {level: [] for level in TRACKED_PERMISSIONS}
    
    try:
        # Fetch collaborators with affiliation=direct to get only direct collaborators
        # (not those who have access through team membership)
        collaborators = paginate(
            f"{API}/repos/{org}/{repo_name}/collaborators",
            session,
            params={"affiliation": "direct"}
        )
        
        for collab in collaborators:
            # Get the permission object which contains role_name
            permissions = collab.get("permissions", {})
            login = collab.get("login")
            
            if not login:
                continue
            
            # Determine the highest permission level
            # GitHub API returns permissions as booleans
            if permissions.get("admin"):
                permission_level = "admin"
            elif permissions.get("maintain"):
                permission_level = "maintain"
            elif permissions.get("push"):  # "push" permission = "write" access
                permission_level = "write"
            elif permissions.get("triage"):
                permission_level = "triage"
            else:
                # "pull" permission = "read" access, which we don't track
                continue
            
            if permission_level in TRACKED_PERMISSIONS:
                permissions_by_level[permission_level].append(login)
                
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Warning: Repository {org}/{repo_name} not found or not accessible")
        else:
            raise
    
    return permissions_by_level


def render_yaml(tracked_repos, permissions_list):
    """Render the repos.yaml content."""
    # Build the document structure
    doc = {
        "tracked_repos": tracked_repos,
        "permissions": permissions_list
    }
    
    # Convert to YAML
    yaml_text = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, allow_unicode=True)
    
    # Add header comments using COMMENT constant for consistency
    header = (
        COMMENT +
        "# This file tracks write-level (and above) permissions for selected repositories.\n"
        "# \n"
        "# To track a repository, add it to the tracked_repos list below.\n"
        "# The permissions section is automatically updated by the workflow.\n\n"
    )
    
    return header + yaml_text


def paginate(url, session, params=None):
    """GitHub REST pagination: keep fetching until the short page."""
    out, page = [], 1
    base_params = params or {}
    
    while True:
        page_params = {**base_params, "per_page": PER_PAGE, "page": page}
        r = session.get(url, params=page_params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        batch = r.json()
        out.extend(batch)
        if len(batch) < PER_PAGE:
            break
        page += 1
    return out


if __name__ == "__main__":
    main()
