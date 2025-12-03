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
            help="Repository name",
        ),
    ] = "",
    description: Annotated[
        str,
        typer.Option(
            "--description",
            "-d",
            help="Repository description",
        ),
    ] = "",
    private: Annotated[
        bool,
        typer.Option(
            "--private/--public",
            help="Repository visibility",
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
    template: Annotated[
        str,
        typer.Option(
            "--template",
            "-t",
            help="Template repository",
        ),
    ] = "wildlife-dynamics/wt-template",
    collaborators: Annotated[
        str,
        typer.Option(
            "--collaborators",
            "-c",
            help="Comma-separated list of collaborators (format: user1:role1,user2:role2)",
        ),
    ] = "",
    skip_collaborators: Annotated[
        bool,
        typer.Option(
            "--skip-collaborators",
            help="Skip adding collaborators",
        ),
    ] = False,
    branch_rules: Annotated[
        str,
        typer.Option(
            "--branch-rules",
            "-b",
            help="Path to branch rules JSON file",
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
            help="Verbose output",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview without executing",
        ),
    ] = False,
) -> None:
    """
    Create a new repository from template with collaborators and branch protection.

    Interactive mode is used by default when options are not provided.
    """
    from wt.commands.create import create_repository

    create_repository(
        name=name,
        description=description,
        private=private,
        org=org,
        template=template,
        collaborators=collaborators,
        skip_collaborators=skip_collaborators,
        branch_rules=branch_rules,
        skip_branch_rules=skip_branch_rules,
        verbose=verbose,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    app()
