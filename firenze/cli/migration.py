"""Migration commands — import clients from the legacy Firenze API."""

import re
from enum import Enum

import requests
import typer
from rich import box
from rich.console import Console
from rich.table import Table

from firenze.config import settings
from firenze.models.client import Client, ClientAni
from firenze.models.service import Service

app = typer.Typer()
console = Console()


class LegacyService(str, Enum):
    fonotarot_cl = "fonotarot-cl"
    alotarot = "alotarot"


def _parse_client_ids(specs: list[str]) -> list[int]:
    """Parse a mix of IDs and ranges into a sorted deduplicated list of ints.

    Accepts: ``"42"``, ``"10-34"``, or any combination.
    """
    ids: set[int] = set()
    for spec in specs:
        if re.match(r"^\d+-\d+$", spec):
            start, end = spec.split("-")
            ids.update(range(int(start), int(end) + 1))
        else:
            ids.add(int(spec))
    return sorted(ids)


def _get_token(base_url: str, username: str, password: str) -> str:
    """Obtain an OAuth2 bearer token from the legacy API."""
    resp = requests.post(
        f"{base_url}/token",
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
            "scope": "audiotex",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _fetch_client(base_url: str, token: str, service_slug: str, client_id: int) -> dict | None:
    """Fetch one client from the legacy API. Returns None if not found."""
    resp = requests.get(
        f"{base_url}/audiotex/{service_slug}/client/{client_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


@app.command("clients")
def migrate_clients(
    ctx: typer.Context,
    service: LegacyService = typer.Argument(..., help="fonotarot-cl or alotarot"),
    client_specs: list[str] = typer.Argument(
        ..., help="Client IDs: '42', '10-34', or mixed e.g. '10-34 55 67'"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen without writing"),
):
    """Migrate clients from the legacy Firenze API into the new DB.

    Examples:

        firenze migration clients fonotarot-cl 42

        firenze migration clients alotarot 10-34

        firenze migration clients fonotarot-cl 10-34 55 67
    """
    db = ctx.obj["dbsession"]

    svc = db.query(Service).filter_by(slug=service.value).first()
    if not svc:
        typer.echo(f"Service '{service.value}' not found in DB — run migrations first.", err=True)
        raise typer.Exit(1)

    if not settings.LEGACY_API_USER or not settings.LEGACY_API_PASSWORD:
        typer.echo("LEGACY_API_USER and LEGACY_API_PASSWORD must be set in .env", err=True)
        raise typer.Exit(1)

    try:
        token = _get_token(settings.LEGACY_API_URL, settings.LEGACY_API_USER, settings.LEGACY_API_PASSWORD)
    except requests.HTTPError as e:
        typer.echo(f"Authentication failed: {e}", err=True)
        raise typer.Exit(1)

    client_ids = _parse_client_ids(client_specs)
    label = " [DRY RUN]" if dry_run else ""
    typer.echo(f"Migrating {len(client_ids)} client(s) for '{service.value}'{label}")

    counts = {"ok": 0, "skipped": 0, "not_found": 0, "error": 0}

    table = Table(title=f"Migration — {service.value}{label}", box=box.ASCII2)
    table.add_column("client_id", style="cyan")
    table.add_column("email")
    table.add_column("credits", justify="right")
    table.add_column("ANIs", justify="right")
    table.add_column("status")

    for cid in client_ids:
        try:
            data = _fetch_client(settings.LEGACY_API_URL, token, service.value, cid)
        except requests.RequestException as e:
            table.add_row(str(cid), "-", "-", "-", f"[red]fetch error: {e}[/red]")
            counts["error"] += 1
            continue

        if data is None:
            table.add_row(str(cid), "-", "-", "-", "[yellow]not found[/yellow]")
            counts["not_found"] += 1
            continue

        existing = db.query(Client).filter_by(service_id=svc.id, client_id=cid).first()
        if existing:
            table.add_row(
                str(cid),
                data.get("correo", ""),
                str(data.get("creditos", 0)),
                str(len(data.get("telefonos", []))),
                "[yellow]skipped (exists)[/yellow]",
            )
            counts["skipped"] += 1
            continue

        phones: list[str] = list(dict.fromkeys(data.get("telefonos", [])))  # deduplicate, preserve order

        if not dry_run:
            try:
                client = Client(
                    service_id=svc.id,
                    client_id=cid,
                    email=data.get("correo"),
                    credits=data.get("creditos", 0),
                )
                db.add(client)
                db.flush()

                for ani in phones:
                    # Skip ANIs already registered to another client in this service
                    if not db.query(ClientAni).filter_by(service_id=svc.id, ani=ani).first():
                        db.add(ClientAni(service_id=svc.id, client_id=cid, ani=ani))

                db.commit()
            except Exception as e:
                db.rollback()
                table.add_row(str(cid), data.get("correo", ""), "-", "-", f"[red]db error: {e}[/red]")
                counts["error"] += 1
                continue

        table.add_row(
            str(cid),
            data.get("correo", ""),
            str(data.get("creditos", 0)),
            str(len(phones)),
            "[green]dry-run[/green]" if dry_run else "[green]ok[/green]",
        )
        counts["ok"] += 1

    console.print(table)
    typer.echo(
        f"\nDone — ok: {counts['ok']}, skipped: {counts['skipped']}, "
        f"not found: {counts['not_found']}, errors: {counts['error']}"
    )
