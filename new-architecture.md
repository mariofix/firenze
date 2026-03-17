# Firenze — New Architecture

## Overview

Firenze is the communications and Asterisk management layer for the FonoTarot platform. It handles call routing, operator management, credit tracking, and real-time call state. It does NOT handle payments, marketing, or public-facing UX — that's nuevo-fonotarot.

### Boundaries

| Concern | Owner |
|---|---|
| Storefront, payments, user accounts | nuevo-fonotarot (Flask) |
| Asterisk call flow, operators, credits, DIDs, DNC | Firenze (FastAPI) |
| Communication | nuevo-fonotarot → Firenze HTTP API (credit push after purchase) |

Firenze knows: client identifiers, credit balances, operators, services, active calls.
Firenze doesn't know: how credits were purchased, payment providers, user passwords on the storefront.

---

## Implementation Status

### Done

- [x] Pydantic v2 migration (`orm_mode` → `from_attributes`)
- [x] Alembic configured via `pyproject.toml`, reads DB URL from settings
- [x] `services/dnc_service.py` — `check_dnc(db, ani) -> bool`
- [x] `services/credit_service.py` — `compute_call_limit(seconds) -> {timeout, audio, minutes}`
- [x] `api/agi.py` — `GET /agi/dnc/{ani}`, `GET /agi/credits/limit?seconds=N`, `GET /agi/services/did/{did}`
- [x] `admin.py` — sqladmin view for DNC list (searchable by ANI)
- [x] Systemd service file + install script

### In Progress / Next

- [ ] `services/operator_service.py` — login/logout/select/release backed by MySQL + Redis
- [ ] `services/call_service.py` — online call tracking
- [ ] `services/did_service.py` — DID → asterisk context resolution
- [ ] `api/agi.py` — remaining AGI endpoints (operators, calls, client lookup, credit deduction)
- [ ] Split `models.py` into `models/` directory (one file per domain)
- [ ] Split `schemas.py` into `schemas/` directory
- [ ] Unified `Client` model (replaces `FonoTarotLatamClient` + all Peewee client tables)
- [ ] Replace `redis-om` (`kvstore.py`) with direct `redis-py` in `operator_service.py`
- [ ] Remove `fastapi-crudrouter` (`tarot.py`)
- [ ] Remove `pystrix` dependency (once all AGI CLI calls are replaced by CURL)

### Planned (later phases)

- [ ] Credit API for nuevo-fonotarot (`POST /api/clients/{identifier}/credit`)
- [ ] Drop Peewee + `audiotex/` directory
- [ ] Dialplan cleanup (remove `limite-saldo` ladder, consolidate per-service contexts)

---

## Current Module Structure

Actual state on `new-architecture` branch (as of 2026-03-16):

```
firenze/
├── __init__.py              # create_app() — FastAPI factory
├── run.py                   # gunicorn/uvicorn entry point
├── config.py                # pydantic-settings v2
├── database.py              # engine, session factory, Base
├── dependencies.py          # get_db() — single definition
├── models.py                # all SQLAlchemy models (single file, to be split)
├── schemas.py               # all Pydantic v2 schemas (single file, to be split)
├── auth.py                  # JWT, OAuth2, AdminAuth for sqladmin
├── crud.py                  # user + event CRUD helpers
├── admin.py                 # sqladmin DNC view
├── core.py                  # legacy coreRouter (unused, to be removed)
├── kvstore.py               # redis-om Operator HashModel (to be replaced)
├── tarot.py                 # fastapi-crudrouter for FonoTarotLatamClient (to be removed)
├── exceptions.py            # GenericError, ProcessError, ConfigException
│
├── services/
│   ├── dnc_service.py       # ✅ check_dnc(db, ani) -> bool
│   └── credit_service.py    # ✅ compute_call_limit(seconds) -> dict
│
├── api/
│   └── agi.py               # ✅ /agi/dnc/{ani}, /agi/credits/limit
│
├── cli/
│   ├── __init__.py          # Typer root + shared context (agi, db, logger)
│   ├── operators.py         # login, logout, change_status, list, info (MySQL + Redis)
│   ├── online_calls.py      # insert, delete, update, list
│   ├── fonotarot_latam.py   # pin lookup, consumo (credit deduction)
│   ├── post_call.py         # add post-call process records
│   ├── services.py          # did lookup → asterisk context
│   └── user_management.py   # search, create, update, delete API users
│
└── audiotex/                # legacy Peewee bridge (migration target, to be dropped)
    ├── database.py          # Peewee connection to AUDIOTEX_DSN
    ├── models.py            # FTChile, Alotarot, Operators, Calls (Peewee)
    └── schemas.py           # Pydantic schemas for audiotex models
```

---

## Target Module Structure

What the structure should look like when the refactor is complete:

```
firenze/
├── __init__.py              # create_app() — FastAPI factory
├── config.py                # Settings (pydantic-settings v2)
├── database.py              # Engine, SessionLocal, Base — single definition
├── dependencies.py          # get_db(), get_settings() — shared FastAPI deps
│
├── models/                  # SQLAlchemy models (one file per domain)
│   ├── __init__.py          # re-exports all models
│   ├── user.py              # User (API users with scopes)
│   ├── service.py           # Service, ServiceNumber
│   ├── operator.py          # Operator, OperatorPhone
│   ├── call.py              # OnlineCall, PostCallProcess
│   ├── client.py            # Client (unified, replaces all legacy tables)
│   ├── dnc.py               # DoNotCall
│   └── event.py             # Event
│
├── schemas/                 # Pydantic v2 schemas
│   ├── __init__.py
│   ├── client.py
│   ├── operator.py
│   └── ...
│
├── services/                # Business logic layer
│   ├── dnc_service.py       # ✅ done
│   ├── credit_service.py    # ✅ done
│   ├── operator_service.py  # Login/logout, availability, select, release
│   ├── call_service.py      # Online call tracking, post-call processes
│   └── did_service.py       # DID resolution → asterisk context
│
├── api/                     # FastAPI routers
│   ├── __init__.py
│   ├── auth.py              # POST /token — JWT
│   ├── core.py              # health + event log
│   ├── clients.py           # Credit API (nuevo-fonotarot calls this)
│   ├── operators.py         # Operator management (admin-facing)
│   ├── calls.py             # Online calls API
│   └── agi.py               # Dialplan-facing endpoints (flat JSON, fast)
│
├── admin/                   # sqladmin views
│   ├── __init__.py
│   └── views.py
│
├── cli/                     # Typer CLI (admin/debug, NOT called by Asterisk)
│   ├── __init__.py
│   ├── services.py
│   ├── online_calls.py
│   ├── operators.py
│   └── dnc.py
│
└── redis/                   # Redis/Valkey layer (replaces kvstore.py + redis-om)
    ├── __init__.py
    └── operator_state.py    # Operator availability read/write
```

