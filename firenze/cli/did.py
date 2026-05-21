"""Comandos CLI de resolución de DID."""

import logging

import typer

from firenze.services.did_service import resolve_did

app = typer.Typer()
logger = logging.getLogger("firenze")


@app.command("resolve")
def resolve(
    ctx: typer.Context,
    did: str = typer.Argument(..., help="DID number to resolve"),
):
    """Resolve a DID to its Asterisk context."""
    session = ctx.obj.get("dbsession")
    context = resolve_did(session, did)
    if context:
        typer.echo(f"{did} → {context}")
    else:
        typer.echo(f"{did} not found or inactive", err=True)
        raise typer.Exit(code=1)
