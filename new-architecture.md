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
| ORM | SQLAlchemy 2.0 (single ORM, no Peewee) |
| Migrations | Alembic |
| Validation | Pydantic v2 + pydantic-settings |
| DB | MySQL (PyMySQL) |
| Cache/State | Redis/Valkey |
| Admin | sqladmin |
| CLI | Typer (admin/debug tool, no longer in the call hot path) |
| Auth | JWT (python-jose) + bcrypt/passlib |
| Monitoring | Sentry (optional) |

### Removed from current stack

- **Peewee** — legacy audiotex DB access, replaced by SQLAlchemy as migration completes
- **pystrix** — only needed for AGI protocol; CURL approach doesn't need it
- **fastapi-crudrouter** — dropped experiment
- **redis-om** — replaced by direct redis-py for operator state (simpler, no magic)

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

## Module Structure

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
│   ├── call.py              # OnlineCall, CallRecord
│   ├── client.py            # Client (unified, replaces legacy tables)
│   ├── dnc.py               # DoNotCall
│   └── event.py             # Event, PostCallProcess
│
├── schemas/                 # Pydantic v2 schemas
│   ├── __init__.py
│   ├── client.py
│   ├── operator.py
│   └── ...
│
├── services/                # Business logic layer
│   ├── credit_service.py    # Balance check, add credits, deduct
│   ├── operator_service.py  # Login/logout, availability, select, release
│   ├── call_service.py      # Online call tracking, post-call processes
│   └── did_service.py       # DID resolution → asterisk context
│
├── api/                     # FastAPI routers
│   ├── __init__.py
│   ├── auth.py              # POST /token — JWT
│   ├── core.py              # GET /thanks, /events — health + event log
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
└── redis/                   # Redis/Valkey layer
    ├── __init__.py           # Connection setup
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

Adding a new service = insert a row in `service` + map DIDs to it + create the dialplan context.

### Client (unified)

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

The CLI command becomes: `firenze client lookup <service> <identifier>` — works for both ANI and PIN.

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
  trunk: str                 # preferred outbound trunk (e.g. "claro1", "didww-mia-out")
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

### Why Redis

- Operator state changes multiple times per call (available → busy → available)
- The `disponibles` query runs at least once per call during the IVR
- Redis reads are sub-millisecond
- TTL (24h) naturally handles "operator forgot to logout"

---

## AGI Endpoints (`/agi/`)

Flat JSON responses designed for `JSON_DECODE()` in the dialplan. Every response includes all variables the dialplan needs — no multi-step lookups.

### Service/DID resolution

```
GET /agi/services/did/{did}

Response:
  {"siguiente": "prepago-fonotarot-cl"}    # context to goto
  {"siguiente": ""}                         # DID not found
```

### DNC check

```
GET /agi/dnc/{ani}

Response:
  {"dnc": "YES"}
  {"dnc": "NO"}
```

### Client lookup (PIN and ANI)

```
GET /agi/clients/lookup?service={slug}&identifier={ani_or_pin}

Response (found):
  {"clientid": 42, "segundos": 1800}

Response (not found):
  {"clientid": 0, "segundos": 0}
```

### Credit deduction

```
POST /agi/clients/{client_id}/deduct?seconds={n}&service={slug}

Response:
  {"ok": true, "credits": 1200}
```

### Online calls

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

### Operator menu

```
GET /agi/operators/menu

Response:
  {
    "disponibles": 3,
    "audio_str": "zvn/tarotistas/maria&zvn/tarotistas/jose&zvn/tarotistas/ana"
  }
```

Returns available operators and pre-built audio string for IVR playback. No `tar_opt_XX` variables — the option-to-operator mapping stays server-side.

### Operator select (atomic: verify + mark busy)

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
  {
    "ok": false,
    "reason": "operator-busy"
  }
```

Selection and marking busy is one atomic operation. No race condition between "check availability" and "mark busy". Eliminates the re-check in `llama-tarotista`.

### Operator release

```
POST /agi/operators/{number}/release

Response: {"ok": true}
```

Called on hangup to mark operator available again.

### Operator login/logout (from dialplan, for tarotista-login/logout contexts)

```
POST /agi/operators/{number}/login
POST /agi/operators/{number}/logout

Response: {"ok": true}
```

---

## Credit API (`/api/clients/`)

Authenticated endpoints for nuevo-fonotarot integration.

```
POST /api/clients/{identifier}/credit
  Headers: Authorization: Bearer <jwt>  (scope: "credits")
  Body: {"amount": 1800, "service": "fonotarot-latam", "reference": "order-123"}

Response: {"credits": 3600, "client_id": 42}
```

```
GET /api/clients/{identifier}/credit?service={slug}
  Headers: Authorization: Bearer <jwt>

Response: {"credits": 3600, "client_id": 42}
```

Firenze receives "add X seconds to client Y" and trusts the caller. It doesn't know about payments, orders, or providers.

---

## Revised Dialplan

### Global variables

```ini
[globals]
FIRENZE_API=http://127.0.0.1:3002/agi
```

### Service selection

```ini
[selecciona-servicio]
exten => _X.,1,NoOp(Seleccionar servicio para ${did})
 same => n,Set(AGIEXITONHANGUP=yes)
 same => n,Set(response=${CURL(${FIRENZE_API}/services/did/${did})})
 same => n,Set(siguiente=${JSON_DECODE(response,siguiente)})
 same => n,GotoIf($["${siguiente}" = ""]?no-service,s,1:)
 same => n,Goto(${siguiente},s,1)

