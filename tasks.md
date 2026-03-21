# Firenze — Migration Tasks

> Full architecture details: [new-architecture.md](new-architecture.md)

---

## Phase 1: Operator management

- [x] `services/operator_service.py` — `login`, `logout`, `set_availability` (MySQL + Redis)
- [x] `redis/operator_state.py` — direct redis-py with graceful degradation
- [x] `POST /agi/operators/by-phone/{ani}/login`
- [x] `POST /agi/operators/by-phone/{ani}/logout`
- [ ] `GET /agi/operators/menu` — available count + audio string
- [ ] `POST /agi/operators/select` — atomic verify + mark busy (option or random mode)
- [ ] `POST /agi/operators/{number}/release` — mark operator available again
- [ ] Replace `${AUDIOTEX}` operator calls in dialplan with CURL
- [ ] Remove `pystrix` from dependencies

---

## Phase 2: Client/credit unification

- [x] Unified `Client` model (Alembic migration `f479283e23a2`)
- [x] `services/client_service.py` — `lookup`, `deduct_credits`
- [x] `GET /agi/clients/lookup?service=&identifier=` — by ANI or PIN
- [x] `POST /agi/clients/{service}/{client_id}/deduct?seconds=N` — credit deduction
- [ ] Populate `client` table with FonoTarot Latam data (from `fonotarot_latam` table)
- [ ] Migrate FonoTarot Chile + Alotarot clients into `Client`
- [ ] Replace `${AUDIOTEX}` client/credit calls in dialplan with CURL
- [ ] Remove `FonoTarotLatamClient` model (after data migrated)
- [ ] Remove `fastapi-crudrouter` (`tarot.py`)

---

## Phase 3: Online call tracking

- [ ] `services/call_service.py` — insert, delete, lookup active calls
- [ ] `POST /agi/calls/online/{service}/{ani}`
- [ ] `DELETE /agi/calls/online/{service}/{ani}`
- [ ] `GET /agi/calls/online/{service}/{ani}`
- [ ] `PATCH /agi/calls/online/{service}/{ani}?operator={num}`
- [ ] Replace `${AUDIOTEX}` call tracking in dialplan with CURL
- [ ] Remove legacy `clientespv` / `clientesonline` tables

---

## Phase 4: Drop AUDIOTEX

- [ ] Remove `audiotex/` directory
- [ ] Remove Peewee from dependencies
- [ ] Remove `AUDIOTEX_DSN` from config
- [ ] Remove `${AUDIOTEX}` global from dialplan

---

## Phase 5: Dialplan cleanup

- [x] `limite-saldo` ladder replaced by `GET /agi/credits/limit`
- [ ] Consolidate ANI-based service contexts
- [x] `models/` package split by domain
- [x] `schemas/` package split by domain
- [ ] Remove `core.py` (unused legacy router)

---

## Credit push API (nuevo-fonotarot integration)

- [ ] `POST /api/clients/{identifier}/credit` — called by nuevo-fonotarot after purchase
