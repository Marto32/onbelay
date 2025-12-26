"""Rich console utilities for terminal output."""

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.theme import Theme

# Custom theme for harness output
HARNESS_THEME = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red bold",
    "heading": "bold magenta",
    "muted": "dim",
    "feature": "bold blue",
    "session": "bold cyan",
})

# Global console instance
console = Console(theme=HARNESS_THEME)


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[info]{message}[/info]")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[success]{message}[/success]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[warning]Warning: {message}[/warning]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[error]Error: {message}[/error]")


def print_heading(title: str) -> None:
    """Print a section heading."""
    console.print(f"\n[heading]{title}[/heading]")
    console.print("[muted]" + "-" * len(title) + "[/muted]")


def print_panel(content: str, title: str = "", style: str = "info") -> None:
    """Print content in a panel."""
    console.print(Panel(content, title=title, border_style=style))


def print_key_value(key: str, value: str, key_width: int = 20) -> None:
    """Print a key-value pair."""
    console.print(f"[muted]{key:<{key_width}}[/muted] {value}")


def create_status_table(title: str = "Status") -> Table:
    """Create a table for displaying status information."""
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Property", style="muted")
    table.add_column("Value")
    return table


def create_feature_table(title: str = "Features") -> Table:
    """Create a table for displaying features."""
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Category", style="cyan")
    table.add_column("Description")
    table.add_column("Status", justify="center")
    table.add_column("Size", justify="center", width=8)
    return table


def create_progress_spinner(description: str = "Working...") -> Progress:
    """Create a progress spinner for long-running operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    )


def create_progress_bar(description: str = "Progress") -> Progress:
    """Create a progress bar for operations with known steps."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def confirm(prompt: str, default: bool = False) -> bool:
    """Prompt for confirmation."""
    default_str = "Y/n" if default else "y/N"
    response = console.input(f"[info]{prompt}[/info] [{default_str}]: ")
    if not response:
        return default
    return response.lower() in ("y", "yes")


def format_cost(amount: float) -> str:
    """Format a cost value."""
    return f"${amount:.2f}"


def format_percentage(value: float) -> str:
    """Format a percentage value."""
    return f"{value * 100:.1f}%"


def format_feature_status(passes: bool, in_progress: bool = False) -> str:
    """Format feature status for display."""
    if in_progress:
        return "[yellow]IN PROGRESS[/yellow]"
    elif passes:
        return "[success]PASS[/success]"
    else:
        return "[muted]PENDING[/muted]"


def format_health_status(score: float) -> str:
    """Format health score for display."""
    if score >= 0.8:
        return f"[success]GOOD ({format_percentage(score)})[/success]"
    elif score >= 0.5:
        return f"[warning]FAIR ({format_percentage(score)})[/warning]"
    else:
        return f"[error]POOR ({format_percentage(score)})[/error]"
