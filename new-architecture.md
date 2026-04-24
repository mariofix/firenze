# Firenze - Architecture

> Current state of migration: [tasks.md](tasks.md)
> Implementation reference (endpoints, configs, code): [tech.md](tech.md)

## What Firenze is

Firenze is the communications and Asterisk management layer for the FonoTarot
platform. It owns call routing, operator state, credit tracking, and active-call
state. It is one of two services in the stack.

| Concern | Owner |
|---|---|
| Storefront, payments, user accounts | nuevo-fonotarot (Flask) |
| Asterisk call flow, operators, credits, DIDs, DNC | Firenze (FastAPI) |
| Communication | nuevo-fonotarot -> Firenze HTTP API |

Firenze knows: client identifiers, credit balances, operators, services,
active calls, DNC list.

Firenze does not know: how credits were purchased, payment providers,
storefront passwords, marketing touches.

## Asterisk integration: CURL from dialplan

Asterisk talks to Firenze via HTTP on localhost. Every dialplan decision
point that used to spawn a Python AGI subprocess (~500-1500ms per spawn)
becomes a `CURL()` + `JSON_DECODE()` to the always-running FastAPI service
(~5-10ms per call).

```
; before: spawn Python process
same => n,Agi(${FIRENZE},services,did,${did})

; after: HTTP to running server
same => n,Set(resp=${CURL(${FIRENZE_API}/services/did/${did})})
same => n,Set(siguiente=${JSON_DECODE(resp,siguiente)})
```

A typical call used to invoke AGI 5-6 times (3-9s of caller-perceived silence).
The target is 2-4 CURL calls totalling 10-60ms.

### Why not ARI

ARI (Asterisk REST Interface, WebSocket-driven) makes Firenze a stateful
always-on dependency: if it dies, calls die. It also requires rewriting all
dialplan logic in Python and is harder to debug than stateless HTTP. At ~6
concurrent channels that cost is not justified.

### Why not stay on AGI

AGI works but spawns a fresh Python interpreter per call step. Loading
SQLAlchemy + Typer + Redis on every spawn dominates the call latency on a
2GB Linode.

### AGI endpoint security

The `/agi/` endpoints are dialplan-facing and must be fast. No JWT auth -
Asterisk's `CURL()` cannot manage token flows. Protection is binding to
localhost plus an optional static API key header. Firenze's public endpoints
(credit API for nuevo-fonotarot, admin panel) keep JWT.

## Domain model overview

- **Service** - a saleable service (`fonotarot-cl`, `alotarot`, `fonotarot-latam`).
  Carries `auth_method` ("ani" or "pin") and `intro_audio`. Has many
  `ServiceNumber`s (DIDs).
- **Client** - unified table keyed by `(service_id, client_id)`. Holds
  `credits` (seconds), `pin` when auth_method is pin. A `ClientAni` child
  table maps N ANIs to one client for ANI-auth services.
- **Operator** - internal number, IVR `option` digits, `audio_file`. Related
  `OperatorPhone` rows hold contact numbers and outbound trunks.
- **OnlineCall** - row per active call, unique on `(service, ani)`. Deleted
  on hangup.
- **DoNotCall** - ANIs that must be refused immediately.

See [tech.md](tech.md) for exact columns.

## Operator state: MySQL source of truth + Redis hot cache

MySQL is authoritative. Redis/Valkey is a fast-read cache consumed by both
the call flow (`/agi/operators/menu`) and external legacy PHP readers.

- Write path: every state change (login, logout, select, release) writes to
  both MySQL and Redis. Redis write is a best-effort mirror - if Redis is
  down, MySQL still commits and we log the degradation.
- Read path: menu + availability read from Redis first, fall back to MySQL.
- TTL 24h: naturally handles "operator forgot to logout".
- Per-operator opt-in via `Operator.enable_valkey` - lets us migrate
  operators into the cache one at a time.

Same pattern for active calls (`firenze:call:{service}:{ani}`).

## Deployment

```
+--------------------------------------+
|          Linode (2GB)                |
|                                      |
|  +----------+     +--------------+   |
|  | Asterisk | --> |   Firenze    |   |
|  |  PJSIP   |     |   FastAPI    |   |
|  |  :5060   |     |   :9002      |   |
|  +----------+     +--------------+   |
|        |                 |           |
|        |          +-------------+    |
|        |          | MySQL+Redis |    |
|        |          +-------------+    |
|        |                             |
|   CURL to localhost:9002             |
+--------------------------------------+
```

- Firenze runs as a systemd service: `gunicorn run:app -k uvicorn.workers.UvicornWorker`
- One worker is enough at current load
- Asterisk hits Firenze via `${FIRENZE_API}` on localhost
- Scaling = duplicate the entire Linode (e.g. European region)
- No Docker for Asterisk - bare metal, hand-rolled

## Tech stack

| Layer | Technology |
|---|---|
| Web API | FastAPI + Uvicorn + Gunicorn |
| ORM | SQLAlchemy 2.0 (`Mapped` / `mapped_column`) |
| Migrations | Alembic, config in `pyproject.toml` |
| Validation | Pydantic v2 + pydantic-settings |
| DB | MySQL via PyMySQL |
| Cache / hot state | Redis/Valkey via `redis-py` |
| Admin | sqladmin at `/boss` |
| CLI | Typer - admin + migration + debug only, no longer in the call hot path |
| Auth | JWT (python-jose) + direct bcrypt |

The CLI is still shipped (entry point `firenze`) but Asterisk no longer
invokes it during calls. All call-time traffic is HTTP.