### Design principle: services/ layer

Both the API routes and CLI commands call the same service functions. No business logic lives in routers or CLI commands — they're just interfaces.

```
Asterisk (CURL) → api/agi.py → services/operator_service.py → MySQL + Redis
Admin (browser) → api/operators.py → services/operator_service.py → MySQL + Redis
Terminal         → cli/operators.py → services/operator_service.py → MySQL + Redis
```

---

## Deployment

Single 2GB Linode = one complete unit:

```
┌─────────────────────────────────────┐
│              Linode (2GB)            │
│                                     │
│  ┌───────────┐    ┌──────────────┐  │
│  │  Asterisk  │───│   Firenze    │  │
│  │  (PJSIP)  │   │  (FastAPI)   │  │
│  │  port 5060 │   │  port 3002   │  │
│  └───────────┘    └──────────────┘  │
│        │               │            │
│        │          ┌────┴─────┐      │
│        │          │  MySQL   │      │
│        │          │  Redis   │      │
│        │          └──────────┘      │
│        │                            │
│   CURL to 127.0.0.1:3002           │
│   (replaces AGI subprocess spawn)   │
└─────────────────────────────────────┘
```

- Firenze runs as a systemd service via gunicorn + uvicorn worker
- Asterisk communicates with Firenze via HTTP (CURL from dialplan) on localhost
- Scaling = duplicate the entire Linode (e.g., for a European region)
- No Docker for Asterisk — bare metal on the Linode

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web API | FastAPI + Uvicorn + Gunicorn |
| ORM | SQLAlchemy 2.0 (single ORM, drop Peewee when migration complete) |
| Migrations | Alembic |
| Validation | Pydantic v2 + pydantic-settings |
| DB | MySQL (PyMySQL) |
| Cache/State | Redis/Valkey (direct redis-py, replacing redis-om) |
| Admin | sqladmin |
| CLI | Typer (admin/debug tool, no longer in the call hot path) |
| Auth | JWT (python-jose) + bcrypt/passlib |

### To be removed

- **Peewee** — legacy audiotex DB access, replaced by SQLAlchemy as migration completes
- **pystrix** — only needed for AGI protocol; CURL approach doesn't need it
- **fastapi-crudrouter** — used in `tarot.py`, drop when unified Client model is in place
- **redis-om** — replace with direct redis-py in `operator_service.py`

---

## Asterisk Integration: CURL Replaces AGI

### Why not AGI

The current approach spawns a full Python process per AGI call. Each spawn loads the Python interpreter + all imports (SQLAlchemy, Typer, Redis, etc.) — roughly 500-1500ms on a 2GB Linode. Some call flows invoke AGI 5-6 times, adding 3-9 seconds of overhead that the caller hears as silence.

### Why not ARI

ARI (Asterisk REST Interface) provides real-time call control via WebSocket. Powerful, but:
- Makes Firenze a stateful, always-on dependency — if it dies, calls die
- Requires rewriting all dialplan logic in Python
- Much harder to debug than stateless HTTP calls
- Overkill for ~6 concurrent channels

### The approach: CURL from dialplan

Firenze's FastAPI server is already running. Asterisk's built-in `CURL()` and `JSON_DECODE()` functions make HTTP calls to it on localhost:

```ini
; Before: spawn Python process (~1s)
same => n,Agi(${FIRENZE},services,did,${did})

; After: HTTP to running server (~5-10ms)
same => n,Set(response=${CURL(http://127.0.0.1:3002/agi/services/did/${did})})
same => n,Set(siguiente=${JSON_DECODE(response,siguiente)})
```

**Performance**: 5-6 AGI spawns per call (3-9s total) → 2-4 CURL calls per call (10-60ms total).

The CLI stays as an admin/debugging tool (`firenze operator list`, `firenze client lookup`, etc.) but is no longer invoked by Asterisk during calls.

### AGI endpoint security

