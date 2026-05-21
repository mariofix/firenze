"""Comandos CLI de lista de No Llamar."""

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from firenze.models import DoNotCall
from firenze.services.dnc_service import check_dnc

app = typer.Typer()


@app.command("check")
def check(
    ctx: typer.Context,
    ani: str = typer.Argument(..., help="Phone number to check"),
):
    """Check if a number is in the DNC list."""
    session = ctx.obj.get("dbsession")
    if check_dnc(session, ani):
        typer.echo(f"{ani} IS in the Do Not Call list")
        raise typer.Exit(code=1)
    typer.echo(f"{ani} is NOT in the Do Not Call list")


@app.command("add")
def add(
    ctx: typer.Context,
    ani: str = typer.Argument(..., help="Phone number to block"),
    reason: str = typer.Option(..., prompt="Reason"),
):
    """Add a number to the DNC list."""
    session = ctx.obj.get("dbsession")
    if check_dnc(session, ani):
        typer.echo(f"{ani} is already in the DNC list", err=True)
        raise typer.Exit(code=1)

    entry = DoNotCall(ani=ani, reason=reason)
    session.add(entry)
    session.commit()
    typer.echo(f"Added {ani} to DNC list")


@app.command("remove")
def remove(
    ctx: typer.Context,
    ani: str = typer.Argument(..., help="Phone number to unblock"),
):
    """Remove a number from the DNC list."""
    session = ctx.obj.get("dbsession")
    entry = session.query(DoNotCall).filter_by(ani=ani).first()
    if not entry:
        typer.echo(f"{ani} is not in the DNC list", err=True)
        raise typer.Exit(code=1)

    session.delete(entry)
    session.commit()
    typer.echo(f"Removed {ani} from DNC list")


@app.command("list")
def list_dnc(ctx: typer.Context):
    """Show all DNC entries."""
    session = ctx.obj.get("dbsession")
    entries = session.query(DoNotCall).all()

    table = Table(title="Do Not Call List", box=box.ASCII2)
    table.add_column("ANI")
    table.add_column("Reason")
    table.add_column("Added")

    for e in entries:
        table.add_row(e.ani, e.reason, str(e.created_at))

    Console().print(table)
