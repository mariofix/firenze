# Firenze - Migration Status

> Overall design: [new-architecture.md](new-architecture.md)
> Endpoint shapes, configs, dialplan reference: [tech.md](tech.md)

## Where we are right now

**Two Firenze runtimes are running side by side in production** while the
dialplan is migrated piece by piece:

- Legacy: AGI CLI subprocesses (`${FIRENZE}` and `${AUDIOTEX}` globals in
  the dialplan). Spawns a Python process per call step.
- New: FastAPI service on `localhost:9002` (this repo). Asterisk hits it
  via `${FIRENZE_API}` using `CURL()` + `JSON_DECODE()`.

**Dialplan tiers:**

| Path | Role |
|---|---|
| `asterisk_config/current/*.conf` (top level) | Older snapshot, pure AGI. Not loaded. |
| `asterisk_config/current/new_config/*.conf` | Currently loaded in Asterisk. Hybrid: CURL calls run alongside the old AGI calls so both runtimes see the same events. Lets us validate the new service against the old one. |
| `asterisk_config/new/*.conf` | Target dialplan. Clean CURL-only, unified `[prepago-service]` context replacing the per-service duplicates. Not yet deployed. |

## Done

### Core infrastructure

- FastAPI app factory, gunicorn + uvicorn worker, systemd unit
- Pydantic v2, pydantic-settings, single `get_db()` in `dependencies.py`
- `database.py` cleaned up (no `sqlalchemy.ext.declarative`)
- `passlib` removed, direct `bcrypt` throughout
- Alembic configured via `pyproject.toml`, current head `a8c5e1f2b9d3`

### Domain and schemas

- `models/` split by domain (`user`, `service`, `operator`, `call`,
  `client`, `dnc`, `event`), SQLAlchemy 2.0 `Mapped` style
- `schemas/` split by domain, Pydantic v2
- Unified `Client` model with per-service `(service_id, client_id)`
- `ClientAni` child table for multi-ANI -> one client mapping
- `Service.auth_method`, `Service.intro_audio`, `Operator.audio_file` -
  enough metadata in the DB to drive a single shared dialplan context

### Services layer

- `services/dnc_service.py` - `check_dnc`
- `services/credit_service.py` - `compute_call_limit`
- `services/did_service.py` - `resolve_did`
- `services/operator_service.py` - `login`, `logout`, `login_by_phone`,
  `logout_by_phone`, `set_availability`, `get_menu`, `select_operator`
  (atomic `SELECT FOR UPDATE`), `release_operator`, `info_operator`
- `services/client_service.py` - `lookup` (PIN then ClientAni),
  `deduct_credits`
- `services/call_service.py` - `insert_call`, `delete_call`,
  `update_call_operator`, `get_active_call`

### AGI endpoints (all live on :9002)

- `GET  /agi/dnc/{ani}`
- `GET  /agi/services/did/{did}`
- `GET  /agi/credits/limit?seconds=N`
- `GET  /agi/clients/lookup?service=&identifier=`
- `POST /agi/clients/{service}/{client_id}/deduct`
- `POST /agi/calls/online`
- `GET  /agi/calls/online/{service}/{ani}`
- `POST /agi/calls/online/{service}/{ani}/assign`
- `POST /agi/calls/online/{service}/{ani}/close`
- `GET  /agi/operators/menu`
- `POST /agi/operators/select`
- `POST /agi/operators/{number}/release`
- `POST /agi/operators/by-phone/{ani}/login`
- `POST /agi/operators/by-phone/{ani}/logout`
- `GET  /agi/operators/by-ani/{ani}` (info, lookup by phone number)
- `GET  /agi/operators/by-option/{option}` (info, lookup by IVR menu digit)

### Redis layer

- `redis/operator_state.py` - direct `redis-py`, graceful degradation
- `redis/call_state.py` - same pattern for active calls. Consumed by the
  legacy PHP readers in `asterisk_config/legacy-php/`.
- `kvstore.py` and `redis-om` removed.

### CLI (Typer)

