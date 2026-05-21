"""Comandos de migración - importar clientes de la API Firenze heredada."""

import logging
import re
from enum import StrEnum

import requests
import typer
from rich import box
from rich.console import Console
from rich.live import Live
from rich.table import Table
from sqlalchemy import func, select, text

from firenze.config import settings
from firenze.models.client import Client, ClientAni
from firenze.models.service import Service

app = typer.Typer()
console = Console()
logger = logging.getLogger("firenze")


class LegacyService(StrEnum):
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


@app.command("update-phones")
def update_phones(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen without writing"),
):
    """Fin the most used ANI in ClientAni to fill client.phone_number

    Examples:
        firenze migration update-phones --dry-run
    """
    typer.echo(
        "Client.phone_number was removed; update-phones is deprecated and now no-ops.",
        err=True,
    )
    raise typer.Exit(0)

    db = ctx.obj["dbsession"]
    stmt = (
        select(ClientAni.client_id, func.count(ClientAni.ani).label("total"), ClientAni.ani)
        .where(ClientAni.service_id == 2)
        .group_by(ClientAni.client_id)
        .order_by(ClientAni.client_id)
    )

    # Execute
    results = db.execute(stmt).all()

    for ani in results:
        if ani[1] == 1:
            client = db.query(Client).filter_by(service_id=2, client_id=ani[0], phone_number=None).first()
            print(f"ANI: {ani[2]} - Client: {client}")
            if client:
                client.phone_number = ani[2]
                db.flush()
                db.commit()
                print(f"{client=}")


