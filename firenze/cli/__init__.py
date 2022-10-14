from firenze.database import engine, SessionLocal
from firenze.config import LOGGING_CONFIG_CLI
from firenze.models import DoNotCall
from firenze.cli.utils import verbose, set_asterisk_var
from firenze.cli import online_calls, services
import typer
import logging.config
import pystrix

logging.config.dictConfig(LOGGING_CONFIG_CLI)
logger = logging.getLogger("firenze-cli")

cli = typer.Typer()
cli.add_typer(online_calls.app, name="online-calls", help="Manages the OnlineCalls")
cli.add_typer(services.app, name="services", help="Queries the Services")


@cli.callback()
def main(
    ctx: typer.Context,
    agi: bool = typer.Option(True, help="Enable/Disable return via AGI."),
):
    """
    Cli application to work with Firenze
    """
    ctx.ensure_object(dict)
    ctx.obj["agi"] = pystrix.agi.AGI() if agi else False
    ctx.obj["dbsession"] = SessionLocal()
    ctx.obj["dbengine"] = engine
    ctx.obj["logger"] = logger


@cli.command()
def test(ctx: typer.Context):
    """
    Returns DATETIME from MariDB Server
    """
    agi = ctx.obj.get("agi")
    engine = ctx.obj.get("dbengine")
    sql = "SELECT CURRENT_TIMESTAMP()"
    logger.debug(f"{sql=}")
    try:
        conn = engine.connect()
        hora = conn.execute(sql)
        hora_val = hora.fetchone()
        server_time = hora_val[0].strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.info(f"{agi=}")
        logger.error(e)
        raise typer.Exit(code=1)
    else:
        logger.info(f"{server_time=}")
        verbose(agi, f"{server_time=}")
        raise typer.Exit(code=0)


@cli.command()
def dnc_search(
    ctx: typer.Context,
    ani: str = typer.Argument(..., help="ANI to check, can be a number or a string"),
):
    """
    Search the ANI against the Do Not Call list
    """
    agi = ctx.obj.get("agi")
    session = ctx.obj.get("dbsession")
    exists = session.query(DoNotCall).filter_by(ani=ani).first()
    if exists:
        logger.info(f"The number {ani} IS in the DoNotCall list.")
        verbose(agi, f"The number {ani} IS in the DoNotCall list.")
        set_asterisk_var(agi, "dnc", "YES")
        raise typer.Exit(code=1)

    logger.info(f"The number {ani} is NOT in the DoNotCall list.")
    verbose(agi, f"The number {ani} is NOT in the DoNotCall list.")
    set_asterisk_var(agi, "dnc", "NO")

    raise typer.Exit(code=0)
