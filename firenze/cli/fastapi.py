"""FastAPI inspection CLI commands."""

import os

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from firenze import create_app
from firenze.config import Settings

app = typer.Typer()

REDACT_PATTERNS = {"password", "secret", "key", "token", "dsn"}


def _should_redact(name: str) -> bool:
    lower = name.lower()
    return any(p in lower for p in REDACT_PATTERNS)


@app.command("routes")
def routes(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show response model and tags"),
):
    """Show all registered routes in the FastAPI app."""
    application = create_app()
    items = []

    for route in application.routes:
        if not hasattr(route, "methods"):
            continue
        methods = ", ".join(sorted(route.methods - {"HEAD", "OPTIONS"}))
        if not methods:
            continue
        items.append(
            {
                "methods": methods,
                "path": route.path,
                "name": route.name or "",
                "tags": ", ".join(getattr(route, "tags", []) or []),
                "response_model": getattr(route, "response_model", None),
            }
        )

    items.sort(key=lambda r: r["path"])

    table = Table(title="Registered Routes", box=box.ASCII2)
    table.add_column("Methods", style="bold")
    table.add_column("Path")
    table.add_column("Name")
    if verbose:
        table.add_column("Tags")
        table.add_column("Response Model")

    for r in items:
        row = [r["methods"], r["path"], r["name"]]
        if verbose:
            row.append(r["tags"])
            model = r["response_model"]
            row.append(model.__name__ if model else "—")
        table.add_row(*row)

    console = Console()
    console.print(table)
    console.print(f"\n[dim]{len(items)} routes registered[/dim]")


@app.command("config")
def config(
    reveal: bool = typer.Option(False, "--reveal", help="Show sensitive values unmasked"),
):
    """Print current application configuration."""
    settings = Settings()

    table = Table(title="Application Config", box=box.ASCII2)
    table.add_column("Key")
    table.add_column("Value")
    table.add_column("Source", style="dim")

    for name in sorted(settings.model_fields):
        value = getattr(settings, name)
        display = str(value)

        if _should_redact(name) and not reveal:
            display = "****" if value else "(empty)"

        source = "env" if name.upper() in os.environ else "default"
        table.add_row(name, display, source)

    Console().print(table)


@app.command("config-env")
def config_env():
    """Output config as .env format (for backup/migration)."""
    settings = Settings()

    for name in sorted(settings.model_fields):
        value = getattr(settings, name)
        if _should_redact(name):
            typer.echo(f"# {name.upper()}=****")
        else:
            typer.echo(f"{name.upper()}={value}")
