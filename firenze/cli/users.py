"""Comandos CLI de administración de usuarios."""

import datetime
import logging

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from sqlalchemy import delete

from firenze.models import ApiCredential, User
from firenze.services import auth_service

app = typer.Typer()
logger = logging.getLogger("firenze")


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
    password: str = typer.Option(..., prompt="Password", hide_input=True, confirmation_prompt="Again"),
    enabled: bool = typer.Option(False, help="Enable the user immediately"),
):
    """Create a new API user (disabled by default)."""
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")
    try:
        user = User(
            login=login,
            email=email,
            password=auth_service.hash_user_password(password),
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
    enable: bool | None = typer.Option(None, help="Enable or disable"),
):
    """Update an existing user."""
    session = ctx.obj.get("dbsession")
    user = session.get(User, user_id)
    if not user:
        typer.echo(f"User {user_id} not found", err=True)
        raise typer.Exit(code=1)

    if enable is not None:
        user.enabled = enable
    if password:
        user.password = auth_service.hash_user_password(password)
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
        user.password = auth_service.hash_user_password(password)
        session.commit()
        typer.echo(f"Password updated for user {user_id}")
    except Exception as e:
        logger.error(e)
        raise typer.Exit(code=1)


@app.command("api-credential-list")
def api_credential_list(
    ctx: typer.Context,
    user_id: int = typer.Option(None, help="Filter by user ID"),
    enabled_only: bool = typer.Option(False, help="Show only enabled credentials"),
):
    """List API credentials."""
    session = ctx.obj.get("dbsession")
    query = session.query(ApiCredential)
    if user_id is not None:
        query = query.filter(ApiCredential.user_id == user_id)
    if enabled_only:
        query = query.filter(ApiCredential.enabled.is_(True), ApiCredential.revoked_at.is_(None))
    rows = query.order_by(ApiCredential.id.asc()).all()

    table = Table(title="API Credentials", box=box.ASCII2)
    table.add_column("ID")
    table.add_column("User ID")
    table.add_column("Name")
    table.add_column("API Key")
    table.add_column("Enabled")
    table.add_column("Expires At")
    table.add_column("Revoked At")
    table.add_column("Last Used")

    for row in rows:
        table.add_row(
            str(row.id),
            str(row.user_id),
            row.name or "",
            row.api_key,
            str(row.enabled),
            str(row.expires_at or ""),
            str(row.revoked_at or ""),
            str(row.last_used_at or ""),
        )
    Console().print(table)


@app.command("api-credential-create")
def api_credential_create(
    ctx: typer.Context,
    user_id: int = typer.Argument(..., help="Owner user ID"),
    name: str = typer.Option(None, help="Optional internal label"),
    expires_days: int = typer.Option(None, help="Optional expiration in days"),
):
    """Create one API credential pair (key+secret). Secret is shown once."""
    session = ctx.obj.get("dbsession")
    user = session.get(User, user_id)
    if not user:
        typer.echo(f"User {user_id} not found", err=True)
        raise typer.Exit(code=1)
    expires_at = None
    if expires_days is not None:
        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=expires_days)
    credential, api_secret = auth_service.create_api_credential(
        session,
        user=user,
        name=name,
        expires_at=expires_at,
    )
    typer.echo(f"Created API credential id={credential.id} for user={user_id}")
    typer.echo(f"x-api-key: {credential.api_key}")
    typer.echo(f"x-api-secret: {api_secret}")


@app.command("api-credential-revoke")
def api_credential_revoke(
    ctx: typer.Context,
    credential_id: int = typer.Argument(..., help="Credential ID"),
):
    """Revoke an API credential."""
    session = ctx.obj.get("dbsession")
    credential = session.get(ApiCredential, credential_id)
    if not credential:
        typer.echo(f"Credential {credential_id} not found", err=True)
        raise typer.Exit(code=1)
    auth_service.revoke_api_credential(session, credential)
    typer.echo(f"Revoked API credential {credential_id}")


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
