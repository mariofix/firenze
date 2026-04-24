"""Online call tracking CLI commands (debug)."""

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from firenze.models import OnlineCalls
from firenze.services.call_service import delete_call

app = typer.Typer()


@app.command("list")
def list_calls(
    ctx: typer.Context,
    service: str = typer.Argument(None, help="Filter by service slug"),
):
    """Show current online calls."""
    session = ctx.obj.get("dbsession")
    query = session.query(OnlineCalls)
    if service:
        query = query.filter_by(service=service)
    calls = query.all()

    table = Table(title="Online Calls", box=box.ASCII2)
    table.add_column("ID")
    table.add_column("Service")
    table.add_column("ANI")
    table.add_column("DID")
    table.add_column("Operator")
    table.add_column("Client ID")
    table.add_column("Since")

    for call in calls:
        table.add_row(
            str(call.id),
            call.service,
            call.ani,
            call.did,
            str(call.operator),
            str(call.client_id),
            str(call.created_at),
        )

    Console().print(table)


@app.command("clear")
def clear_calls(
    ctx: typer.Context,
    service: str = typer.Argument(None, help="Clear only this service (all if omitted)"),
    confirm: bool = typer.Option(False, "--yes", help="Skip confirmation"),
):
    """Clear stale online call records from MySQL and Redis."""
    session = ctx.obj.get("dbsession")
    redis_conn = ctx.obj.get("redis")

    query = session.query(OnlineCalls)
    if service:
        query = query.filter_by(service=service)

    calls = query.all()
    count = len(calls)
    if count == 0:
        typer.echo("No online calls to clear")
        return

    label = f"{count} calls" + (f" for {service}" if service else "")
    if not confirm:
        typer.confirm(f"Delete {label}?", abort=True)

    for call in calls:
        delete_call(session, call.service, call.ani, redis_conn)

    typer.echo(f"Cleared {label}")
