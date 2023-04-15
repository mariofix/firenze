from firenze.config import LOGGING_CONFIG_CLI
from firenze.database import engine, SessionLocal
from firenze.models import PostCallProcess
from sqlalchemy import delete, update, select
import logging.config
import typer
from rich.console import Console
from rich.table import Table
from rich import box


logging.config.dictConfig(LOGGING_CONFIG_CLI)
logger = logging.getLogger("firenze-cli")
app = typer.Typer()


@app.command("add")
def post_call_add(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Associated Service"),
    client_id: int = typer.Argument(..., help="Client ID"),
    number: int = typer.Argument(..., help="Customer Number"),
    call_duration: int = typer.Argument(..., help="Call Duration"),
):
    """Add a Post Call Process"""
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    texto = "Los astros han hablado! Gracias por tu llamada, ahora queremos pedirte si nos puedes regalar 1 minuto para contestar 3 preguntas. https://opinion.fonotarot.cl/form/R1Ww1d"
    try:
        new_process = PostCallProcess(
            service=service,
            process_name="post_call_poll",
            client_id=client_id,
            processed=False,
            parameters={
                "destination": number,
                "text": texto,
                "duration": call_duration,
            },
        )
        session.add(new_process)
        session.commit()
        session.refresh(new_process)
    except Exception as e:
        logger.warn(e)
        raise typer.Exit(code=0)
    else:
        typer.echo(f"{new_process=}")
        logger.info(f"{new_process=}")

    raise typer.Exit(code=0)
