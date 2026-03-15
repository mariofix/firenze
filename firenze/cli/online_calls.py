import logging.config

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from sqlalchemy import delete, select, update

from firenze.config import LOGGING_CONFIG_CLI
from firenze.database import SessionLocal, engine
from firenze.models import OnlineCalls

logging.config.dictConfig(LOGGING_CONFIG_CLI)
logger = logging.getLogger("firenze-cli")
app = typer.Typer()


@app.command("insert")
def insert_online_call(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service slug"),
    ani: str = typer.Argument(..., help="ANI"),
    did: str = typer.Argument(..., help="DID"),
    operator: int = typer.Argument(..., help="Operator Number"),
    client_id: int = typer.Argument(..., help="client_id"),
):
    """
    Inserts a record in OnlineCalls
    """
    session = ctx.obj.get("dbsession")
    try:
        llamada = OnlineCalls(
            service=service, ani=ani, did=did, operator=operator, client_id=client_id
        )
        session.add(llamada)
        session.commit()
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)
    else:
        session.refresh(llamada)
        logger.debug(f"{llamada.service=}, {llamada.ani=}, {llamada.client_id=}")


@app.command("delete")
def delete_online_call(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service slug"),
    ani: str = typer.Argument(..., help="ANI"),
):
    """
    Deletes a record from OnlineCalls
    """
    session = SessionLocal()
    try:
        busca = select(OnlineCalls).where(
            OnlineCalls.service == service, OnlineCalls.ani == ani
        )
        llamada = session.scalars(busca).first()
        session.delete(llamada)
        session.commit()
    except Exception as e:
        logger.warn(e)
        raise typer.Exit(code=10)
    else:
        logger.debug(f"Deleted: {service=} AND {ani=}")


@app.command("update")
def update_online_call(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service slug"),
    ani: str = typer.Argument(..., help="ANI"),
    operator: int = typer.Argument(..., help="Operator Number"),
):
    """
    Updates the operator of a record in OnlineCalls
    """
    session = SessionLocal()
    try:
        busca = select(OnlineCalls).where(
            OnlineCalls.service == service, OnlineCalls.ani == ani
        )
        llamada = session.scalars(busca).first()
        llamada.operator = operator

        session.commit()
    except Exception as e:
        logger.warn(e)
        raise typer.Exit(code=1)
    else:
        logger.debug(f"Updated {service=} AND {ani=} with {operator=}")


@app.command("list")
def list_online_call(
    ctx: typer.Context,
    service: str = typer.Argument(None, help="Service slug"),
):
    """
    Show the current calls
    """
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    calls = session.query(OnlineCalls)
    if service:
        calls = calls.filter_by(service=service)
    calls = calls.all()

    table = Table(title="On Line Calls", highlight=True, box=box.ASCII2)

    table.add_column("ID")
    table.add_column("Date")
    table.add_column("Service")
    table.add_column("client_id")
    table.add_column("ANI")
    table.add_column("DID")
    table.add_column("Operator")

    for call in calls:
        table.add_row(
            str(call.id),
            str(call.created_at),
            call.service,
            str(call.client_id),
            call.ani,
            call.did,
            str(call.operator),
        )

    console = Console()
    console.print(table)