- `firenze users` - search, create, update, delete API users
- `firenze operator` - login, logout, change-status, list, info
- `firenze dnc` - check, add, remove, list
- `firenze did` - resolve
- `firenze calls` - list, clear
- `firenze migration` - bulk-import clients from the legacy Firenze API
  (includes `check-anis` audit / repair)
- `firenze fastapi` - misc FastAPI tools

### Tests

- `tests/test_dnc_service.py`, `test_credit_service.py`,
  `test_did_service.py`, `test_client_service.py`,
  `test_operator_service.py`, `test_operator_state.py`,
  `test_call_state.py`, `test_incoming_call_flow.py`,
  `test_incoming_call_http.py`

### Target dialplan written (not yet deployed)

- `asterisk_config/new/extensions.conf` - globals incl. `FIRENZE_API` and
  `TRUNK_STRIP_*` strip table
- `asterisk_config/new/extensions_zvn.conf` - trunks, supervisor,
  operator login/logout via CURL
- `asterisk_config/new/extensions_services.conf` - unified
  `[prepago-service]` with `[auth-ani]` / `[auth-pin]` / `[sub-post-auth]`
  / `[selecciona-operador]` / `[llama-operador]`

## In flight

- **Client data migration.** FonoTarot Latam is partially imported. Chile
  and Alotarot still read/write through the AUDIOTEX AGI path in the live
  `new_config/` dialplan. Use `firenze migration` to finish.
- **Dialplan hybridization.** `new_config/` already CURLs the new service
  for DNC, DID resolution, credit limit, and online-call insert/close, in
  parallel with the old AGI calls. We have not yet removed the AGI calls.
- **`ServiceNumber.asterisk_context`.** Still points at per-service
  contexts (`prepago-fonotarot-cl`, `prepago-alotarot`,
  `prepago-fonotarot-latam`). Target is `prepago-service` for every DID,
  which is what `asterisk_config/new/` assumes.

## Next (ordered by what unblocks deployment)

1. **Finish client data migration.** Chile + Alotarot rows into `Client` +
   `ClientAni`. Verify credit balances match the legacy DB.
2. **Remove the AGI-side credit writes from the live dialplan.** After the
   data migration, stop writing to AUDIOTEX so the two systems do not
   diverge. Equivalent for online-call insert/delete.
3. **Switch `ServiceNumber.asterisk_context` to `prepago-service`.** Do
   one DID at a time so rollback is cheap.
4. **Deploy `asterisk_config/new/` as the live dialplan.** Per-service
   contexts (`extensions_alotarot.conf`, `extensions_fonotarot.conf`) go
   away.
5. **Operator selection via CURL.** The hybrid `new_config/` still calls
   `${AUDIOTEX}` for `ejecutivos_disponibles`, `ejecutivo_aleatorio`, and
   `info_ejecutivo`. Endpoints exist; swap the dialplan.
6. **Credit push API for nuevo-fonotarot.**
   `POST /api/clients/{identifier}/credit`, JWT-scoped. Needed before
   nuevo-fonotarot can complete a purchase end to end.

## Cleanup debt (safe to delete once 1-5 land)

| Item | Why it is still around |
|---|---|
| `firenze/audiotex/` (Peewee models) | Read by old AGI path only |
| `asterisk_agi/` (AGI CLI scripts) | Invoked by live `${FIRENZE}` / `${AUDIOTEX}` globals |
| `firenze/tarot.py` | fastapi-crudrouter for `FonoTarotLatamClient` - superseded by unified `Client`. Not in the router tree. |
| `firenze/core.py` | Legacy unused router |
| `firenze/asterisk/` (empty package) | Leftover |
| `peewee` in `pyproject.toml` | Drops with `audiotex/` |
| `pystrix` in `pyproject.toml` | No longer imported anywhere; kept only because it is still in the lock |
| `AUDIOTEX_DSN` in config | Drops with `audiotex/` |
| `${FIRENZE}` and `${AUDIOTEX}` dialplan globals | Drop in step 4 above |
| `asterisk_config/current/` top-level `.conf` (older snapshot) | Not loaded - keep while we roll out, delete after |
| `asterisk_config/legacy-php/` Redis readers | Consumers need to switch to the new keys or be retired |
