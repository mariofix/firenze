"""User management CLI commands."""

from typing import Optional
import logging

import bcrypt
import typer
from rich import box
from rich.console import Console
from rich.table import Table
from sqlalchemy import delete

from firenze.models import User

app = typer.Typer()
logger = logging.getLogger("firenze")


def _hash_password(password: str) -> str:
    """Hash a password, truncating to 72 bytes as required by bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode(
        "utf-8"
    )


@app.command("search")
def search_user(
    ctx: typer.Context,
    login: str = typer.Option(None, help="Username"),
    email: str = typer.Option(None, help="Email address"),
    id: int = typer.Option(None, help="User ID"),
):
    """Search for users by login, email, or ID."""
    session = ctx.obj.get("dbsession")
    users = session.query(User)
    if login:
        users = users.filter(User.login == login)
    if email:
        users = users.filter(User.email == email)
    if id is not None:
        users = users.filter(User.id == id)
    users = users.all()

    table = Table(title="Users", box=box.ASCII2)
    table.add_column("ID")
    table.add_column("Login")
    table.add_column("Email")
    table.add_column("Enabled")
    table.add_column("Scopes")

    for user in users:
        table.add_row(
            str(user.id),
            user.login,
            user.email,
            str(user.enabled),
            str(user.scopes),
        )

    Console().print(table)


@app.command("create")
def create_user(
    ctx: typer.Context,
    login: str = typer.Option(..., prompt="Username"),
    email: str = typer.Option(..., prompt="Email"),
    scopes: str = typer.Option(..., prompt="Scopes (comma separated)"),
    password: str = typer.Option(
        ..., prompt="Password", hide_input=True, confirmation_prompt="Again"
    ),
    enabled: bool = typer.Option(False, help="Enable the user immediately"),
):
    """Create a new API user (disabled by default)."""
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    try:
        user = User(
            login=login,
            email=email,
            password=_hash_password(password),
            scopes=[s.strip() for s in scopes.split(",")],
            enabled=enabled,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        typer.echo(f"Created user {user.login} (id={user.id})")
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)


@app.command("update")
def update_user(
    ctx: typer.Context,
    user_id: int = typer.Argument(..., help="User ID"),
    login: str = typer.Option(None, help="New username"),
    email: str = typer.Option(None, help="New email"),
    scopes: str = typer.Option(None, help="New scopes (comma separated)"),
    password: str = typer.Option(
        None,
        help="New password (avoid passing on command line; use change-password instead)",
    ),
    enable: Optional[bool] = typer.Option(None, help="Enable or disable"),
):
    """Update an existing user."""
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    user = session.get(User, user_id)
    if not user:
        typer.echo(f"User {user_id} not found", err=True)
        raise typer.Exit(code=1)

    if enable is not None:
        user.enabled = enable
    if password:
        user.password = _hash_password(password)
    if login:
        user.login = login
    if email:
        user.email = email
    if scopes:
        user.scopes = [s.strip() for s in scopes.split(",")]

    session.commit()
    typer.echo(f"Updated user {user_id}")


@app.command("change-password")
def change_password(
    ctx: typer.Context,
    user_id: int = typer.Argument(..., help="User ID"),
    password: str = typer.Option(
        ...,
        prompt="New password",
        hide_input=True,
        confirmation_prompt="Confirm new password",
    ),
):
    """Change a user's password (prompts securely, never echoed)."""
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    user = session.get(User, user_id)
    if not user:
        typer.echo(f"User {user_id} not found", err=True)
        raise typer.Exit(code=1)
    try:
        user.password = _hash_password(password)
        session.commit()
        typer.echo(f"Password updated for user {user_id}")
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)


@app.command("delete")
def delete_user(
    ctx: typer.Context,
    user_id: int = typer.Argument(..., help="User ID"),
    confirm: bool = typer.Option(False, "--yes", help="Skip confirmation"),
):
    """Delete a user permanently."""
    if not confirm:
        typer.confirm(f"Delete user {user_id}? This cannot be undone", abort=True)

    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    try:
        session.execute(delete(User).where(User.id == user_id))
        session.commit()
        typer.echo(f"Deleted user {user_id}")
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)
