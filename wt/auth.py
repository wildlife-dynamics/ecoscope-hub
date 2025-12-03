"""GitHub authentication management."""

import os
from pathlib import Path
from typing import Optional

import yaml
from github import Auth, Github, GithubException

from wt.ui.console import ask_password, console, print_error, print_info, print_warning


# Default config directory and file
CONFIG_DIR = Path.home() / ".config" / "wt"
CONFIG_FILE = CONFIG_DIR / "config.yml"


def _read_stored_token() -> Optional[str]:
    """
    Read stored GitHub token from config file.

    Returns:
        Token if found, None otherwise.
    """
    if not CONFIG_FILE.exists():
        return None

    try:
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
            return config.get("github_token")
    except Exception:
        # Silently fail if we can't read the config
        return None


def _store_token(token: str) -> None:
    """
    Store GitHub token securely in config file.

    Args:
        token: GitHub personal access token to store.
    """
    # Create config directory if it doesn't exist
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Write token to config file
    config = {"github_token": token}
    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump(config, f)

    # Set secure permissions (owner read/write only)
    CONFIG_FILE.chmod(0o600)


def _prompt_for_token() -> str:
    """
    Prompt user for GitHub token with instructions.

    Returns:
        GitHub personal access token.
    """
    console.print()
    console.print("[bold]GitHub Token Required[/bold]")
    console.print()
    console.print("Create a token at: [link]https://github.com/settings/tokens/new[/link]")
    console.print()
    console.print("Required scopes:")
    console.print("  • [cyan]repo[/cyan] - Full control of private repositories")
    console.print("  • [cyan]admin:org[/cyan] - Full control of organizations (if creating org repos)")
    console.print()

    token = ask_password("Enter your GitHub token")
    console.print()

    return token


def get_github_token(force_prompt: bool = False) -> str:
    """
    Get GitHub token from environment or stored config.

    Priority:
    1. GITHUB_TOKEN environment variable
    2. GH_TOKEN environment variable
    3. Stored token in ~/.config/wt/config.yml
    4. Prompt user and store for future use

    Args:
        force_prompt: Force prompting for token (useful for expired tokens).

    Returns:
        GitHub personal access token.
    """
    if not force_prompt:
        # Check environment variables first
        if token := os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"):
            print_info("Using token from environment variable")
            return token

        # Check stored token
        if token := _read_stored_token():
            print_info(f"Using stored token from [dim]{CONFIG_FILE}[/dim]")
            return token

    # Prompt user and store token
    token = _prompt_for_token()
    _store_token(token)
    print_info(f"Token stored securely in [dim]{CONFIG_FILE}[/dim]")

    return token


def create_github_client(token: Optional[str] = None) -> Github:
    """
    Create authenticated GitHub client with token expiration handling.

    Args:
        token: Optional token. If not provided, will use get_github_token().

    Returns:
        Authenticated Github client.

    Raises:
        SystemExit: If authentication fails after retrying.
    """
    if token is None:
        token = get_github_token()

    auth = Auth.Token(token)
    client = Github(auth=auth)

    # Validate token by getting authenticated user
    try:
        user = client.get_user()
        login = user.login
        print_info(f"Authenticated as: [bold]{login}[/bold]")
        return client
    except GithubException as e:
        error_message = e.data.get("message", str(e)) if hasattr(e, "data") else str(e)

        # Check if token is expired or invalid
        if e.status in (401, 403):
            print_error(f"Authentication failed: {error_message}")
            print_warning("Your token may be expired or invalid.")
            console.print()

            # Prompt for new token
            new_token = _prompt_for_token()
            _store_token(new_token)
            print_info(f"New token stored in [dim]{CONFIG_FILE}[/dim]")

            # Retry with new token
            return create_github_client(token=new_token)
        else:
            # Other error, don't retry
            print_error(f"Authentication failed: {error_message}")
            raise SystemExit(1)
