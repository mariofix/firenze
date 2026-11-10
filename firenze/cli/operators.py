"""CLI de administración de operadores — envoltorio delgado sobre operator_service."""

import logging
import logging.config

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from firenze.config import LOGGING_CONFIG
from firenze.services.operator_service import OperatorNotFound, set_availability
from firenze.services.operator_service import login as svc_login
from firenze.services.operator_service import logout as svc_logout

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("firenze")
app = typer.Typer()


@app.command("login")
def login(ctx: typer.Context, number: int = typer.Argument(..., help="Operator Number")):
    """Mark operator as logged in and available."""
    session = ctx.obj.get("dbsession")
    try:
        op = svc_login(session, number)
        logger.info(f"Login: {op}")
    except OperatorNotFound as e:
        logger.error(str(e))
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


@app.command("logout")
def logout(ctx: typer.Context, number: int = typer.Argument(..., help="Operator Number")):
    """Mark operator as logged out and unavailable."""
    session = ctx.obj.get("dbsession")
    try:
        op = svc_logout(session, number)
        logger.info(f"Logout: {op}")
    except OperatorNotFound as e:
        logger.error(str(e))
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


@app.command("change-status")
def change_status(
    ctx: typer.Context,
    number: int = typer.Option(..., help="Operator Number"),
    status: int = typer.Option(..., help="Availability: 1=available, 0=unavailable"),
):
    """Set operator availability without changing login state."""
    session = ctx.obj.get("dbsession")
    try:
        op = set_availability(session, number, bool(status))
        logger.info(f"Status change: {op}")
    except OperatorNotFound as e:
        logger.error(str(e))
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


@app.command("list")
def list_operators(ctx: typer.Context):
    """List all operators with DB state."""
    from firenze.models import Operator

    session = ctx.obj.get("dbsession")
    operators = session.query(Operator).all()

    table = Table(title="Operators", highlight=True, box=box.ASCII2)
    table.add_column("Number")
    table.add_column("Name")
    table.add_column("IVR Option")
    table.add_column("Phones")
    table.add_column("Last Call")
    table.add_column("Logged In")
    table.add_column("Available")

    for op in operators:
        table.add_row(
            str(op.number),
            str(op.name),
            str(op.option),
            "\n".join(f"{p.number}/E:{p.enabled}/C:{p.contact}/P:{p.pin}" for p in op.numbers),
            str(op.lastcall),
            str(op.loggedin),
            str(op.available),
        )

    Console().print(table)


@app.command("info")
def info(
    ctx: typer.Context,
    number: int = typer.Argument(..., help="Operator Number"),
):
    """Show a single operator's DB state."""
    from firenze.models import Operator

    session = ctx.obj.get("dbsession")

    op = session.query(Operator).filter_by(number=number).first()
    if not op:
        typer.echo(f"Operator {number} not found", err=True)
        raise typer.Exit(code=1)

    table = Table(title=f"Operator {op.number}", highlight=True, box=box.ASCII2)
    table.add_column("Field")
    table.add_column("DB")

    table.add_row("Name", str(op.name))
    table.add_row("IVR Option", str(op.option))
    table.add_row("Logged In", str(op.loggedin))
    table.add_row("Available", str(op.available))
    table.add_row("Last Call", str(op.lastcall))
    table.add_row(
        "Phones",
        "\n".join(f"{p.number}/E:{p.enabled}/C:{p.contact}/P:{p.pin}" for p in op.numbers),
    )

    Console().print(table)
