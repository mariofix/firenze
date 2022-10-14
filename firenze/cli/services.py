from firenze.config import LOGGING_CONFIG_CLI
from firenze.models import ServiceNumber
from firenze.cli.utils import verbose, set_asterisk_var
import logging.config
import typer

logging.config.dictConfig(LOGGING_CONFIG_CLI)
logger = logging.getLogger("firenze-cli")
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
        set_asterisk_var(agi, "siguiente", number.asterisk_context)
        verbose(agi, f"Se encontró el contexto {number.asterisk_context}")
        raise typer.Exit(code=0)
    else:
        logger.warn(f"The DID {did} is not registered.")
        set_asterisk_var(agi, "siguiente", "no-service")
        verbose(agi, f"The DID {did} is not registered.")
        raise typer.Exit(code=0)