exten => h,1,NoOp(Goodbye)
```

### Operator selection (replaces selecciona-ejecutivo-prepago)

```ini
[selecciona-ejecutivo-prepago]
exten => s,1,Noop(Seleccionar ejecutivo)
 ; Get available operators in one call
 same => n(refresh),Set(response=${CURL(${FIRENZE_API}/operators/menu)})
 same => n,Set(disponibles=${JSON_DECODE(response,disponibles)})
 same => n,Set(audio_str=${JSON_DECODE(response,audio_str)})
 same => n,GotoIf($[${disponibles} = 0]?no-operators:)
 ; Menu
 same => n(menu),Read(opcion,zvn/menutarot,1)
 same => n,GotoIf($["${opcion}" = "1"]?lista:)
 same => n,GotoIf($["${opcion}" = "2"]?aleatorio:)
 same => n,Goto(menu)
 ; Option 1: hear names, pick by option code
 same => n(lista),Read(seleccion,${audio_str},2,s,2,1)
 same => n,GotoIf($["${seleccion}" = ""]?menu:)
 same => n,Set(response=${CURL(${FIRENZE_API}/operators/select?mode=option&selection=${seleccion})})
 same => n,Goto(check)
 ; Option 2: random
 same => n(aleatorio),Set(response=${CURL(${FIRENZE_API}/operators/select?mode=random)})
 same => n,Goto(check)
 ; Validate and set variables
 same => n(check),Set(ok=${JSON_DECODE(response,ok)})
 same => n,GotoIf($["${ok}" = "false"]?unavailable:)
 same => n,Set(OPERATOR_NUM=${JSON_DECODE(response,operador_numero)})
 same => n,Set(OPERATOR_TEL=${JSON_DECODE(response,operador_telefono)})
 same => n,Set(OPERATOR_NAM=${JSON_DECODE(response,operador_nombre)})
 same => n,Set(OPERATOR_TRUNK=${JSON_DECODE(response,operador_trunk)})
 same => n,Return()
 ; Errors
 same => n(unavailable),Playback(zvn/ocupado)
 same => n,Goto(refresh)
 same => n(no-operators),Playback(zvn/ocupado)
 same => n,Goto(refresh)

exten => h,1,Set(x=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani},DELETE)})
 same => n,NoOp(Goodbye)
```

### Call the operator (simplified, no re-check needed)

```ini
[llama-tarotista]
include => outbound-ejecutivos
exten => _XXXX,1,Noop(Llamando a ${OPERATOR_NAM} (${OPERATOR_NUM}) via ${OPERATOR_TRUNK})
 same => n,Goto(${OPERATOR_TEL},1)

exten => BUSY,1,Noop(Telefono Ocupado)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)

exten => CONGESTION,1,Noop(Red Ocupada)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)

exten => CHANUNAVAIL,1,Noop(Canal no disponible)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)

exten => FAILED,1,Noop(Numero Malo)
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Set(salida=prepago-${servicio})
 same => n,Goto(${salida},s,selecciona-ejecutivo)

exten => h,1,Noop(Post-call)
 same => n,StopMixMonitor()
 same => n,Set(x=${CURL(${FIRENZE_API}/operators/${OPERATOR_NUM}/release)})
 same => n,Set(x=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani},DELETE)})
 same => n,Set(x=${CURL(${FIRENZE_API}/clients/${clientid}/deduct?seconds=${CDR(billsec)}&service=${servicio})})
 same => n,NoOp(Goodbye)
```

### Fonotarot Latam (PIN-based)

```ini
[prepago-fonotarot-latam]
exten => s,1,NoOp(Prepago Fonotarot Latam)
 same => n,Answer()
 same => n,Set(servicio=fonotarot-latam)
 same => n,Set(clientid=0)
 same => n,Playback(zvn/intro-ftlatam)
 same => n(pide-pin),Read(pin,zvn/new-enter-pin&beep,8,s,2,10)
 same => n,GotoIf($["${pin}" = ""]?bad-pin:)
 same => n,Set(response=${CURL(${FIRENZE_API}/clients/lookup?service=${servicio}&identifier=${pin})})
 same => n,Set(clientid=${JSON_DECODE(response,clientid)})
 same => n,Set(segundos=${JSON_DECODE(response,segundos)})
 same => n,GotoIf($["${clientid}" = "0"]?bad-pin:good-pin)
 same => n(good-pin),Playback(zvn/new-good-pin)
 same => n,Set(CDR(zvn_clientid)=${clientid})
 same => n,Set(CDR(userfield)=${servicio})
 same => n,Gosub(limite-saldo,s,1)
 same => n,Set(x=${CURL(${FIRENZE_API}/calls/online,service=${servicio}&ani=${ani}&did=${did}&operator=0&client_id=${clientid})})
 same => n(selecciona-ejecutivo),Gosub(selecciona-ejecutivo-prepago,s,1)
 same => n,Goto(llama-tarotista,${OPERATOR_NUM},1)
 same => n,Hangup(16)
 same => n(bad-pin),Playback(zvn/bad-pin)
 same => n,Goto(pide-pin)

