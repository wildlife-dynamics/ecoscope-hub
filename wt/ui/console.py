"""Rich console utilities for beautiful terminal output."""

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.theme import Theme

# Custom theme for wt CLI
custom_theme = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red bold",
    "dim": "dim",
})

# Global console instance
console = Console(theme=custom_theme)


def print_header(text: str) -> None:
    """Print a formatted header."""
    console.print()
    console.print(Panel(text, style="bold cyan"))
    console.print()


def print_success(text: str) -> None:
    """Print a success message."""
    console.print(f"✓ {text}", style="success")


def print_error(text: str) -> None:
    """Print an error message."""
    console.print(f"✗ {text}", style="error")


def print_warning(text: str) -> None:
    """Print a warning message."""
    console.print(f"⚠ {text}", style="warning")


def print_info(text: str) -> None:
    """Print an info message."""
    console.print(f"ℹ {text}", style="info")


def print_step(step: int, total: int, title: str) -> None:
    """Print a step header."""
    console.print()
    console.print(f"[bold cyan][{step}/{total}] {title}[/bold cyan]")


def confirm(question: str, default: bool = True) -> bool:
    """Ask for confirmation."""
    return Confirm.ask(question, default=default)


def ask(question: str, default: str = "") -> str:
    """Ask for user input."""
    return Prompt.ask(question, default=default)


def ask_password(question: str) -> str:
    """Ask for password/token input."""
    return Prompt.ask(question, password=True)


def create_table(title: str, columns: list[str]) -> Table:
    """Create a formatted table."""
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for column in columns:
        table.add_column(column)
    return table


def create_progress() -> Progress:
    """Create a progress spinner."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    )