The `/agi/` endpoints are dialplan-facing and must be fast:
- No JWT auth (Asterisk CURL can't manage token flows)
- Protected by binding to localhost or LAN, plus an optional static API key header
- Firenze's public-facing endpoints (nuevo-fonotarot credit API, admin panel) keep JWT auth

---

## AGI Endpoints (`/agi/`)

Flat JSON responses designed for `JSON_DECODE()` in the dialplan.

### DNC check ✅ implemented

```
GET /agi/dnc/{ani}

Response:
  {"dnc": "YES"}
  {"dnc": "NO"}
```

Dialplan — add early in each service context, after `ani` is set:

```ini
same => n,Set(response=${CURL(${FIRENZE_API}/dnc/${ani})})
same => n,GotoIf($["${JSON_DECODE(response,dnc)}" = "YES"]?hangup-dnc,s,1:)
```

### Credit limit lookup ✅ implemented

Replaces the `[limite-saldo]` hardcoded ladder in the dialplan.

```
GET /agi/credits/limit?seconds=N

Response:
  {"timeout": 900, "audio": "zvn/saldo/15", "minutes": 15}
  {"timeout": 1, "audio": "", "minutes": 0}    # zero/negative balance
```

Dialplan — replace `Gosub(limite-saldo,s,1)` with:

```ini
same => n,Set(response=${CURL(${FIRENZE_API}/credits/limit?seconds=${segundos})})
same => n,Set(TIMEOUT(absolute)=${JSON_DECODE(response,timeout)})
same => n,Set(saldo_audio=${JSON_DECODE(response,audio)})
same => n,GotoIf($["${saldo_audio}" = ""]?:)
same => n,Playback(${saldo_audio})
```

### Service/DID resolution ✅ implemented

```
GET /agi/services/did/{did}

Response:
  {"siguiente": "prepago-fonotarot-cl"}    # context to goto
  {"siguiente": ""}                         # DID not found
```

Dialplan — replace `Agi(${FIRENZE},services,did,${did})` in `[selecciona-servicio]`:

```ini
[selecciona-servicio]
exten => _X.,1,NoOp(Vamos a seleccionar el servicio)
 same => n,Set(AGIEXITONHANGUP=yes)
 same => n,Set(response=${CURL(${FIRENZE_API}/services/did/${did})})
 same => n,Set(siguiente=${JSON_DECODE(response,siguiente)})
 same => n,GotoIf($["${siguiente}" = ""]?no-service,s,1:)
 same => n,Goto(${siguiente},s,1)
exten => h,1,NoOp(Goodbye)
```

### Client lookup — PIN and ANI (planned)

```
GET /agi/clients/lookup?service={slug}&identifier={ani_or_pin}

Response (found):
  {"clientid": 42, "segundos": 1800}

Response (not found):
  {"clientid": 0, "segundos": 0}
```

### Credit deduction (planned)

```
POST /agi/clients/{client_id}/deduct?seconds={n}&service={slug}

Response:
  {"ok": true, "credits": 1200}
```

### Online calls (planned)

```
POST /agi/calls/online
  Body/params: service, ani, did, operator, client_id
Response: {"ok": true}

DELETE /agi/calls/online/{service}/{ani}
Response: {"ok": true}

PATCH /agi/calls/online/{service}/{ani}?operator={num}
Response: {"ok": true}

GET /agi/calls/online/{service}/{ani}
Response: {"llamada_activa": "true"} or {"llamada_activa": "false"}
```

### Operator menu (planned)

```
GET /agi/operators/menu

Response:
  {
    "disponibles": 3,
    "audio_str": "zvn/tarotistas/maria&zvn/tarotistas/jose&zvn/tarotistas/ana"
  }
```

### Operator select — atomic verify + mark busy (planned)

```
POST /agi/operators/select?mode=option&selection=03
POST /agi/operators/select?mode=random

Response (success):
  {
    "ok": true,
    "operador_nombre": "Maria",
    "operador_telefono": "56912345678",
    "operador_numero": "1001",
    "operador_trunk": "claro1"
  }

Response (unavailable):
  {"ok": false, "reason": "operator-busy"}
```

### Operator release (planned)

```
POST /agi/operators/{number}/release
Response: {"ok": true}
```

### Operator login/logout from dialplan (planned)

```
POST /agi/operators/by-phone/{ani}/login
POST /agi/operators/by-phone/{ani}/logout
Response: {"ok": true}
```

---

## Domain Models

### Service

```
Service:
  id: int (PK)
  name: str
  slug: str (unique, e.g. "fonotarot-cl", "alotarot", "fonotarot-latam")
  auth_method: str ("ani" | "pin")
  active: bool
  numbers: [ServiceNumber...]

ServiceNumber:
  id: int (PK)
  did: str (unique, e.g. "56229402147")
  active: bool
  asterisk_context: str (e.g. "prepago-fonotarot-cl")
  service_id: FK → Service
```

### Client (unified — planned)

Replaces: `FonoTarotLatamClient` (SQLAlchemy) + `FTChileClientId`/`FTChileCreditos`/`AlotarotClientId`/`AlotarotCreditos` (legacy Peewee).

```
Client:
  client_id: int (PK)
  service_id: FK → Service
  identifier: str            # ANI or PIN, depending on service.auth_method
  credits: int               # seconds (balance)
  email: str (nullable)
  full_name: str (nullable)
  phone_number: str (nullable)
  created_at: datetime
  modified_at: datetime
```

### Operator

```
Operator:
  id: int (PK)
  number: int (unique)       # internal operator number (e.g. 1001)
  name: str
  description: text (nullable)
  option: str(2) (unique)    # IVR digit(s) the caller presses
  loggedin: bool
  available: bool
  lastcall: datetime
  trunk: str                 # preferred outbound trunk
  numbers: [OperatorPhone...]

OperatorPhone:
  id: int (PK)
  number: str                # phone number to dial
  enabled: bool
  contact: bool              # primary contact number
  pin: str(4) (nullable)
  operator_id: FK → Operator
```

### OnlineCall

```
OnlineCall:
  id: int (PK)
  service: str
  ani: str
  did: str
  operator: int
  client_id: int
  created_at: datetime
```

---

## Operator State: MySQL + Redis

MySQL is the source of truth. Redis is the fast-read cache for the call flow.

### Write path (login, logout, select, release)

```
operator_service.login(number):
  MySQL: UPDATE operator SET loggedin=1, available=1, lastcall=now()
  Redis: HSET operator:{number} loggedin 1 available 1 lastcall {ts}
  Redis: EXPIRE operator:{number} 86400
```

### Read path (menu, disponibles)

```
operator_service.get_available():
  Redis: SCAN/GET all operator:* keys WHERE loggedin=1 AND available=1
  (fallback to MySQL if Redis unavailable)
```

Redis TTL (24h) handles "operator forgot to logout" naturally.

---

## Credit API (`/api/clients/`) — planned

Authenticated endpoints for nuevo-fonotarot integration.

```
POST /api/clients/{identifier}/credit
  Headers: Authorization: Bearer <jwt>  (scope: "credits")
  Body: {"amount": 1800, "service": "fonotarot-latam", "reference": "order-123"}
Response: {"credits": 3600, "client_id": 42}

GET /api/clients/{identifier}/credit?service={slug}
  Headers: Authorization: Bearer <jwt>
Response: {"credits": 3600, "client_id": 42}
```

Firenze receives "add X seconds to client Y" and trusts the caller. It doesn't know about payments, orders, or providers.

---

## Current Dialplan (production)

The actual dialplan split across three `#include` files from `extensions.conf`.

### extensions.conf (globals + base contexts)

```ini
[general]
static=yes
clearglobalvars=no

[globals]
FIRENZE=/home/zvn/public_apps/firenze/.venv/bin/firenze
AUDIOTEX=/home/zvn/public_apps/firenze/asterisk_agi/audiotex.py

[honeypot]
exten => _X.,1,NoOp(${PJSIP_HEADER(read,from)})
 same => n,Playback(tt-monkeys)
exten => h,1,NoOp(Goodbye)

[public]
include => honeypot

[default]
include => honeypot

#include extensions_zvn.conf
#include extensions_fonotarot.conf
#include extensions_alotarot.conf
```

### extensions_zvn.conf — inbound trunks + operator login/logout

```ini
[selecciona-servicio]
; ← still using AGI subprocess; migrate to CURL /agi/services/did/{did}
exten => _X.,1,NoOp(Vamos a seleccionar el servicio)
 same => n,Set(AGIEXITONHANGUP=yes)
 same => n,Agi(${FIRENZE},services,did,${did})
 same => n,GotoIf($["${siguiente}" = ""]?no-service,s,1:)
 same => n,Goto(${siguiente},s,1)
exten => h,1,NoOp(Goodbye)

[no-service]
exten => s,1,Noop(DID ${did} no Reconocido)
 same => n,Set(CDR(userfield)=${did})
 same => n,Hangup(27)
exten => h,1,Log(error,"${did} Not Found from ${ani} - Headers: ${PJSIP_HEADER(read,from)}")

[inbound-didww]
exten => _X.,1,Noop(Llamada entrante DIDWW)
 same => n,Set(CALLERID(num)=${FILTER(0123456789,${CALLERID(num)})})
 same => n,Set(did=${EXTEN})
 same => n,Set(ani=${CALLERID(num)})
 same => n,Goto(selecciona-servicio,${did},1)

[inbound-tecnoera]
exten => _X.,1,Noop(Llamada entrante Tecnoera)
 same => n,Set(CALLERID(num)=${FILTER(0123456789,${CALLERID(num)})})
 same => n,Set(did=56${EXTEN})
 same => n,Set(ani=56${CALLERID(num):-9})
 same => n,Goto(selecciona-servicio,${did},1)

[inbound-claro1]
exten => _X.,1,Noop(Llamada entrante Claro)
 same => n,Set(CALLERID(num)=${FILTER(0123456789,${CALLERID(num)})})
 same => n,Set(did=${EXTEN})
 same => n,Set(ani=${CALLERID(num)})
 same => n,Goto(selecciona-servicio,${did},1)

[outbound-didww]
exten => _56.,1,Noop(Marcando didww-mia-out)
 same => n,Set(REC_FILE=${STRFTIME(${EPOCH},America/Santiago,%Y/%m)}/${servicio}-${clientid}-${ani}-${OPERATOR_NUM}-${UNIQUEID}.gsm)
 same => n,MixMonitor(${REC_FILE},ab)
 same => n,Set(CALLERID(num)=56229402147)
 same => n,Dial(PJSIP/${EXTEN}@didww-mia-out)
 same => n,StopMixMonitor()
 same => n,Goto(${DIALSTATUS},1)
exten => BUSY,1,Noop(Telefono Ocupado)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => CONGESTION,1,Noop(Red Ocupada)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => CHANUNAVAIL,1,Noop(Red Ocupada)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => FAILED,1,Noop(Numero Malo)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => h,1,NoOp(Goodbye)

[outbound-claro1]
exten => _56.,1,Noop(Marcando claro1)
 same => n,Set(REC_FILE=${STRFTIME(${EPOCH},America/Santiago,%Y/%m)}/${servicio}-${clientid}-${ani}-${OPERATOR_NUM}-${UNIQUEID}.gsm)
 same => n,MixMonitor(${REC_FILE},ab)
 same => n,Set(CALLERID(num)=56222301515)
 same => n,Dial(PJSIP/${EXTEN}@claro1)
 same => n,StopMixMonitor()
 same => n,Goto(${DIALSTATUS},1)
exten => BUSY,1,Noop(Telefono Ocupado)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => CONGESTION,1,Noop(Red Ocupada)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => CHANUNAVAIL,1,Noop(Red Ocupada)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => FAILED,1,Noop(Numero Malo)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => h,1,NoOp(Goodbye)

[outbound-ejecutivos]
exten => _56.,1,Noop(Marcando a ${OPERATOR_NUM} via ${OPERATOR_TRUNK})
 same => n,Set(REC_FILE=${STRFTIME(${EPOCH},America/Santiago,%Y/%m)}/${servicio}-${clientid}-${ani}-${OPERATOR_NUM}-${UNIQUEID}.gsm)
 same => n,MixMonitor(${REC_FILE},ab)
 same => n,Set(CALLERID(num)=56222301515)
 same => n,Dial(PJSIP/${EXTEN:2}@${OPERATOR_TRUNK})
 same => n,StopMixMonitor()
 same => n,Goto(${DIALSTATUS},1)
exten => BUSY,1,Noop(Telefono Ocupado)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => CONGESTION,1,Noop(Red Ocupada)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => CHANUNAVAIL,1,Noop(Red Ocupada)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => FAILED,1,Noop(Numero Malo)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => h,1,NoOp(Goodbye)

[outbound-supervisor]
exten => s,1,Noop(Marcando al supervisor)
 same => n,Set(CALLERID(num)=222301515)
 same => n,Set(REC_FILE=${STRFTIME(${EPOCH},America/Santiago,%Y/%m)}/${ani}-supervisor-${UNIQUEID}.gsm)
 same => n,MixMonitor(${REC_FILE},ab)
 same => n,Dial(PJSIP/963349072@tecno)
 same => n,StopMixMonitor()

[tarotista-login]
; ← still uses AUDIOTEX; migrate to POST /agi/operators/by-phone/{ani}/login
exten => s,1,Noop(Login Tarotista)
 same => n,Agi(${AUDIOTEX},info_ejecutivo,telefono,${ani})
 same => n,Agi(${AUDIOTEX},cambia_login,${operador_numero},1,1)
 same => n,Playback(zvn/good-pin)
 same => n,Hangup()
 same => n(no-operator),Noop(Tarotista no existe)
 same => n,Goto(outbound-supervisor,s,1)
exten => h,1,Noop(Goodbye)

[tarotista-logout]
; ← still uses AUDIOTEX; migrate to POST /agi/operators/by-phone/{ani}/logout
exten => s,1,Noop(Logout Tarotista)
 same => n,Agi(${AUDIOTEX},info_ejecutivo,telefono,${ani})
 same => n,Agi(${AUDIOTEX},cambia_login,${operador_numero},0,0)
 same => n,Playback(zvn/good-pin)
 same => n,Hangup()
 same => n(no-operator),Noop(Tarotista no existe)
 same => n,Goto(outbound-supervisor,s,1)
exten => h,1,Noop(Goodbye)
```

### extensions_fonotarot.conf — FonoTarot Chile + Latam call flow

```ini
[saldo-insuficiente]
exten => s,1,Noop(Saldo de ${ani} es insuficiente)
 same => n,Playback(zvn/saldo-insuficiente&zvn/espere-linea-supervisor)
 same => n,Goto(outbound-supervisor,s,1)
exten => h,1,NoOp(Goodbye)

[prepago-fonotarot-latam]
exten => s,1,NoOp(Prepago Fonotarot Latam)
 same => n,Answer()
 same => n,Set(servicio=fonotarot-latam)
 same => n,Set(clientid=0)
 same => n,Playback(zvn/intro-ftlatam)
 same => n(pide-pin),Read(pin,zvn/new-enter-pin&beep,8,s,2,10)
 same => n,GotoIf($["${pin}" = ""]?bad-pin:)
 same => n,Agi(${FIRENZE},services,${servicio},pin,${pin})     ; ← FIRENZE AGI (PIN lookup)
 same => n,GotoIf($["${clientid}" = "0"]?bad-pin:good-pin)
 same => n(good-pin),Playback(zvn/new-good-pin)
 same => n,Set(CDR(zvn_clientid)=${clientid})
 same => n,Set(CDR(userfield)=${servicio})
 same => n,Gosub(limite-saldo,s,1)                            ; ← dialplan ladder (to be replaced by CURL)
 same => n,Agi(${FIRENZE},online-calls,insert,${servicio},${ani},${did},0,${clientid})
 same => n(selecciona-ejecutivo),Gosub(selecciona-ejecutivo-prepago,s,1)
 same => n,Goto(llama-tarotista,${OPERATOR_NUM},1)
 same => n,Hangup(16)
 same => n(bad-pin),Playback(zvn/bad-pin)
 same => n,Goto(pide-pin)
exten => h,1,Agi(${FIRENZE},online-calls,delete,${servicio},${ani})
 same => n,NoOp(Goodbye)

[prepago-fonotarot-cl]
exten => s,1,NoOp(Prepago Fonotarot Chile)
 same => n,Answer()
 same => n,Set(servicio=fonotarot-cl)
 same => n,Set(clientid=0)
 same => n,Playback(zvn/intro-ftchile)
 same => n,Agi(${AUDIOTEX},obtiene_clientid,${ani:2},${servicio})  ; ← AUDIOTEX (client lookup by ANI)
 same => n,GotoIf($["${clientid}" = "0"]?outbound-supervisor,s,1:)
 same => n,Set(CDR(zvn_clientid)=${clientid})
 same => n,Set(CDR(userfield)=${servicio})
 same => n,Agi(${FIRENZE},online-calls,search,${servicio},${ani},${clientid})
 same => n,GotoIf($["${llamada_activa}" = "true"]?saldo-insuficiente,s,1:)
 same => n,Agi(${AUDIOTEX},obtiene_segundos,${clientid},${servicio})  ; ← AUDIOTEX (credit balance)
 same => n,GotoIf($["${segundos}" = "0"]?saldo-insuficiente,s,1:)
 same => n,Gosub(limite-saldo,s,1)                                    ; ← dialplan ladder
 same => n,Agi(${FIRENZE},online-calls,insert,${servicio},${ani},${did},0,${clientid})
 same => n(selecciona-ejecutivo),Gosub(selecciona-ejecutivo-prepago,s,1)
 same => n,Agi(${FIRENZE},online-calls,update,${servicio},${ani},${OPERATOR_NUM})
 same => n,Goto(llama-tarotista,${OPERATOR_NUM},1)
 same => n,Hangup(16)
exten => h,1,Agi(${AUDIOTEX},elimina_llamada_online,${ani})
 same => n,Agi(${FIRENZE},online-calls,delete,${servicio},${ani})
 same => n,NoOp(Goodbye)

[selecciona-ejecutivo-prepago]
; ← all AUDIOTEX; target: replace with CURL /agi/operators/menu + /agi/operators/select
exten => s,1,Noop(Vamos a seleccionar un ejecutivo)
 same => n(ejecutivos-disponibles),Agi(${AUDIOTEX},ejecutivos_disponibles,7)
 same => n,GotoIf($["${siguiente}" = "no-operators"]?no-operators:)
 same => n,GotoIf($["${disponibles}" = "0"]?no-operators:menu)
 same => n(menu),Read(opcion,zvn/menutarot,1)
 same => n,Goto(o${opcion})
 same => n(o1),NoOp(Lista Ejecutivos)
 same => n,Agi(${AUDIOTEX},ejecutivos_disponibles,7)
 same => n,Read(seleccion,${audio_str},2,s,2,1)
 same => n,GotoIf($["${seleccion}" = ""]?o:)
 same => n,Set(ejecutivo_seleccionado=${tar_opt_${seleccion}})
 same => n,Goto(variables)
 same => n(o2),Noop(Random Ejecutivo)
 same => n,Agi(${AUDIOTEX},ejecutivo_aleatorio,7)
 same => n,GotoIf($["${siguiente}" = "no-operators"]?no-operators:variables)
 same => n,Goto(menu)
 same => n(o),Noop(No selecciona opcion)
 same => n,Goto(ejecutivos-disponibles)
 same => n(no-operators),Playback(zvn/ocupado)
 same => n,Goto(ejecutivos-disponibles)
 same => n(variables),Noop(Seteando Variables de ${ejecutivo_seleccionado})
 same => n,Agi(${AUDIOTEX},info_ejecutivo,opcion,${ejecutivo_seleccionado})
 same => n,Set(OPERATOR_NUM=${ejecutivo_seleccionado})
 same => n,Set(OPERATOR_TEL=${operador_telefono})
 same => n,Set(OPERATOR_NAM=${operador_nombre})
 same => n,Set(OPERATOR_TRUNK=${operador_trunk})
 same => n(salida),Return()
exten => h,1,Agi(${FIRENZE},online-calls,delete,${servicio},${ani})
 same => n,NoOp(Goodbye)

[limite-saldo]
; ← 150-line ladder replaced by GET /agi/credits/limit ✅
; ... (full content in asterisk_config/current/extensions_fonotarot.conf)

[llama-tarotista]
include => outbound-ejecutivos
exten => _XXXX,1,Noop(Ultima verificacion antes de llamar)
 same => n,Agi(${AUDIOTEX},info_ejecutivo,operator,${OPERATOR_NUM})  ; ← re-check (race condition)
 same => n,GotoIf($["${siguiente}" = ""]?:${siguiente})
 same => n,Agi(${AUDIOTEX},cambia_estado,${OPERATOR_NUM},0)
 same => n,Goto(${OPERATOR_TEL},1)
 same => n(no-operator),Noop(Operador no disponible)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
 same => n(operator-busy),Noop(Operador ocupado)
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)
exten => h,1,Noop(Procesos post llamada)
 same => n,StopMixMonitor()
 same => n,Agi(${AUDIOTEX},cambia_estado,${OPERATOR_NUM},1)          ; ← release via AUDIOTEX
 same => n,Agi(${FIRENZE},online-calls,delete,${servicio},${ani})
 same => n,Agi(${FIRENZE},services,${servicio},consumo,${clientid},${CDR(billsec)})
 same => n,Agi(${AUDIOTEX},resta_saldo,${CDR(billsec)},${clientid},${servicio})  ; ← deduct via AUDIOTEX
 same => n,NoOp(Goodbye)
```

### extensions_alotarot.conf — Alotarot call flow

```ini
[prepago-alotarot]
exten => s,1,Noop(Prepago Alotarot)
 same => n,Set(servicio=alotarot)
 same => n,Set(clientid=0)
 same => n,Playback(zvn/intro-alotarot&zvn/intro-alotarot-info)
 same => n,Agi(${AUDIOTEX},obtiene_clientid,${ani:2},${servicio})   ; ← AUDIOTEX client lookup
 same => n,GotoIf($["${clientid}" = "0"]?outbound-supervisor,s,1:)
 same => n,Set(CDR(zvn_clientid)=${clientid})
 same => n,Set(CDR(userfield)=${servicio})
 same => n,Agi(${AUDIOTEX},obtiene_segundos,${clientid},${servicio})  ; ← AUDIOTEX credit balance
 same => n,GotoIf($["${segundos}" = "0"]?outbound-supervisor,s,1:)
 same => n,Gosub(limite-saldo,s,1)
 same => n,Agi(${FIRENZE},online-calls,insert,${servicio},${ani},${did},0,${clientid})
 same => n,Agi(${AUDIOTEX},inserta_llamada_online,${ani},${did})
 same => n(selecciona-ejecutivo),Gosub(selecciona-ejecutivo-prepago,s,1)
 same => n,Agi(${FIRENZE},online-calls,update,${servicio},${ani},${OPERATOR_NUM})
 same => n,Goto(llama-tarotista,${OPERATOR_NUM},1)
 same => n,Hangup(16)
exten => h,1,Agi(${AUDIOTEX},elimina_llamada_online,${ani})
 same => n,Agi(${FIRENZE},online-calls,delete,${servicio},${ani})
 same => n,NoOp(Goodbye)
```

### Migration status per context

| Context | Status | Blocking on |
|---|---|---|
| `selecciona-servicio` | AGI → CURL ready | endpoint live ✅, dialplan not yet updated |
| `limite-saldo` | replaced by `/agi/credits/limit` | endpoint live ✅, dialplan not yet updated |
| `prepago-fonotarot-latam` | partial (FIRENZE AGI for PIN, FIRENZE for online-calls) | Phase 2 (unified Client) |
| `prepago-fonotarot-cl` | partial (AUDIOTEX for client/credits, FIRENZE for online-calls) | Phase 2 |
| `prepago-alotarot` | partial (AUDIOTEX for client/credits, FIRENZE for online-calls) | Phase 2 |
| `selecciona-ejecutivo-prepago` | all AUDIOTEX | Phase 1 (operator_service) |
| `llama-tarotista` | AUDIOTEX for state change + credit deduction | Phase 1 + 2 |
| `tarotista-login` | AUDIOTEX | Phase 1 |
| `tarotista-logout` | AUDIOTEX | Phase 1 |

---

## Revised Dialplan (migration in progress)

The dialplan is migrated incrementally. `FIRENZE_API` is added alongside the existing `FIRENZE` and `AUDIOTEX` globals — all three coexist until the migration is complete.

### Global variables — transition state

```ini
[globals]
FIRENZE=/home/zvn/public_apps/firenze/.venv/bin/firenze    ; keep until fully replaced
AUDIOTEX=/home/zvn/public_apps/firenze/asterisk_agi/audiotex.py  ; keep until Phase 4
FIRENZE_API=http://127.0.0.1:3002/agi                      ; new — CURL-based
```

---

### Ready to deploy now (endpoints live ✅)

#### `[selecciona-servicio]` — DID resolution

Replaces `Agi(${FIRENZE},services,did,${did})`:

```ini
[selecciona-servicio]
exten => _X.,1,NoOp(Vamos a seleccionar el servicio)
 same => n,Set(AGIEXITONHANGUP=yes)
 same => n,Set(response=${CURL(${FIRENZE_API}/services/did/${did})})
 same => n,Set(siguiente=${JSON_DECODE(response,siguiente)})
 same => n,GotoIf($["${siguiente}" = ""]?no-service,s,1:)
 same => n,Goto(${siguiente},s,1)
exten => h,1,NoOp(Goodbye)
```

#### `[limite-saldo]` — credit limit

Drop the entire `[limite-saldo]` context and replace `Gosub(limite-saldo,s,1)` in each service context with:

```ini
same => n,Set(response=${CURL(${FIRENZE_API}/credits/limit?seconds=${segundos})})
same => n,Set(TIMEOUT(absolute)=${JSON_DECODE(response,timeout)})
same => n,Set(saldo_audio=${JSON_DECODE(response,audio)})
same => n,GotoIf($["${saldo_audio}" = ""]?:)
same => n,Playback(${saldo_audio})
```

#### DNC check — add to each service context

Add early in `[prepago-fonotarot-cl]`, `[prepago-fonotarot-latam]`, and `[prepago-alotarot]`, after `ani` is set:

```ini
same => n,Set(response=${CURL(${FIRENZE_API}/dnc/${ani})})
same => n,GotoIf($["${JSON_DECODE(response,dnc)}" = "YES"]?hangup-dnc,s,1:)
```

---

### Phase 1 — operator management (pending `services/operator_service.py`)

#### `[selecciona-ejecutivo-prepago]`

Replaces all `Agi(${AUDIOTEX},ejecutivos_disponibles,...)` / `ejecutivo_aleatorio` / `info_ejecutivo` calls:

```ini
[selecciona-ejecutivo-prepago]
exten => s,1,Noop(Seleccionar ejecutivo)
 same => n(refresh),Set(response=${CURL(${FIRENZE_API}/operators/menu)})
 same => n,Set(disponibles=${JSON_DECODE(response,disponibles)})
 same => n,Set(audio_str=${JSON_DECODE(response,audio_str)})
 same => n,GotoIf($[${disponibles} = 0]?no-operators:)
 same => n(menu),Read(opcion,zvn/menutarot,1)
 same => n,GotoIf($["${opcion}" = "1"]?lista:)
 same => n,GotoIf($["${opcion}" = "2"]?aleatorio:)
 same => n,Goto(menu)
 same => n(lista),Read(seleccion,${audio_str},2,s,2,1)
 same => n,GotoIf($["${seleccion}" = ""]?menu:)
 same => n,Set(response=${CURL(${FIRENZE_API}/operators/select?mode=option&selection=${seleccion})})
 same => n,Goto(check)
 same => n(aleatorio),Set(response=${CURL(${FIRENZE_API}/operators/select?mode=random)})
 same => n,Goto(check)
 same => n(check),Set(ok=${JSON_DECODE(response,ok)})
 same => n,GotoIf($["${ok}" = "false"]?unavailable:)
 same => n,Set(OPERATOR_NUM=${JSON_DECODE(response,operador_numero)})
 same => n,Set(OPERATOR_TEL=${JSON_DECODE(response,operador_telefono)})
 same => n,Set(OPERATOR_NAM=${JSON_DECODE(response,operador_nombre)})
 same => n,Set(OPERATOR_TRUNK=${JSON_DECODE(response,operador_trunk)})
 same => n,Return()
 same => n(unavailable),Playback(zvn/ocupado)
 same => n,Goto(refresh)
 same => n(no-operators),Playback(zvn/ocupado)
 same => n,Goto(refresh)
exten => h,1,Set(x=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani},DELETE)})
 same => n,NoOp(Goodbye)
```

#### `[llama-tarotista]` — remove re-check, use CURL for release

Replaces `Agi(${AUDIOTEX},cambia_estado,...)` on busy/fail and post-call:

```ini
[llama-tarotista]
include => outbound-ejecutivos
exten => _XXXX,1,Noop(Llamando a ${OPERATOR_NAM} (${OPERATOR_NUM}) via ${OPERATOR_TRUNK})
 same => n,Goto(${OPERATOR_TEL},1)
exten => BUSY,1,Noop(Telefono Ocupado)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Goto(prepago-${servicio},s,selecciona-ejecutivo)
exten => CONGESTION,1,Noop(Red Ocupada)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Goto(prepago-${servicio},s,selecciona-ejecutivo)
exten => CHANUNAVAIL,1,Noop(Canal no disponible)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Goto(prepago-${servicio},s,selecciona-ejecutivo)
exten => FAILED,1,Noop(Numero Malo)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Goto(prepago-${servicio},s,selecciona-ejecutivo)
exten => h,1,Noop(Post-call)
 same => n,StopMixMonitor()
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Set(x=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani},DELETE)})
 same => n,NoOp(Goodbye)
```

#### `[tarotista-login]` / `[tarotista-logout]`

Replaces `Agi(${AUDIOTEX},info_ejecutivo,...)` + `Agi(${AUDIOTEX},cambia_login,...)`:

```ini
[tarotista-login]
exten => s,1,Noop(Login Tarotista)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/by-phone/${ani}/login,POST)})
 same => n,Playback(zvn/good-pin)
 same => n,Hangup()
exten => h,1,Noop(Goodbye)

[tarotista-logout]
exten => s,1,Noop(Logout Tarotista)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/by-phone/${ani}/logout,POST)})
 same => n,Playback(zvn/good-pin)
 same => n,Hangup()
exten => h,1,Noop(Goodbye)
```

---

### Phase 2 — client/credit unification (pending unified Client model)

#### `[prepago-fonotarot-cl]`

Replaces `Agi(${AUDIOTEX},obtiene_clientid,...)` and `Agi(${AUDIOTEX},obtiene_segundos,...)`. Credit deduction (`resta_saldo`) also moves here from `[llama-tarotista]`:

```ini
[prepago-fonotarot-cl]
exten => s,1,NoOp(Prepago Fonotarot Chile)
 same => n,Answer()
 same => n,Set(servicio=fonotarot-cl)
 same => n,Set(clientid=0)
 same => n,Playback(zvn/intro-ftchile)
 same => n,Set(response=${CURL(${FIRENZE_API}/dnc/${ani})})
 same => n,GotoIf($["${JSON_DECODE(response,dnc)}" = "YES"]?hangup-dnc,s,1:)
 same => n,Set(response=${CURL(${FIRENZE_API}/clients/lookup?service=${servicio}&identifier=${ani})})
 same => n,Set(clientid=${JSON_DECODE(response,clientid)})
 same => n,Set(segundos=${JSON_DECODE(response,segundos)})
 same => n,GotoIf($["${clientid}" = "0"]?outbound-supervisor,s,1:)
 same => n,Set(response=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani})})
 same => n,GotoIf($["${JSON_DECODE(response,llamada_activa)}" = "true"]?saldo-insuficiente,s,1:)
 same => n,GotoIf($["${segundos}" = "0"]?saldo-insuficiente,s,1:)
 same => n,Set(CDR(zvn_clientid)=${clientid})
 same => n,Set(CDR(userfield)=${servicio})
 same => n,Set(response=${CURL(${FIRENZE_API}/credits/limit?seconds=${segundos})})
 same => n,Set(TIMEOUT(absolute)=${JSON_DECODE(response,timeout)})
 same => n,Set(saldo_audio=${JSON_DECODE(response,audio)})
 same => n,GotoIf($["${saldo_audio}" = ""]?:)
 same => n,Playback(${saldo_audio})
 same => n,Set(x=${CURL(${FIRENZE_API}/calls/online,service=${servicio}&ani=${ani}&did=${did}&operator=0&client_id=${clientid})})
 same => n(selecciona-ejecutivo),Gosub(selecciona-ejecutivo-prepago,s,1)
 same => n,Set(x=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani}?operator=${OPERATOR_NUM},PATCH)})
 same => n,Goto(llama-tarotista,${OPERATOR_NUM},1)
 same => n,Hangup(16)
exten => h,1,Set(x=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani},DELETE)})
 same => n,NoOp(Goodbye)
```

Credit deduction moves into `[llama-tarotista]` hangup handler (replacing `Agi(${AUDIOTEX},resta_saldo,...)`):

```ini
; add to exten => h in [llama-tarotista]:
same => n,Set(x=${CURL(${FIRENZE_API}/clients/${clientid}/deduct?seconds=${CDR(billsec)}&service=${servicio})})
```

#### `[prepago-fonotarot-latam]`

Replaces `Agi(${FIRENZE},services,${servicio},pin,${pin})` with the unified client lookup:

```ini
same => n,Set(response=${CURL(${FIRENZE_API}/clients/lookup?service=${servicio}&identifier=${pin})})
same => n,Set(clientid=${JSON_DECODE(response,clientid)})
same => n,Set(segundos=${JSON_DECODE(response,segundos)})
```

---

## Legacy Migration Path

### Phase 1: Operator management ← next
- Build `services/operator_service.py` backed by Operator model + Redis (direct redis-py)
- Build `/agi/operators/*` endpoints in `api/agi.py`
- Replace `${AUDIOTEX}` operator calls in dialplan with CURL calls
- Removes: redis-om (`kvstore.py`), pystrix dependency for operator commands

### Phase 2: Client/credit unification
- Build unified Client model (Alembic migration)
- Migrate FonoTarot Chile clients + Alotarot clients into Client
- Build `services/did_service.py` and `/agi/clients/*` endpoints
- Replace `${AUDIOTEX}` client/credit calls with CURL
- Removes: `FonoTarotLatamClient`, fastapi-crudrouter (`tarot.py`)

### Phase 3: Online call tracking
- Build `services/call_service.py`
- Build remaining `/agi/calls/*` endpoints
- Replace remaining `${AUDIOTEX}` call tracking with CURL
- Removes: legacy `clientespv`/`clientesonline` tables

### Phase 4: Drop AUDIOTEX
- Remove `audiotex/` directory
- Remove Peewee from dependencies
- Remove `AUDIOTEX_DSN` config
- Remove `${AUDIOTEX}` global from dialplan

### Phase 5: Dialplan cleanup
- Remove `limite-saldo` hardcoded ladder — already replaced by `/agi/credits/limit` ✅
- Consolidate per-service contexts where possible (ANI-based services share most logic)
- Split `models.py` → `models/` and `schemas.py` → `schemas/`
- Remove `core.py` (unused legacy router)

---

## Summary of Changes vs Current Architecture

| Aspect | Current | Target |
|---|---|---|
| Asterisk → Firenze | AGI subprocess spawn (~1s each) | CURL to localhost API (~5-10ms each) |
| DNC check | AGI CLI subprocess | `GET /agi/dnc/{ani}` ✅ |
| Credit limit | `[limite-saldo]` 47-line dialplan ladder | `GET /agi/credits/limit` ✅ |
| DID resolution | AGI CLI subprocess | `GET /agi/services/did/{did}` ✅ |
| Operator selection | 5-6 AGI calls, race condition | 2 CURL calls, atomic select+lock |
| `tar_opt_XX` variables | Set in Asterisk, mapped in dialplan | Gone — mapping lives server-side |
| `llama-tarotista` re-check | AGI call to verify availability | Gone — `/select` already verified |
| ORM | SQLAlchemy + Peewee (dual) | SQLAlchemy only |
| Redis client | redis-om (kvstore.py) | direct redis-py |
| Business logic location | Scattered in routes, CLI, AGI scripts | Centralized in `services/` layer |
| `get_db()` | Defined 4 times | Defined once in `dependencies.py` ✅ |
| Client models | 5 separate tables across 2 databases | 1 unified Client table |
| Service types | Hardcoded per-service logic | Pluggable via `service.auth_method` |
| CLI role | Hot path (called by Asterisk) | Admin/debug tool only |
| Operator state reads | MySQL on every AGI call | Redis (sub-ms), MySQL fallback |