exten => h,1,Set(x=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani},DELETE)})
 same => n,NoOp(Goodbye)
```

### Fonotarot Chile (ANI-based)

```ini
[prepago-fonotarot-cl]
exten => s,1,NoOp(Prepago Fonotarot Chile)
 same => n,Answer()
 same => n,Set(servicio=fonotarot-cl)
 same => n,Set(clientid=0)
 same => n,Playback(zvn/intro-ftchile)
 same => n,Set(response=${CURL(${FIRENZE_API}/clients/lookup?service=${servicio}&identifier=${ani})})
 same => n,Set(clientid=${JSON_DECODE(response,clientid)})
 same => n,Set(segundos=${JSON_DECODE(response,segundos)})
 same => n,GotoIf($["${clientid}" = "0"]?outbound-supervisor,s,1:)
 ; Check for active call (prevent double-call)
 same => n,Set(response=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani})})
 same => n,Set(llamada_activa=${JSON_DECODE(response,llamada_activa)})
 same => n,GotoIf($["${llamada_activa}" = "true"]?saldo-insuficiente,s,1:)
 same => n,GotoIf($["${segundos}" = "0"]?saldo-insuficiente,s,1:)
 same => n,Set(CDR(zvn_clientid)=${clientid})
 same => n,Set(CDR(userfield)=${servicio})
 same => n,Gosub(limite-saldo,s,1)
 same => n,Set(x=${CURL(${FIRENZE_API}/calls/online,service=${servicio}&ani=${ani}&did=${did}&operator=0&client_id=${clientid})})
 same => n(selecciona-ejecutivo),Gosub(selecciona-ejecutivo-prepago,s,1)
 same => n,Set(x=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani}?operator=${OPERATOR_NUM},PATCH)})
 same => n,Goto(llama-tarotista,${OPERATOR_NUM},1)
 same => n,Hangup(16)

exten => h,1,Set(x=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani},DELETE)})
 same => n,NoOp(Goodbye)
```

### Operator login/logout

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

## Legacy Migration Path

### Phase 1: Operator management
- Build `/agi/operators/*` endpoints backed by Firenze's Operator model + Redis
- Replace all `${AUDIOTEX}` operator calls in the dialplan with `${FIRENZE_API}` CURL calls
- Migrate operator data from legacy `operators` table to Firenze's DB
- Removes: dependency on legacy DB for operator state

### Phase 2: Client/credit unification
- Build unified Client model in Firenze's DB
- Migrate FonoTarot Chile clients (`clientid` + `creditos` tables) into Client
- Migrate Alotarot clients (`clientidalo` + `creditosalo` tables) into Client
- Build `/agi/clients/*` endpoints
- Replace `${AUDIOTEX}` client/credit calls with CURL calls
- Removes: `obtiene_clientid`, `obtiene_segundos`, `resta_saldo` from AUDIOTEX

### Phase 3: Online call tracking
- Already mostly migrated to Firenze
- Replace remaining `${AUDIOTEX}` `inserta_llamada_online`/`elimina_llamada_online` with CURL
- Removes: legacy `clientespv`/`clientesonline` tables

### Phase 4: Drop AUDIOTEX
- Remove `asterisk_agi/` directory
- Remove Peewee from dependencies
- Remove `AUDIOTEX_DSN` config
- Remove `${AUDIOTEX}` global from dialplan
- Drop legacy audiotex database connection

### Phase 5: Dialplan cleanup
- Remove `limite-saldo` hardcoded ladder — replace with a dynamic approach
  (Firenze returns the appropriate audio file and timeout based on credit balance)
- Consolidate per-service contexts where possible (ANI-based services share most logic)

---

## Summary of Changes vs Current Architecture

| Aspect | Current | New |
|---|---|---|
| Asterisk → Firenze | AGI subprocess spawn (~1s each) | CURL to localhost API (~5-10ms each) |
| Operator selection | 5-6 AGI calls, race condition | 2 CURL calls, atomic select+lock |
| `tar_opt_XX` variables | Set in Asterisk, mapped in dialplan | Gone — mapping lives server-side |
| `llama-tarotista` re-check | AGI call to verify availability | Gone — `/select` already verified |
| ORM | SQLAlchemy + Peewee (dual) | SQLAlchemy only |
| Pydantic | v1 | v2 |
| Business logic location | Scattered in routes, CLI, AGI scripts | Centralized in `services/` layer |
| `get_db()` | Defined 4 times | Defined once in `dependencies.py` |
| Client models | 5 separate tables across 2 databases | 1 unified Client table |
| Service types | Hardcoded per-service logic | Pluggable via `service.auth_method` |
| CLI role | Hot path (called by Asterisk) | Admin/debug tool only |
| Operator state reads | MySQL on every AGI call | Redis (sub-ms), MySQL fallback |
