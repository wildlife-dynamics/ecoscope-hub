"""Main CLI application."""

import typer
from typing_extensions import Annotated

from wt import __version__
from wt.ui.console import console

app = typer.Typer(
    name="wt",
    help="Ecoscope Workflow Management CLI - Tool for managing ecoscope repositories",
    add_completion=False,
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"wt version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Ecoscope Workflow Management CLI."""
    pass


@app.command()
def create(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Repository name (must start with 'wt-', e.g., 'wt-my-workflow')",
        ),
    ] = "",
    description: Annotated[
        str,
        typer.Option(
            "--description",
            "-d",
            help="Short description of the workflow repository",
        ),
    ] = "",
    private: Annotated[
        bool,
        typer.Option(
            "--private/--public",
            help="Repository visibility (default: private)",
        ),
    ] = True,
    org: Annotated[
        str,
        typer.Option(
            "--org",
            "-o",
            help="Organization name (leave empty for personal repo)",
        ),
    ] = "",
    collaborators: Annotated[
        str,
        typer.Option(
            "--collaborators",
            "-c",
            help="Comma-separated list: 'user1:role1,user2:role2'. Roles: read, write, admin, maintain, triage",
        ),
    ] = "",
    skip_collaborators: Annotated[
        bool,
        typer.Option(
            "--skip-collaborators",
            help="Skip the collaborator addition step",
        ),
    ] = False,
    branch_rules: Annotated[
        str,
        typer.Option(
            "--branch-rules",
            "-b",
            help="Path to JSON file with branch protection rules (e.g., repo-setup/ecoscope_main_branch_rules.json)",
        ),
    ] = "",
    skip_branch_rules: Annotated[
        bool,
        typer.Option(
            "--skip-branch-rules",
            help="Skip applying branch protection rules",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Show detailed output for debugging",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview actions without making changes",
        ),
    ] = False,
) -> None:
    """
    Create a new ecoscope workflow repository from template.

    Creates a repository from wildlife-dynamics/wt-template with optional
    collaborators and branch protection rules.

    Examples:

        # Interactive mode
        wt create

        # Create with all options
        wt create --name wt-my-workflow --description "My workflow" --private

        # Create with collaborators
        wt create --name wt-my-workflow --collaborators "user1:admin,user2:write"

        # Preview without creating
        wt create --name wt-my-workflow --dry-run
    """
    from wt.commands.create import create_repository

    create_repository(
        name=name,
        description=description,
        private=private,
        org=org,
        collaborators=collaborators,
        skip_collaborators=skip_collaborators,
        branch_rules=branch_rules,
        skip_branch_rules=skip_branch_rules,
        verbose=verbose,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    app()
