# Firenze - Technical Reference

> Architecture overview: [new-architecture.md](new-architecture.md)
> Current migration state: [tasks.md](tasks.md)

This file documents what is actually in the repo and how it is wired. If
something here disagrees with the code, the code wins - update this file.

## Runtime

- Python >= 3.14
- Entry point: `run.py` -> `firenze.create_app()`
- Service: `gunicorn run:app -k uvicorn.workers.UvicornWorker --workers 1`
- Bound to `10.0.0.3:9002`
- systemd unit: `system_files/new-firenze.service`
- Logs: `/home/zvn/public_apps/new-firenze/logs/gunicorn-{access,error}.log`
- CLI entry point: `firenze` (installed via `pyproject.toml` scripts)

Older `asterisk_config/firenze.service` pins port 3002; it is the legacy
unit for the old Firenze CLI service and is being replaced by
`system_files/new-firenze.service` on 9002.

## Module layout (current)

```
firenze/
  __init__.py              - create_app()
  config.py                - Settings (pydantic-settings v2)
  database.py              - engine, SessionLocal, Base
  dependencies.py          - get_db(), get_redis()
  auth.py                  - API header auth + AdminAuth for sqladmin
  crud.py                  - user + event CRUD
  admin.py                 - sqladmin views
  exceptions.py            - GenericError, ProcessError, ConfigException
  core.py                  - legacy unused router (cleanup)
  tarot.py                 - fastapi-crudrouter for legacy client (cleanup)

  models/                  - SQLAlchemy 2.0
    base.py                - TimestampMixin
    user.py                - User
    service.py             - Service, ServiceNumber
    operator.py            - Operator, OperatorPhone
    call.py                - OnlineCalls, PostCallProcess
    client.py              - Client, ClientAni
    dnc.py                 - DoNotCall
    event.py               - Event

  schemas/                 - Pydantic v2
    common.py, user.py, client.py

  services/                - business logic
    dnc_service.py, credit_service.py, did_service.py,
    operator_service.py, client_service.py, call_service.py

  api/
    agi.py                 - /agi/* endpoints (dialplan-facing)

  redis/
    __init__.py            - get_redis() factory
    operator_state.py      - firenze:operator:{number}
    call_state.py          - firenze:call:{service}:{ani}

  cli/                     - Typer CLI
    users.py, operators.py, dnc.py, did.py, calls.py,
    migration.py, fastapi.py, services.py, user_management.py,
    fonotarot_latam.py, post_call.py, utils.py

  audiotex/                - legacy Peewee bridge (cleanup)
    database.py, models.py, schemas.py

  asterisk/                - empty package (cleanup)
```

## Configuration

`.env` holds secrets + DB URLs. Relevant dialplan-side globals live in
`asterisk_config/current/new_config/extensions.conf`:

```ini
[globals]
FIRENZE=/home/zvn/public_apps/firenze/.venv/bin/firenze
AUDIOTEX=/home/zvn/public_apps/firenze/asterisk_agi/audiotex.py
FIRENZE_API=http://localhost:9002/agi

; Leading chars to strip from E.164 operator number, per trunk.
; Numbers stored as 56XXXXXXXXX. Undefined trunk -> strip=0.
TRUNK_STRIP_didww-mia-out=0
TRUNK_STRIP_tecno=2
```

`asterisk_config/new/extensions.conf` adds `TRUNK_STRIP_tecnoera=2` and
`TRUNK_STRIP_claro1=2` and drops `FIRENZE` / `AUDIOTEX` entirely.

## Alembic

Config in `pyproject.toml` under `[tool.alembic]`. DB URL read from
`Settings`. Migrations in `alembic/versions/`:

```
39eca712cefd  init
afef1c6f7e7b  postcallprocess
90e828f91189  postcallprocess.processed
dc5ed20c815c  fonotarot_latam
384745ac99b2  fonotarot_latam.phone_number
b466f9f7ec96  fonotarot_latam.pin_calc
3d332fe36da6  operator + operator_phone
a1b2c3d4e5f6  operator_phone.trunk
f479283e23a2  unified client model
124ca3374fe3  add client_ani table, drop ani column
a8c5e1f2b9d3  service.auth_method, service.intro_audio, operator.audio_file  <- head
```

## AGI endpoints

