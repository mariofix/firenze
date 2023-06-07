import logging.config

import typer

from ..config import LOGGING_CONFIG_CLI
from ..models import FonoTarotLatamClient
from .utils import set_asterisk_var, verbose

logging.config.dictConfig(LOGGING_CONFIG_CLI)
logger = logging.getLogger("firenze-cli")
app = typer.Typer()


@app.command("pin")
def search_pin(
    ctx: typer.Context,
    pin: int = typer.Argument(..., help="Returns PIN information"),
):
    """
    Search the PIN, returns the relevant information.
    """
    session = ctx.obj.get("dbsession")
    agi = ctx.obj.get("agi")
    
    pin_info = session.query(FonoTarotLatamClient).filter_by(pin_code=pin).first()
    
    if pin_info:
        set_asterisk_var(agi, "clientid", int(pin_info.client_id))
        verbose(agi, f"clientid={int(pin_info.client_id)}")
        set_asterisk_var(agi, "segundos", int(pin_info.credits))
        verbose(agi, f"segundos={int(pin_info.credits)}")
        raise typer.Exit(code=0)
    else:
        logger.warn(f"The PIN {pin} does not exist.")
        set_asterisk_var(agi, "clientid", 0)
        verbose(agi, f"clientid=0")
        set_asterisk_var(agi, "segundos", 0)
        verbose(agi, f"segundos=0")
        raise typer.Exit(code=1)

@app.command("consumo")
def use_credits(
    ctx: typer.Context,
    client_id: int = typer.Argument(..., help="Client ID"),
    used_credits: int = typer.Argument(..., help="Used credits"),
):
    """
    Deducts credits from clientid
    """
    session = ctx.obj.get("dbsession")
    agi = ctx.obj.get("agi")

    client = session.query(FonoTarotLatamClient).filter_by(client_id=client_id).first()
    if not client:
        logger.warn(f"The {client_id=} does not exist.")
        raise typer.Abort()
    new_credits = int(int(client.credits) - used_credits)
    logger.info(f"{client_id=} {new_credits=}.")
    client.credits = new_credits
    session.commit()
    raise typer.Exit(code=0)