@app.command("clients")
def migrate_clients(
    ctx: typer.Context,
    service: LegacyService = typer.Argument(..., help="fonotarot-cl or alotarot"),
    client_specs: list[str] = typer.Argument(..., help="Client IDs: '42', '10-34', or mixed e.g. '10-34 55 67'"),
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
        typer.echo(
            f"Service '{service.value}' not found in DB - run migrations first.",
            err=True,
        )
        raise typer.Exit(1)

    if not settings.LEGACY_API_USER or not settings.LEGACY_API_PASSWORD:
        typer.echo("LEGACY_API_USER and LEGACY_API_PASSWORD must be set in .env", err=True)
        raise typer.Exit(1)

    try:
        token = _get_token(
            settings.LEGACY_API_URL,
            settings.LEGACY_API_USER,
            settings.LEGACY_API_PASSWORD,
        )
    except requests.HTTPError as e:
        typer.echo(f"Authentication failed: {e}", err=True)
        raise typer.Exit(1)

    client_ids = _parse_client_ids(client_specs)
    label = " [DRY RUN]" if dry_run else ""
    typer.echo(f"Migrating {len(client_ids)} client(s) for '{service.value}'{label}")

    counts = {"ok": 0, "skipped": 0, "not_found": 0, "error": 0}

    table = Table(title=f"Migration: {service.value}{label}", box=box.ASCII2)
    table.add_column("client_id", style="cyan")
    table.add_column("email")
    table.add_column("credits", justify="right")
    table.add_column("ANIs", justify="right")
    table.add_column("status")

    with Live(table, console=console, refresh_per_second=8, vertical_overflow="visible"):
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
                updated = False
                if not dry_run:
                    if existing.credits != data.get("creditos", 0):
                        existing.credits = data.get("creditos", 0)
                        db.flush()
                        db.commit()
                        updated = True

                table.add_row(
                    str(cid),
                    data.get("correo", ""),
                    str(data.get("creditos", 0)),
                    str(len(data.get("telefonos", []))),
                    f"[yellow]skipped (exists)[/yellow][green]{updated=}[/green]",
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
                    table.add_row(
                        str(cid),
                        data.get("correo", ""),
                        "-",
                        "-",
                        f"[red]db error: {e}[/red]",
                    )
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

    typer.echo(
        f"\nDone - ok: {counts['ok']}, skipped: {counts['skipped']}, "
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

    # Fixable: missing 56 - Chilean mobile (9 + 8 digits)
    if re.match(r"^9\d{8}$", ani):
        fixed = f"56{ani}"
        return fixed, "missing 56 prefix", _suspicious_digits(fixed)

    # Fixable: missing 56 - Santiago landline (2 + 7 digits)
    if re.match(r"^2\d{7}$", ani):
        fixed = f"56{ani}"
        return fixed, "missing 56 prefix", _suspicious_digits(fixed)

    # Has 56 prefix - collect all warnings
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
    service: str | None = typer.Option(None, "--service", "-s", help="Filter by service slug"),
    client_id: int | None = typer.Option(None, "--client-id", "-c", help="Filter by client_id"),
    ani_filter: str | None = typer.Option(None, "--ani", "-a", help="Filter by exact ANI value"),
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

    counts = {
        "ok": 0,
        "fixable": 0,
        "fixed": 0,
        "suspicious": 0,
        "leave_alone": 0,
        "error": 0,
    }

    with Live(table, console=console, refresh_per_second=8, vertical_overflow="visible"):
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
                    .filter(
                        ClientAni.service_id == row.service_id,
                        ClientAni.ani == suggested,
                        ClientAni.id != row.id,
                    )
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

    typer.echo(
        f"\nTotal: {len(rows)}: "
        f"ok: {counts['ok']}, "
        f"fixable: {counts['fixable']}, "
        f"fixed: {counts['fixed']}, "
        f"suspicious: {counts['suspicious']}, "
        f"leave-alone: {counts['leave_alone']}, "
        f"errors: {counts['error']}"
    )


@app.command("check-phones")
def check_phones(
    ctx: typer.Context,
    service: str | None = typer.Option(None, "--service", "-s", help="Filter by service slug"),
    client_id: int | None = typer.Option(None, "--client-id", "-c", help="Filter by client_id"),
    ani_filter: str | None = typer.Option(None, "--ani", "-a", help="Filter by exact ANI value"),
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

    query = db.query(Client)

    if service:
        svc = db.query(Service).filter_by(slug=service).first()
        if not svc:
            typer.echo(f"Service '{service}' not found in DB", err=True)
            raise typer.Exit(1)
        query = query.filter(Client.service_id == svc.id)

    if client_id is not None:
        query = query.filter(Client.client_id == client_id)

    if ani_filter:
        query = query.filter(Client.phone_number == ani_filter)

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

    counts = {
        "ok": 0,
        "fixable": 0,
        "fixed": 0,
        "suspicious": 0,
        "leave_alone": 0,
        "error": 0,
    }

    with Live(table, console=console, refresh_per_second=8, vertical_overflow="visible"):
        for row in rows:
            if row.phone_number:
                suggested, fix_reason, warning = _analyze_ani(row.phone_number)

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
                        db.query(Client)
                        .filter(
                            Client.service_id == row.service_id,
                            Client.phone_number == suggested,
                            Client.id != row.id,
                        )
                        .first()
                    )
                    if conflict:
                        diag = f"[red]conflict: {suggested} already exists (id={conflict.id})[/red]"
                        suggested_str = suggested
                        counts["error"] += 1
                    else:
                        try:
                            row.phone_number = suggested
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
                    row.phone_number,
                    suggested_str,
                    diag,
                )

    typer.echo(
        f"\nTotal: {len(rows)}: "
        f"ok: {counts['ok']}, "
        f"fixable: {counts['fixable']}, "
        f"fixed: {counts['fixed']}, "
        f"suspicious: {counts['suspicious']}, "
        f"leave-alone: {counts['leave_alone']}, "
        f"errors: {counts['error']}"
    )


# ---------------------------------------------------------------------------
# Backfill email + full_name from the legacy zvn_portal Django DB
# ---------------------------------------------------------------------------
#
# Source (zvn_portal):
#   zvn_cliente.servicio_id  -> portal service (1 = Fonotarot)
#   zvn_cliente.client_id    -> integer client id shared with Firenze
#   zvn_correo               -> latest active email per cliente
#   zvn_compra.nombre        -> name typed at purchase time (latest wins)
#
# Target (new_firenze.client): updates email and full_name in place.
# Both DBs live on the same MariaDB instance, so we use cross-DB JOINs
# through the existing SQLAlchemy session - no second connection needed.

_PORTAL_DB = "zvn_portal"

_EMAIL_PREVIEW_SQL = """
SELECT c.client_id, c.email AS current_email, co.correo AS portal_email
FROM client AS c
JOIN {portal}.zvn_cliente AS zc
  ON zc.client_id = c.client_id AND zc.servicio_id = :portal_service_id
JOIN (
    SELECT cliente_id, correo,
           ROW_NUMBER() OVER (PARTITION BY cliente_id
                              ORDER BY modificado DESC, id DESC) AS rn
    FROM {portal}.zvn_correo
    WHERE activo = 1 AND correo IS NOT NULL AND correo <> ''
) AS co
  ON co.cliente_id = zc.id AND co.rn = 1
WHERE c.service_id = :service_id
  AND co.correo <> COALESCE(c.email, '')
  {fill_clause}
"""

_NAME_PREVIEW_SQL = """
SELECT c.client_id, c.full_name AS current_name, TRIM(cp.nombre) AS portal_name
FROM client AS c
JOIN {portal}.zvn_cliente AS zc
  ON zc.client_id = c.client_id AND zc.servicio_id = :portal_service_id
JOIN (
    SELECT cliente_id, nombre,
           ROW_NUMBER() OVER (PARTITION BY cliente_id
                              ORDER BY modificado DESC, id DESC) AS rn
    FROM {portal}.zvn_compra
    WHERE nombre IS NOT NULL AND TRIM(nombre) <> ''
) AS cp
  ON cp.cliente_id = zc.id AND cp.rn = 1
WHERE c.service_id = :service_id
  AND TRIM(cp.nombre) <> COALESCE(c.full_name, '')
  {fill_clause}
"""

_EMAIL_UPDATE_SQL = """
UPDATE client AS c
JOIN {portal}.zvn_cliente AS zc
  ON zc.client_id = c.client_id AND zc.servicio_id = :portal_service_id
JOIN (
    SELECT cliente_id, correo,
           ROW_NUMBER() OVER (PARTITION BY cliente_id
                              ORDER BY modificado DESC, id DESC) AS rn
    FROM {portal}.zvn_correo
    WHERE activo = 1 AND correo IS NOT NULL AND correo <> ''
) AS co
  ON co.cliente_id = zc.id AND co.rn = 1
SET c.email = co.correo
WHERE c.service_id = :service_id
  {fill_clause}
"""

_NAME_UPDATE_SQL = """
UPDATE client AS c
JOIN {portal}.zvn_cliente AS zc
  ON zc.client_id = c.client_id AND zc.servicio_id = :portal_service_id
JOIN (
    SELECT cliente_id, nombre,
           ROW_NUMBER() OVER (PARTITION BY cliente_id
                              ORDER BY modificado DESC, id DESC) AS rn
    FROM {portal}.zvn_compra
    WHERE nombre IS NOT NULL AND TRIM(nombre) <> ''
) AS cp
  ON cp.cliente_id = zc.id AND cp.rn = 1
SET c.full_name = TRIM(cp.nombre)
WHERE c.service_id = :service_id
  {fill_clause}
"""


@app.command("sync-portal")
def sync_portal(
    ctx: typer.Context,
    service: str = typer.Option("fonotarot-cl", "--service", "-s", help="Target service slug"),
    portal_service_id: int = typer.Option(
        1,
        "--portal-service-id",
        help="zvn_portal.zvn_cliente.servicio_id to source from",
    ),
    portal_db: str = typer.Option(_PORTAL_DB, "--portal-db", help="Schema name of the Django portal DB"),
    fill_only: bool = typer.Option(
        False,
        "--fill-only",
        help="Only update rows where the target field is NULL or empty",
    ),
    skip_email: bool = typer.Option(False, "--skip-email", help="Don't touch the email column"),
    skip_name: bool = typer.Option(False, "--skip-name", help="Don't touch the full_name column"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the diff, don't write"),
    sample: int = typer.Option(15, "--sample", help="Rows to show in the dry-run preview"),
):
    """Backfill ``client.email`` and ``client.full_name`` from the zvn_portal Django DB.

    Uses cross-DB JOINs against the same MariaDB instance - no separate connection.

    Examples:

        firenze migration sync-portal --dry-run

        firenze migration sync-portal --fill-only

        firenze migration sync-portal --skip-name
    """
    db = ctx.obj["dbsession"]

    svc = db.query(Service).filter_by(slug=service).first()
    if not svc:
        typer.echo(f"Service '{service}' not found in DB.", err=True)
        raise typer.Exit(1)

    if not re.match(r"^[A-Za-z0-9_]+$", portal_db):
        typer.echo(f"Invalid --portal-db value: {portal_db!r}", err=True)
        raise typer.Exit(1)

    params = {"service_id": svc.id, "portal_service_id": portal_service_id}
    email_fill_preview = "AND (c.email IS NULL OR c.email = '')" if fill_only else ""
    name_fill_preview = "AND (c.full_name IS NULL OR c.full_name = '')" if fill_only else ""
    email_fill_update = "AND (c.email IS NULL OR c.email = '')" if fill_only else ""
    name_fill_update = "AND (c.full_name IS NULL OR c.full_name = '')" if fill_only else ""

    label_bits = []
    if dry_run:
        label_bits.append("DRY RUN")
    if fill_only:
        label_bits.append("fill-only")
    label = f" [{', '.join(label_bits)}]" if label_bits else ""

    typer.echo(
        f"sync-portal: service={service} (id={svc.id}) "
        f"<- {portal_db}.zvn_cliente.servicio_id={portal_service_id}{label}"
    )

    if not skip_email:
        sql_preview = _EMAIL_PREVIEW_SQL.format(portal=portal_db, fill_clause=email_fill_preview)
        rows = db.execute(text(sql_preview), params).fetchall()
        _render_preview("email", rows, sample)

        if not dry_run and rows:
            sql_update = _EMAIL_UPDATE_SQL.format(portal=portal_db, fill_clause=email_fill_update)
            result = db.execute(text(sql_update), params)
            db.commit()
            typer.echo(f"  email: updated {result.rowcount} row(s).")
        elif dry_run:
            typer.echo(f"  email: would update {len(rows)} row(s).")

    if not skip_name:
        sql_preview = _NAME_PREVIEW_SQL.format(portal=portal_db, fill_clause=name_fill_preview)
        rows = db.execute(text(sql_preview), params).fetchall()
        _render_preview("full_name", rows, sample)

        if not dry_run and rows:
            sql_update = _NAME_UPDATE_SQL.format(portal=portal_db, fill_clause=name_fill_update)
            result = db.execute(text(sql_update), params)
            db.commit()
            typer.echo(f"  full_name: updated {result.rowcount} row(s).")
        elif dry_run:
            typer.echo(f"  full_name: would update {len(rows)} row(s).")


def _render_preview(field: str, rows: list, sample: int) -> None:
    """Print a small before/after table for a sync-portal field."""
    if not rows:
        typer.echo(f"  {field}: nothing to change.")
        return

    table = Table(title=f"{field}: {len(rows)} change(s), showing up to {sample}", box=box.ASCII2)
    table.add_column("client_id", style="cyan", justify="right")
    table.add_column(f"current {field}")
    table.add_column(f"portal {field}")
    for row in rows[:sample]:
        client_id, current, incoming = row
        table.add_row(str(client_id), "" if current is None else str(current), str(incoming))
    console.print(table)
