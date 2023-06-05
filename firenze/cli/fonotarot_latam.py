import logging.config

import typer

from .utils import set_asterisk_var, verbose
from ..config import LOGGING_CONFIG_CLI
from ..models import FonoTarotLatamClient


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
