import logging.config

import typer


from firenze.config import LOGGING_CONFIG
from firenze.models import ServiceNumber

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("firenze")
app = typer.Typer()


@app.command("did")
def search_did(
    ctx: typer.Context,
    did: str = typer.Argument(..., help="DID to check, can be a number or a string"),
):
    """
    Search the DID, returns/prints the asterisk context.
    """
    session = ctx.obj.get("dbsession")
    agi = ctx.obj.get("agi")
    number = session.query(ServiceNumber).filter_by(did=did, active=True).first()

    if number:
        logger.info(f"{number=}")
        raise typer.Exit(code=0)
    else:
        logger.warn(f"The DID {did} is not registered.")
        raise typer.Exit(code=0)
