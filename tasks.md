# Firenze - Estado de Migración

> Diseño general: [new-architecture.md](new-architecture.md)
> Formas de endpoints, configuraciones, referencia dialplan: [tech.md](tech.md)

## Dónde estamos ahora

**Dos tiempos de ejecución de Firenze se están ejecutando lado a lado en producción** mientras
el dialplan se migra pieza por pieza:

- Heredado: Subprocesos CLI AGI (`${FIRENZE}` y `${AUDIOTEX}` globales en
  el dialplan). Genera un proceso Python por paso de llamada.
- Nuevo: Servicio FastAPI en `localhost:9002` (este repositorio). Asterisk lo golpea
  a través de `${FIRENZE_API}` usando `CURL()` + `JSON_DECODE()`.

**Niveles de dialplan:**

| Ruta | Rol |
|---|---|
| `asterisk_config/current/*.conf` (nivel superior) | Snapshot más antiguo, puro AGI. No cargado. |
| `asterisk_config/current/new_config/*.conf` | Actualmente cargado en Asterisk. Híbrido: llamadas CURL se ejecutan junto a las llamadas AGI antiguas para que ambos tiempos de ejecución vean los mismos eventos. Nos permite validar el nuevo servicio contra el antiguo. |
| `asterisk_config/new/*.conf` | Dialplan objetivo. Solo CURL limpio, contexto `[prepago-service]` unificado reemplazando los duplicados por servicio. No aún desplegado. |

## Hecho

### Infraestructura central

- Factory de aplicación FastAPI, gunicorn + uvicorn worker, unidad systemd
- Pydantic v2, pydantic-settings, `get_db()` único en `dependencies.py`
- `database.py` limpiado (sin `sqlalchemy.ext.declarative`)
- `passlib` eliminado, `bcrypt` directo en todas partes
- Alembic configurado a través de `pyproject.toml`, head actual `a8c5e1f2b9d3`

### Dominio y esquemas

- `models/` dividido por dominio (`user`, `service`, `operator`, `call`,
  `client`, `dnc`, `event`), estilo SQLAlchemy 2.0 `Mapped`
- `schemas/` dividido por dominio, Pydantic v2
- Modelo `Client` unificado con `(service_id, client_id)` por servicio
- Tabla secundaria `ClientAni` para mapeo multi-ANI -> un cliente
- `Service.auth_method`, `Service.intro_audio`, `Operator.audio_file` -
  suficientes metadatos en la BD para impulsar un contexto dialplan compartido único

### Capa de servicios

- `services/dnc_service.py` - `check_dnc`
- `services/credit_service.py` - `compute_call_limit`
- `services/did_service.py` - `resolve_did`
- `services/operator_service.py` - `login`, `logout`, `login_by_phone`,
  `logout_by_phone`, `set_availability`, `get_menu`, `select_operator`
  (atómico `SELECT FOR UPDATE`), `release_operator`, `info_operator`
- `services/client_service.py` - `lookup` (PIN luego ClientAni),
  `deduct_credits`
- `services/call_service.py` - `insert_call`, `delete_call`,
  `update_call_operator`, `get_active_call`

### Endpoints AGI (todos viven en :9002)

- `GET  /agi/dnc/{ani}`
- `GET  /agi/services/did/{did}` (acepta `uniqueid` y `channel` opcionales para telemetría GA4 `service_lookup`)
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
- `GET  /agi/operators/by-ani/{ani}` (info, lookup por número de teléfono)
- `GET  /agi/operators/by-option/{option}` (info, lookup por dígito de menú IVR)

### Capa Redis

- `redis/operator_state.py` - `redis-py` directo, degradación elegante
- `redis/call_state.py` - mismo patrón para llamadas activas. Consumido por los
  lectores PHP heredados en `asterisk_config/legacy-php/`.
- `kvstore.py` y `redis-om` eliminados.

### CLI (Typer)

- `firenze users` - buscar, crear, actualizar, eliminar usuarios API
- `firenze operator` - login, logout, change-status, listar, info
- `firenze dnc` - verificar, agregar, eliminar, listar
- `firenze did` - resolver
- `firenze calls` - listar, limpiar
- `firenze migration` - importación masiva de clientes desde la API Firenze heredada
  (incluye auditoría `check-anis` / reparación)
- `firenze fastapi` - herramientas FastAPI diversas

### Pruebas