All mounted under `/agi` by `firenze.api.agi.agiRouter`. Responses are
flat JSON designed for `JSON_DECODE()`. No JWT.

### DNC

```
GET /agi/dnc/{ani}
-> {"dnc": "YES"}  or  {"dnc": "NO"}
```

### Service / DID resolution

```
GET /agi/services/did/{did}
-> {"siguiente": "prepago-service",
    "servicio":  "alotarot",
    "auth_method": "ani",
    "intro_audio": "zvn/intro-alotarot"}

not found:
-> {"siguiente": "", "servicio": "", "auth_method": "", "intro_audio": ""}
```

### Credit limit

Replaces the old `[limite-saldo]` dialplan ladder.

```
GET /agi/credits/limit?seconds=N
-> {"timeout": 900, "audio": "zvn/saldo/15", "minutes": 15}
zero / negative balance:
-> {"timeout": 1, "audio": "", "minutes": 0}
```

### Client lookup

```
GET /agi/clients/lookup?service={slug}&identifier={ani_or_pin}
found:
-> {"clientid": 42, "segundos": 1800}
not found:
-> {"clientid": 0, "segundos": 0}
```

Lookup order inside `client_service.lookup`:
1. `Client` where `(service_id, pin=identifier)` - PIN-auth services
2. `ClientAni` where `(service_id, ani=identifier)` -> parent `Client` - ANI-auth services
3. otherwise `{clientid: 0, segundos: 0}`

### Credit deduction

```
POST /agi/clients/{service}/{client_id}/deduct
form: seconds=N
-> {"ok": true, "remaining": 1200}
```

### Online call tracking

```
POST /agi/calls/online
form: service, ani, did, client_id, operator (default 0)
-> {"ok": true}
-> {"ok": false, "reason": "call-already-active"}

GET /agi/calls/online/{service}/{ani}
-> {"llamada_activa": "true"}  or  {"llamada_activa": "false"}

POST /agi/calls/online/{service}/{ani}/assign
form: operator=N
-> {"ok": true}  or  {"ok": false, "reason": "call-not-found"}

POST /agi/calls/online/{service}/{ani}/close
form: _=1          (dummy body - Asterisk CURL only does GET or POST-body)
-> {"ok": true}    (idempotent)
```

### Operator menu

```
GET /agi/operators/menu
-> {"disponibles": 3,
    "audio_str": "zvn/tarotistas/maria&zvn/tarotistas/jose&zvn/tarotistas/ana"}
```

`audio_str` is built from `Operator.audio_file`, ordered by
`Operator.option`. Operators without an `audio_file` count toward
`disponibles` but are omitted from the audio string.

### Operator select (atomic)

Uses `SELECT FOR UPDATE` so two concurrent callers cannot grab the same
operator. Random mode shuffles candidates and locks one at a time.

```
POST /agi/operators/select
form: mode=random
form: mode=option&selection=03

success:
-> {"ok": true,
    "operador_numero":   "1001",
    "operador_nombre":   "Maria",
    "operador_telefono": "56912345678",
    "operador_trunk":    "claro1"}

failure:
-> {"ok": false, "reason": "operator-busy"}
-> {"ok": false, "reason": "no-operators"}
-> {"ok": false, "reason": "no-phone-configured"}
```

### Operator release

```
POST /agi/operators/{number}/release
form: _=1
-> {"ok": true}
```

Stamps `lastcall` in Redis so "forgot to logout" detection has a signal.

### Operator login / logout (dialplan)

```
POST /agi/operators/by-phone/{ani}/login   -> {"ok": true}
POST /agi/operators/by-phone/{ani}/logout  -> {"ok": true}
```

### Operator info (lookup, no claim)

Read-only lookups used between `/operators/menu` and `/operators/select`.
The dialplan plays the menu, the caller picks an option, the dialplan
calls one of these to translate the input into the operator's contact
info, then later calls `/operators/select` to atomically claim. Splitting
lookup from claim keeps operators free during the 5-10s menu/audio
window; the atomic `SELECT FOR UPDATE` in `/operators/select` resolves
the resulting race. `loggedin` and `available` in the response are
advisory only - trust `/operators/select` for the real claim.

