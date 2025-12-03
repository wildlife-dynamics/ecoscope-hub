"""Repository creation command."""

import json
from pathlib import Path
from typing import Optional

import requests
from github import Github

from wt.auth import create_github_client
from wt.ui.console import (
    ask,
    confirm,
    console,
    create_progress,
    print_error,
    print_header,
    print_info,
    print_step,
    print_success,
    print_warning,
)

# Valid GitHub repository permission levels
# Note: GitHub API uses 'pull' and 'push' internally, but we expose as 'read' and 'write'
VALID_ROLES = {
    "read": "pull",      # Read-only access
    "write": "push",     # Read + Write access
    "admin": "admin",    # Full admin access
    "maintain": "maintain",  # Manage without admin
    "triage": "triage",  # Manage issues/PRs
}

# For backward compatibility, also accept GitHub's internal names
ROLE_ALIASES = {
    "pull": "pull",
    "push": "push",
}


def create_repository(
    name: str,
    description: str,
    private: bool,
    org: str,
    collaborators: str,
    skip_collaborators: bool,
    dry_run: bool,
) -> None:
    """
    Create a new repository from template.

    Args:
        name: Repository name
        description: Repository description
        private: Make repository private
        org: Organization name
        collaborators: Comma-separated collaborators
        skip_collaborators: Skip adding collaborators
        dry_run: Preview without executing
    """
    # Template and branch rules are always the same
    template = "wildlife-dynamics/wt-template"
    # Branch rules URL - always fetch from GitHub
    branch_rules_url = "https://raw.githubusercontent.com/wildlife-dynamics/ecoscope-hub/main/repo-setup/ecoscope_main_branch_rules.json"
    print_header("Ecoscope Workflow Repository Creator")

    # Interactive mode if name not provided
    interactive = not name

    if interactive:
        print_step(1, 4, "Repository Details")

        # Ask for repository name with validation
        console.print("[dim]Repository name must start with 'wt-' (e.g., wt-my-workflow)[/dim]")
        while True:
            name = ask("Repository name")
            if not name:
                console.print("[yellow]Repository name cannot be empty[/yellow]")
                continue
            if not name.startswith("wt-"):
                console.print(f"[yellow]Repository name must start with 'wt-' (got: '{name}')[/yellow]")
                console.print("[dim]Example: wt-my-workflow, wt-elephant-tracking[/dim]")
                continue
            break

        description = ask("Repository description", default="")
        private = confirm("Make repository private?", default=True)

        # Ask for organization with warning
        console.print()
        console.print("[yellow]⚠  You must have admin permission in the organization to create repositories[/yellow]")
        console.print("[dim]Press Enter for personal repository, or type organization name (e.g., wildlife-dynamics)[/dim]")
        org = ask("Organization", default="")
    else:
        console.print("[dim]Non-interactive mode[/dim]")

    # Validate inputs
    if not name:
        print_error("Repository name is required")
        raise SystemExit(1)

    # Validate name starts with wt-
    if not name.startswith("wt-"):
        print_error(f"Repository name must start with 'wt-' (got: '{name}')")
        console.print("[dim]Example: wt-my-workflow, wt-elephant-tracking[/dim]")
        raise SystemExit(1)

    # Display summary
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Name: [cyan]{name}[/cyan]")
    console.print(f"  Description: [cyan]{description or '(none)'}[/cyan]")
    console.print(f"  Visibility: [cyan]{'Private' if private else 'Public'}[/cyan]")
    console.print(f"  Owner: [cyan]{org or 'Personal'}[/cyan]")
    console.print(f"  Template: [cyan]{template}[/cyan]")
    console.print()

    if dry_run:
        console.print("[yellow]Dry run - no changes will be made[/yellow]")
        return

    # Create GitHub client and get current user
    client = create_github_client()
    current_user = client.get_user().login

    # Parse collaborators and add current user as admin by default
    collab_list = []
    if not skip_collaborators:
        if collaborators:
            for collab in collaborators.split(","):
                collab = collab.strip()
                if ":" in collab:
                    username, role = collab.split(":", 1)
                    role = role.strip().lower()
                    # Map user-friendly names to GitHub API names
                    api_role = VALID_ROLES.get(role, ROLE_ALIASES.get(role, role))
                    collab_list.append((username.strip(), api_role))

        # Add current user as admin if not already in the list
        if not any(username == current_user for username, _ in collab_list):
            collab_list.insert(0, (current_user, "admin"))
            print_info(f"Adding current user [bold]{current_user}[/bold] as admin")

    console.print()
    print_step(2, 4, "Creating Repository")

    try:
        # Parse template owner/repo
        template_owner, template_repo = template.split("/", 1)

        # Get template repository
        with create_progress() as progress:
            task = progress.add_task("Fetching template repository...", total=None)
            template_repo_obj = client.get_repo(template)
            progress.update(task, completed=True)

        # Create repository from template
        with create_progress() as progress:
            task = progress.add_task(f"Creating repository {name}...", total=None)

            if org:
                # Create in organization
                org_obj = client.get_organization(org)
                new_repo = org_obj.create_repo_from_template(
                    name=name,
                    repo=template_repo_obj,
                    description=description,
                    private=private,
                )
            else:
                # Create in personal account
                user = client.get_user()
                new_repo = user.create_repo_from_template(
                    name=name,
                    repo=template_repo_obj,
                    description=description,
                    private=private,
                )

            progress.update(task, completed=True)

        print_success(f"Repository created: [bold]{new_repo.full_name}[/bold]")
        console.print(f"  [dim]→[/dim] {new_repo.html_url}")

    except Exception as e:
        print_error(f"Failed to create repository: {e}")
        raise SystemExit(1)

    # Add collaborators
    if collab_list and not skip_collaborators:
        console.print()
        print_step(3, 4, "Adding Collaborators")

        # Get repository owner to skip them
        repo_owner = new_repo.owner.login

        for username, role in collab_list:
            # Skip if user is the repository owner
            if username.lower() == repo_owner.lower():
                print_info(f"Skipping [bold]{username}[/bold] (repository owner)")
                continue

            try:
                with create_progress() as progress:
                    task = progress.add_task(f"Adding {username} as {role}...", total=None)
                    new_repo.add_to_collaborators(username, permission=role)
                    progress.update(task, completed=True)
                print_success(f"Added [bold]{username}[/bold] ({role})")
            except Exception as e:
                print_error(f"Failed to add {username}: {e}")
                import traceback
                console.print(f"  [dim]{traceback.format_exc()}[/dim]")

    # Apply branch protection rules (only for organization repos)
    # Note: Repository rulesets require GitHub Pro for personal accounts
    console.print()
    print_step(4, 4, "Applying Branch Protection Rules")

    if not org:
        print_info("Skipping branch protection rules (personal repository)")
        console.print("[dim]Private repository rulesets require GitHub Pro for personal accounts[/dim]")
        console.print("[dim]You can manually add branch protection in Settings → Branches[/dim]")
    else:
        try:
            # Fetch rules from GitHub
            with create_progress() as progress:
                task = progress.add_task("Fetching branch rules from GitHub...", total=None)
                rules_response = requests.get(branch_rules_url)
                progress.update(task, completed=True)

            if rules_response.status_code != 200:
                print_error(f"Failed to fetch branch rules from GitHub: {rules_response.status_code}")
                print_info("Skipping branch protection rules")
            else:
                rules_data = rules_response.json()

                # Apply ruleset using GitHub REST API
                # PyGithub doesn't support rulesets yet, so we use requests directly
                token = client._Github__requester._Requester__auth.token
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }

                # Prepare ruleset payload
                ruleset_payload = {
                    "name": rules_data.get("name", "Main Branch Rules"),
                    "target": rules_data.get("target", "branch"),
                    "enforcement": rules_data.get("enforcement", "active"),
                    "conditions": rules_data.get("conditions", {}),
                    "rules": rules_data.get("rules", []),
                    "bypass_actors": rules_data.get("bypass_actors", []),
                }

                # Create ruleset
                api_url = f"https://api.github.com/repos/{new_repo.full_name}/rulesets"

                with create_progress() as progress:
                    task = progress.add_task("Creating branch protection ruleset...", total=None)
                    response = requests.post(api_url, headers=headers, json=ruleset_payload)
                    progress.update(task, completed=True)

                if response.status_code == 201:
                    print_success("Branch protection rules applied")
                else:
                    print_error(f"Failed to apply branch rules: {response.status_code}")
                    console.print(f"  [dim]{response.text}[/dim]")

        except Exception as e:
            print_error(f"Failed to apply branch protection rules: {e}")
            import traceback
            console.print(f"  [dim]{traceback.format_exc()}[/dim]")

    console.print()
    print_success("Repository setup complete!")
    console.print(f"  [dim]→[/dim] {new_repo.html_url}")
