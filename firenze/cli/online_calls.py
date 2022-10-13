from firenze.config import LOGGING_CONFIG
from firenze.models import OnlineCalls
from sqlalchemy import delete, update
import logging.config
import typer

logging.config.dictConfig(LOGGING_CONFIG)
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
    engine = ctx.obj.get("dbengine")
    try:
        llamada = delete(OnlineCalls).where(
            OnlineCalls.service == service, OnlineCalls.ani == ani
        )
        engine.execute(llamada)
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)
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
    engine = ctx.obj.get("dbengine")
    try:
        llamada = (
            update(OnlineCalls)
            .where(OnlineCalls.service == service, OnlineCalls.ani == ani)
            .values(operator=operator)
        )
        engine.execute(llamada)
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)
    else:
        logger.debug(f"Updated {service=} AND {ani=} with {operator=}")
