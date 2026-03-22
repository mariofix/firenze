"""Migration commands — import clients from the legacy Firenze API."""

import re
from enum import Enum
from typing import Optional

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


# ---------------------------------------------------------------------------
# ANI audit helpers
# ---------------------------------------------------------------------------

def _suspicious_digits(ani: str) -> str:
    """Return a warning string if the ANI has 4+ consecutive identical digits."""
    m = re.search(r"(\d)\1{3,}", ani)
    if m:
        return f"4+ '{m.group(1)}'"
    return ""


def _analyze_ani(ani: str) -> tuple[str | None, str, str]:
    """Analyze an ANI and return ``(suggested_fix, fix_reason, warning)``.

    - ``suggested_fix``: corrected ANI string, or ``None`` if nothing to change.
    - ``fix_reason``: why the fix was applied; empty if no fix.
    - ``warning``: human-readable flag for suspicious patterns; empty if clean.

    Leave-alone cases (pure zeros, test patterns) return all-empty.
    """
    # Leave-alone: pure zeros
    if re.match(r"^0+$", ani):
        return None, "", "leave-alone (zeros)"

    # Leave-alone: starts with 9 followed only by zeros (e.g. 90000000000)
    if re.match(r"^90+$", ani):
        return None, "", "leave-alone (9+zeros)"

    # Fixable: double 56 prefix (e.g. 5656912345678 or 5657321)
    if ani.startswith("5656"):
        fixed = ani[2:]
        return fixed, "double 56 prefix", _suspicious_digits(fixed)

    # Fixable: missing 56 — Chilean mobile (9 + 8 digits)
    if re.match(r"^9\d{8}$", ani):
        fixed = f"56{ani}"
        return fixed, "missing 56 prefix", _suspicious_digits(fixed)

    # Fixable: missing 56 — Santiago landline (2 + 7 digits)
    if re.match(r"^2\d{7}$", ani):
        fixed = f"56{ani}"
        return fixed, "missing 56 prefix", _suspicious_digits(fixed)

    # Has 56 prefix — collect all warnings
    warnings = []
    if len(ani) != 11:
        warnings.append(f"unexpected length ({len(ani)}, expected 11)")
    digits_warn = _suspicious_digits(ani)
    if digits_warn:
        warnings.append(digits_warn)
    return None, "", " + ".join(warnings)


@app.command("check-anis")
def check_anis(
    ctx: typer.Context,
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Filter by service slug"),
    client_id: Optional[int] = typer.Option(None, "--client-id", "-c", help="Filter by client_id"),
    ani_filter: Optional[str] = typer.Option(None, "--ani", "-a", help="Filter by exact ANI value"),
    fix: bool = typer.Option(False, "--fix", help="Apply fixable corrections to the DB"),
    all_records: bool = typer.Option(False, "--all", help="Scan all ANI records (use with caution)"),
):
    """Audit and optionally fix ANI records in client_ani.

    Detects: double 56 prefix, missing 56 prefix, suspicious digit patterns,
    and known leave-alone values (zeros, test numbers).

    Examples:

        firenze migration check-anis --service fonotarot-cl

        firenze migration check-anis --client-id 42

        firenze migration check-anis --ani 5656912345678 --fix

        firenze migration check-anis --all
    """
    db = ctx.obj["dbsession"]

    if not any([service, client_id, ani_filter, all_records]):
        typer.echo(
            "Provide at least one filter (--service, --client-id, --ani) or --all",
            err=True,
        )
        raise typer.Exit(1)

    query = db.query(ClientAni)

    if service:
        svc = db.query(Service).filter_by(slug=service).first()
        if not svc:
            typer.echo(f"Service '{service}' not found in DB", err=True)
            raise typer.Exit(1)
        query = query.filter(ClientAni.service_id == svc.id)

    if client_id is not None:
        query = query.filter(ClientAni.client_id == client_id)

    if ani_filter:
        query = query.filter(ClientAni.ani == ani_filter)

    rows: list[ClientAni] = query.all()

    if not rows:
        typer.echo("No ANI records matched the filter.")
        raise typer.Exit(0)

    label = " [DRY RUN]" if not fix else " [FIX MODE]"
    table = Table(title=f"ANI Audit{label}", box=box.ASCII2)
    table.add_column("id", style="cyan", justify="right")
    table.add_column("svc_id", justify="right")
    table.add_column("client_id", justify="right")
    table.add_column("current ANI")
    table.add_column("suggested fix")
    table.add_column("diagnosis")

    counts = {"ok": 0, "fixable": 0, "fixed": 0, "suspicious": 0, "leave_alone": 0, "error": 0}

    for row in rows:
        suggested, fix_reason, warning = _analyze_ani(row.ani)

        if "leave-alone" in warning:
            diag = f"[dim]{warning}[/dim]"
            suggested_str = "-"
            counts["leave_alone"] += 1
        elif fix_reason and warning:
            diag = f"[yellow]{fix_reason} + {warning}[/yellow]"
            suggested_str = suggested or "-"
            counts["fixable"] += 1
        elif fix_reason:
            diag = f"[blue]{fix_reason}[/blue]"
            suggested_str = suggested or "-"
            counts["fixable"] += 1
        elif warning:
            diag = f"[yellow]suspicious: {warning}[/yellow]"
            suggested_str = "-"
            counts["suspicious"] += 1
        else:
            diag = "[green]ok[/green]"
            suggested_str = "-"
            counts["ok"] += 1

        if fix and suggested and fix_reason and "leave-alone" not in warning:
            # Check the target ANI isn't already taken by another row in this service
            conflict = (
                db.query(ClientAni)
                .filter(ClientAni.service_id == row.service_id, ClientAni.ani == suggested, ClientAni.id != row.id)
                .first()
            )
            if conflict:
                diag = f"[red]conflict: {suggested} already exists (id={conflict.id})[/red]"
                suggested_str = suggested
                counts["error"] += 1
            else:
                try:
                    row.ani = suggested
                    db.commit()
                    diag = f"[green]fixed: {fix_reason}[/green]"
                    suggested_str = suggested
                    counts["fixed"] += 1
                except Exception as e:
                    db.rollback()
                    diag = f"[red]db error: {e}[/red]"
                    counts["error"] += 1

        table.add_row(
            str(row.id),
            str(row.service_id),
            str(row.client_id),
            row.ani,
            suggested_str,
            diag,
        )

    console.print(table)
    typer.echo(
        f"\nTotal: {len(rows)} — "
        f"ok: {counts['ok']}, "
        f"fixable: {counts['fixable']}, "
        f"fixed: {counts['fixed']}, "
        f"suspicious: {counts['suspicious']}, "
        f"leave-alone: {counts['leave_alone']}, "
        f"errors: {counts['error']}"
    )