- `tests/test_dnc_service.py`, `test_credit_service.py`,
  `test_did_service.py`, `test_client_service.py`,
  `test_operator_service.py`, `test_operator_state.py`,
  `test_call_state.py`, `test_incoming_call_flow.py`,
  `test_incoming_call_http.py`

### Dialplan objetivo escrito (no aún desplegado)

- `asterisk_config/new/extensions.conf` - globales incl. `FIRENZE_API` y
  tabla strip `TRUNK_STRIP_*`
- `asterisk_config/new/extensions_zvn.conf` - troncales, supervisor,
  login/logout de operadores a través de CURL
- `asterisk_config/new/extensions_services.conf` - `[prepago-service]`
  unificado con `[auth-ani]` / `[auth-pin]` / `[sub-post-auth]`
  / `[selecciona-operador]` / `[llama-operador]`

## En vuelo

- **Migración de datos de cliente.** FonoTarot Latam está parcialmente importado. Chile
  y Alotarot aún leen/escriben a través de la ruta AGI AUDIOTEX en el dialplan
  `new_config/` en vivo. Usa `firenze migration` para terminar.
- **Hibridación de dialplan.** `new_config/` ya hace CURL al nuevo servicio
  para DNC, resolución DID, límite de crédito e inserción/cierre de llamada en línea,
  en paralelo con las llamadas AGI antiguas. Aún no hemos eliminado las llamadas AGI.
- **`ServiceNumber.asterisk_context`.** Aún apunta a contextos por servicio
  (`prepago-fonotarot-cl`, `prepago-alotarot`,
  `prepago-fonotarot-latam`). El objetivo es `prepago-service` para cada DID,
  que es lo que `asterisk_config/new/` asume.

## Siguiente (ordenado por lo que desbloquea el despliegue)

1. **Terminar migración de datos de cliente.** Filas de Chile + Alotarot en `Client` +
   `ClientAni`. Verifica que los saldos de crédito coincidan con la BD heredada.
2. **Elimina las escrituras de crédito del lado AGI del dialplan en vivo.** Después de la
   migración de datos, deja de escribir a AUDIOTEX para que los dos sistemas no
   diverjan. Equivalente para inserción/eliminación de llamadas en línea.
3. **Cambia `ServiceNumber.asterisk_context` a `prepago-service`.** Haz
   un DID a la vez para que la reversión sea económica.
4. **Despliega `asterisk_config/new/` como el dialplan en vivo.** Contextos por servicio
   (`extensions_alotarot.conf`, `extensions_fonotarot.conf`) desaparecen.
5. **Selección de operador a través de CURL.** El `new_config/` híbrido aún llama
   a `${AUDIOTEX}` para `ejecutivos_disponibles`, `ejecutivo_aleatorio`, e
   `info_ejecutivo`. Los endpoints existen; cambia el dialplan.
6. **API de empuje de crédito para nuevo-fonotarot.**
   `POST /api/clients/{identifier}/credit`, scope de encabezado API. Necesario antes
   de que nuevo-fonotarot pueda completar una compra de principio a fin.

## Deuda de limpieza (seguro de eliminar una vez que 1-5 lleguen)

| Elemento | Por qué aún está alrededor |
|---|---|
| `firenze/audiotex/` (modelos Peewee) | Leído por ruta AGI antigua solo |
| `asterisk_agi/` (scripts AGI CLI) | Invocado por globales `${FIRENZE}` / `${AUDIOTEX}` en vivo |
| `firenze/tarot.py` | fastapi-crudrouter para `FonoTarotLatamClient` - supersedido por `Client` unificado. No en el árbol de router. |
| `firenze/core.py` | Router heredado no utilizado |
| `firenze/asterisk/` (paquete vacío) | Resto |
| `peewee` en `pyproject.toml` | Desaparece con `audiotex/` |
| `pystrix` en `pyproject.toml` | Ya no importado en ninguna parte; mantenido solo porque aún está en el lock |
| `AUDIOTEX_DSN` en config | Desaparece con `audiotex/` |
| `${FIRENZE}` y `${AUDIOTEX}` globales dialplan | Desaparece en paso 4 arriba |
| `asterisk_config/current/` top-level `.conf` (snapshot más antiguo) | No cargado - mantener mientras lanzamos, eliminar después |
| `asterisk_config/legacy-php/` lectores Redis | Los consumidores necesitan cambiar a las nuevas claves o ser retirados |
