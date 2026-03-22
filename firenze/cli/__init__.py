"""Firenze CLI — admin and debug commands."""

import logging
import logging.config

import typer

from firenze.cli import calls, dnc, did, migration, operators, users
from firenze.config import LOGGING_CONFIG_CLI
from firenze.database import SessionLocal
from firenze.redis import get_redis

logging.config.dictConfig(LOGGING_CONFIG_CLI)
logger = logging.getLogger("firenze-cli")

cli = typer.Typer(help="Admin and debug CLI for Firenze.")
cli.add_typer(users.app, name="users", help="Manage API users")
cli.add_typer(operators.app, name="operator", help="Operator login, logout, and status")
cli.add_typer(dnc.app, name="dnc", help="Do Not Call list")
cli.add_typer(did.app, name="did", help="DID resolution")
cli.add_typer(calls.app, name="calls", help="Online call tracking (debug)")
cli.add_typer(migration.app, name="migration", help="Migrate data from the legacy Firenze API")


@cli.callback()
def main(ctx: typer.Context):
    """Admin and debug CLI for Firenze."""
    ctx.ensure_object(dict)
    ctx.obj["dbsession"] = SessionLocal()
    ctx.obj["logger"] = logger
    try:
        ctx.obj["redis"] = get_redis()
    except Exception:
        logger.warning("Redis unavailable — operator state commands will skip Redis sync")
        ctx.obj["redis"] = None
