import logging.config
from typing import Optional

import typer
from passlib.context import CryptContext
from rich import box
from rich.console import Console
from rich.table import Table
from sqlalchemy import delete

from firenze.config import LOGGING_CONFIG_CLI
from firenze.database import SessionLocal
from firenze.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    """Hash a password, truncating to 72 bytes as required by bcrypt."""
    return pwd_context.hash(password.encode("utf-8")[:72])


app = typer.Typer()


@app.command("search")
def search_user(
    ctx: typer.Context,
    login: str = typer.Option(None, help="Username"),
    email: str = typer.Option(None, help="Email address"),
    id: int = typer.Option(None, help="User ID"),
    scope: str = typer.Option(None, help="User Scope (only 1)"),
):
    """
    Search for a user
    """
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    users = session.query(User)
    if login:
        users = users.filter(User.login == login)
    if email:
        users = users.filter(User.email == email)
    if id:
        users = users.filter(User.id == id)
    users = users.all()
    table = Table(title="User Info", highlight=True, box=box.ASCII2)
    table.add_column("ID")
    table.add_column("Login")
    table.add_column("Email")
    table.add_column("Enabled")
    table.add_column("Scopes")
    table.add_column("Created at")
    table.add_column("Modified at")
    for user in users:
        table.add_row(
            str(user.id),
            user.login,
            user.email,
            str(user.enabled),
            f"{user.scopes}",
            f"{user.created_at}",
            f"{user.modified_at}",
        )
    console = Console()
    console.print(table)
    raise typer.Exit()


@app.command("create")
def create_user(
    ctx: typer.Context,
    login: str = typer.Option(..., help="Username", prompt="Username"),
    email: str = typer.Option(..., help="Email Address", prompt="Email Address"),
    scopes: str = typer.Option(
        ..., help="Scopes (comma separated)", prompt="Scopes (comma separated)"
    ),
    password: str = typer.Option(
        ...,
        help="Password",
        prompt="Password",
        hide_input=True,
        confirmation_prompt="Again",
    ),
    enabled: bool = typer.Option(False, help="User Enabled"),
):
    """
    Create a new user

    Disabled by default.

    """
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    try:
        pwd_hash = _hash_password(password)
        nuevo_usuario = User(
            login=login,
            email=email,
            password=pwd_hash,
            scopes=scopes.split(","),
            enabled=enabled,
        )
        session.add(nuevo_usuario)
        session.commit()
        session.refresh(nuevo_usuario)
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)
    else:
        logger.info(f"{nuevo_usuario=}")

    raise typer.Exit()


@app.command("update")
def update_user(
    ctx: typer.Context,
    user_id: int = typer.Argument(..., help="User ID"),
    login: str = typer.Option(None, help="New Username"),
    email: str = typer.Option(None, help="New Email Address"),
    scopes: str = typer.Option(None, help="New Scopes (comma separated)"),
    password: str = typer.Option(
        None,
        help="New Password",
    ),
    enable: Optional[bool] = typer.Option(None, help="Enable (true) or disable (false) the user"),
):
    """
    Update a current user
    """
    session = SessionLocal()
    logger = ctx.obj.get("logger")
    try:
        usuario = session.get(User, user_id)

        if enable is not None:
            usuario.enabled = enable
        if password:
            pwd_hash = _hash_password(password)
            usuario.password = pwd_hash
        if login:
            usuario.login = login
        if email:
            usuario.email = email
        if scopes:
            usuario.scopes = scopes.split(",")
        session.commit()
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)
    else:
        logger.info(f"Updated {user_id=}")
        typer.echo(f"Updated {user_id=}")
    raise typer.Exit(code=0)


@app.command("delete")
def delete_user(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="User ID"),
):
    """
    Deletes a current user

    Cannot recover

    """
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    try:
        session.execute(delete(User).where(User.id == user_id))
        session.commit()
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)
    else:
        logger.info(f"Deleted: {user_id=}")
    raise typer.Exit()
