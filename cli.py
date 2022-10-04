#!//home/mariofix/proyectos/zvn-firenze/.venv/bin/python
import typer
import pystrix
from firenze.config import settings, LOGGING_CONFIG
from firenze.database import engine, SessionLocal
from firenze.models import Service, ServiceNumber, DoNotCall
from firenze.exceptions import GenericError, ProcessError
import logging.config

cli = typer.Typer()

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("firenze")
agi = False
session = SessionLocal()


def verbose(level: str, msg: str) -> bool:
    if agi:
        try:
            agi.execute(pystrix.agi.core.Verbose(msg))
        except Exception as e:
            logger.error(e)
            raise typer.Exit(code=1)
    else:
        logger.log(level, msg)
    return True


def set_asterisk_var(name: str, value: str) -> bool:
    logger.info(f"{name}={value}")
    if agi:
        try:
            agi.execute(pystrix.agi.core.SetVariable(name, value))
        except Exception as e:
            logger.error(e)
            raise typer.Exit(code=1)


@cli.callback()
def main(
    use_agi: bool = typer.Option(True, "--no-agi", help="Enables/Disables AGI return.")
):
    """
    Cli application to work with Firenze
    """
    global agi
    agi = pystrix.agi.AGI() if use_agi else False


@cli.command()
def test():
    """
    Returns DATETIME from MariDB Server
    """
    sql_test = "SELECT CURRENT_TIMESTAMP() as hora"
    logger.debug(f"SQL: {sql_test}")
    try:
        conn = engine.connect()
        hora = conn.execute(sql_test)
        hora_val = hora.fetchone()
        hora_str = hora_val[0].strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.info(f"{agi=}")
        logger.error(e)
        raise typer.Exit(code=1)
    else:
        logger.info(f"{use_agi=}")
        logger.info(f"Server Time: {hora_str}")
        raise typer.Exit(code=0)


@cli.command()
def did_search(
    did: str = typer.Argument(..., help="DID to check, can be a number or a string")
):
    """
    Search the DID, returns/prints the asterisk context.
    """
    number = session.query(ServiceNumber).filter_by(did=did, active=True).first()

    if number:
        set_asterisk_var("siguiente", number.asterisk_context)
        verbose(logging.INFO, f"Se encontró el contexto {number.asterisk_context}")
        raise typer.Exit(code=0)
    else:
        set_asterisk_var("siguiente", "no-service")
        verbose(logging.WARNING, f"The DID {did} is not registered.")
        raise typer.Exit(code=1)


@cli.command()
def dnc_search(
    ani: str = typer.Argument(..., help="ANI to check, can be a number or a string")
):
    """
    Search the ANI agains the Do Not Call list
    """
    exists = session.query(DoNotCall).filter_by(ani=ani).first()
    if exists:
        set_asterisk_var("dnc", "True")
        verbose(logging.WARNING, f"The number {ani} IS in the Do Not Call list.")
        raise typer.Exit(code=1)

    set_asterisk_var("dnc", "False")
    verbose(logging.INFO, f"The number {ani} is NOT in the Do Not Call list.")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    cli()