```
GET /agi/operators/by-option/{option}     (option: "1" or "01", zero-padded internally)
GET /agi/operators/by-ani/{ani}           (ani: phone number registered to operator)

success (same shape from both):
-> {"ok": true,
    "operador_numero":   "1001",
    "operador_nombre":   "Maria",
    "operador_telefono": "56912345678",
    "operador_trunk":    "claro1",
    "loggedin":          true,
    "available":         true}

failure:
-> {"ok": false, "reason": "not-found"}
-> {"ok": false, "reason": "no-phone-configured"}
```

## Redis / Valkey

Connection managed by `firenze.redis.get_redis()` (FastAPI dependency).
Graceful degradation: if Redis is unavailable, service calls log a warning
and continue with MySQL only.

### Keys

```
firenze:operator:{number}    Hash fields: loggedin, available, lastcall
firenze:call:{service}:{ani} Hash fields: did, operator, client_id, created_at
```

TTL on both: 24h.

### Consumers

- `services/operator_service.py` and `services/call_service.py` write both
  MySQL and Redis.
- `api/agi.py` reads via those services.
- `asterisk_config/legacy-php/onlinecalls_redis.php` and
  `operators_redis.php` are external readers used by legacy dashboards.
  They consume the same keys.

## Dialplan

Three copies live under `asterisk_config/`:

| Path | Role |
|---|---|
| `current/*.conf` (top level) | Older snapshot, pure AGI. Not loaded. Kept for reference. |
| `current/new_config/*.conf` | Currently loaded by Asterisk. Hybrid: old AGI calls + new CURL calls side by side. |
| `new/*.conf` | Target: CURL only, unified `[prepago-service]`. Not deployed. |

### Hybrid (live) - `current/new_config/`

Top of each service context runs both paths. Example from
`extensions_fonotarot.conf` `[prepago-fonotarot-cl]`:

```ini
; new path (CURL)
same => n,Set(response=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani})})
; old path (still writes to legacy)
same => n,Agi(${FIRENZE},online-calls,search,${servicio},${ani},${clientid})
```

Both runtimes see the event. The `JSON_DECODE` consumers still read from
the old path's channel vars where the new path has not fully replaced it.

### Target - `asterisk_config/new/`

Three files only:

```
extensions.conf            - globals, honeypot, #include zvn + services
extensions_zvn.conf        - inbound trunks, [selecciona-servicio],
                             supervisor, tarotista-login/-logout (CURL)
extensions_services.conf   - unified flow:
                               [prepago-service]   -> DNC + intro + dispatch
                               [auth-ani]          -> client lookup by ANI
                               [auth-pin]          -> client lookup by PIN
                               [sub-post-auth]     -> credit limit + insert call
                               [saldo-insuficiente]
                               [selecciona-operador] (menu + select + assign)
                               [llama-operador]    (dial + post-call hooks)
```

Two per-service files (`extensions_alotarot.conf`,
`extensions_fonotarot.conf`) go away entirely - `Service.auth_method` and
`Service.intro_audio` drive the branching inside `[prepago-service]`.

### CURL conventions in the target dialplan

- GET: `${CURL(url)}`
- POST with body: `${CURL(url,field=val&field2=val2)}`
- No `CURLOPT()` - this Asterisk build does not support `httpcustom` or
  `postfields`.
- Endpoints that need no semantic body take `_=1` as a dummy form field,
  because Asterisk's `CURL()` only reliably does GET or POST-with-body.

### Trunk strip table

All operator phone numbers are stored as E.164 (`56XXXXXXXXX`). Each
outbound trunk expects a different prefix. The dialplan strips at dial
time using a globals lookup:

```ini
same => n,Set(dial_num=${OPERATOR_TEL:${TRUNK_STRIP_${OPERATOR_TRUNK}}})
same => n,Dial(PJSIP/${dial_num}@${OPERATOR_TRUNK})
```

Default is strip=0 (full E.164) when the trunk is not in the table.

## Dead code to remove (cross-ref tasks.md)

- `firenze/tarot.py`, `firenze/core.py`, `firenze/asterisk/`
- `firenze/audiotex/` + `peewee` dependency + `AUDIOTEX_DSN` config
- `asterisk_agi/` (old AGI CLI scripts)
- `pystrix` dependency (no longer imported)
- `asterisk_config/current/*.conf` top-level snapshot (once `new/` is live)
