import logging.config

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from sqlalchemy import delete, select, update

from firenze.config import LOGGING_CONFIG_CLI
from firenze.database import SessionLocal, engine
from firenze.models import PostCallProcess

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
    texto = "Los%20astros%20han%20hablado%21%20Gracias%20por%20tu%20llamada%20ahora%20queremos%20pedirte%20si%20nos%20puedes%20regalar%201%20minuto%20para%20contestar%203%20preguntas.%20https%3A%2F%2Fopinion.fonotarot.cl%2Fform%2FR1Ww1d"
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
