# """CLI de Firenze — comandos de administración y depuración."""

# import logging
# import logging.config

# import typer

# # from firenze.cli import calls, client, did, dnc, fastapi, migration, operators, users
# from firenze.config import LOGGING_CONFIG
# from firenze.database import SessionLocal

# logging.config.dictConfig(LOGGING_CONFIG)
# logger = logging.getLogger("firenze")

# cli = typer.Typer(help="Admin and debug CLI for Firenze.")
# cli.add_typer(users.app, name="users", help="Manage API users")
# cli.add_typer(dnc.app, name="dnc", help="Do Not Call list")
# cli.add_typer(did.app, name="did", help="DID resolution")
# cli.add_typer(operators.app, name="operator", help="Operator login, logout, and status")
# cli.add_typer(client.app, name="client", help="Client management tools")
# cli.add_typer(calls.app, name="calls", help="Online call tracking (debug)")
# cli.add_typer(migration.app, name="migration", help="Migrate data from the legacy Firenze API")
# cli.add_typer(fastapi.app, name="fastapi", help="various tools for fastapi")


# @cli.callback()
# def main(ctx: typer.Context):
#     """Admin and debug CLI for Firenze."""
#     ctx.ensure_object(dict)
#     db = SessionLocal()
#     ctx.call_on_close(db.close)
#     ctx.obj["dbsession"] = db
#     ctx.obj["logger"] = logger
