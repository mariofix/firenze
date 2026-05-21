# Firenze - Referencia Técnica

> Descripción general de arquitectura: [new-architecture.md](new-architecture.md)
> Estado actual de migración: [tasks.md](tasks.md)

Este archivo documenta lo que realmente está en el repositorio y cómo está conectado. Si
algo aquí está en desacuerdo con el código, el código gana - actualiza este archivo.

## Tiempo de ejecución

- Python >= 3.14
- Punto de entrada: `run.py` -> `firenze.create_app()`
- Servicio: `gunicorn run:app -k uvicorn.workers.UvicornWorker --workers 1`
- Vinculado a `10.0.0.3:9002`
- Unidad systemd: `system_files/new-firenze.service`
- Registros: `/home/zvn/public_apps/new-firenze/logs/gunicorn-{access,error}.log`
- Punto de entrada CLI: `firenze` (instalado a través de scripts `pyproject.toml`)

El `asterisk_config/firenze.service` más antiguo fija el puerto 3002; es la
unidad heredada para el servicio CLI Firenze antiguo y está siendo reemplazado por
`system_files/new-firenze.service` en el puerto 9002.

## Distribución de módulos (actual)

```
firenze/
  __init__.py              - create_app()
  config.py                - Settings (pydantic-settings v2)
  database.py              - engine, SessionLocal, Base
  dependencies.py          - get_db(), get_redis()
  auth.py                  - Autenticación de encabezado API + AdminAuth para sqladmin
  crud.py                  - CRUD de usuario + evento
  admin.py                 - vistas sqladmin
  exceptions.py            - GenericError, ProcessError, ConfigException
  core.py                  - router heredado no utilizado (limpieza)
  tarot.py                 - fastapi-crudrouter para cliente heredado (limpieza)

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

  services/                - lógica de negocios
    dnc_service.py, credit_service.py, did_service.py,
    operator_service.py, client_service.py, call_service.py

  api/
    agi.py                 - endpoints /agi/* (orientados al dialplan)

  redis/
    __init__.py            - factory get_redis()
    operator_state.py      - firenze:operator:{number}
    call_state.py          - firenze:call:{service}:{ani}

  cli/                     - CLI Typer
    users.py, operators.py, dnc.py, did.py, calls.py,
    migration.py, fastapi.py, services.py, user_management.py,
    fonotarot_latam.py, post_call.py, utils.py

  audiotex/                - puente Peewee heredado (limpieza)
    database.py, models.py, schemas.py

  asterisk/                - paquete vacío (limpieza)
```

## Configuración

`.env` contiene secretos + URLs de BD. Los globales relevantes del lado del dialplan
viven en `asterisk_config/current/new_config/extensions.conf`:

```ini
[globals]
FIRENZE=/home/zvn/public_apps/firenze/.venv/bin/firenze
AUDIOTEX=/home/zvn/public_apps/firenze/asterisk_agi/audiotex.py
FIRENZE_API=http://localhost:9002/agi

; Caracteres iniciales a eliminar del número de operador E.164, por troncal.
; Números almacenados como 56XXXXXXXXX. Troncal indefinida -> strip=0.
TRUNK_STRIP_didww-mia-out=0
TRUNK_STRIP_tecno=2
```

`asterisk_config/new/extensions.conf` agrega `TRUNK_STRIP_tecnoera=2` y
`TRUNK_STRIP_claro1=2` y elimina completamente `FIRENZE` / `AUDIOTEX`.

## Alembic

Configuración en `pyproject.toml` bajo `[tool.alembic]`. URL de BD leída desde
`Settings`. Migraciones en `alembic/versions/`:

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

## Endpoints AGI

Todos montados bajo `/agi` por `firenze.api.agi.agiRouter`. Las respuestas son
JSON plano diseñado para `JSON_DECODE()`. Sin JWT.

### DNC

```
GET /agi/dnc/{ani}
-> {"dnc": "YES"}  o  {"dnc": "NO"}
```

### Resolución de servicio / DID

```
GET /agi/services/did/{did}
-> {"siguiente": "prepago-service",
    "servicio":  "alotarot",
    "auth_method": "ani",
    "intro_audio": "zvn/intro-alotarot"}

no encontrado:
-> {"siguiente": "", "servicio": "", "auth_method": "", "intro_audio": ""}
```

### Límite de crédito

Reemplaza la escalera dialplan `[limite-saldo]` antigua.

```
GET /agi/credits/limit?seconds=N
-> {"timeout": 900, "audio": "zvn/saldo/15", "minutes": 15}
saldo cero / negativo:
-> {"timeout": 1, "audio": "", "minutes": 0}
```

### Búsqueda de cliente

```
GET /agi/clients/lookup?service={slug}&identifier={ani_or_pin}
encontrado:
-> {"clientid": 42, "segundos": 1800}
no encontrado:
-> {"clientid": 0, "segundos": 0}
```

Orden de búsqueda dentro de `client_service.lookup`:
1. `Client` donde `(service_id, pin=identifier)` - servicios con autenticación PIN
2. `ClientAni` donde `(service_id, ani=identifier)` -> `Client` padre - servicios con autenticación ANI
3. de lo contrario `{clientid: 0, segundos: 0}`

### Deducción de crédito

```
POST /agi/clients/{service}/{client_id}/deduct
form: seconds=N
-> {"ok": true, "remaining": 1200}
```

### Seguimiento de llamadas en línea

```
POST /agi/calls/online
form: service, ani, did, client_id, operator (default 0)
-> {"ok": true}
-> {"ok": false, "reason": "call-already-active"}

GET /agi/calls/online/{service}/{ani}
-> {"llamada_activa": "true"}  o  {"llamada_activa": "false"}

POST /agi/calls/online/{service}/{ani}/assign
form: operator=N
-> {"ok": true}  o  {"ok": false, "reason": "call-not-found"}

POST /agi/calls/online/{service}/{ani}/close
form: _=1          (cuerpo ficticio - CURL de Asterisk solo hace GET o POST-body)
-> {"ok": true}    (idempotente)
```

### Menú de operador

```
GET /agi/operators/menu
-> {"disponibles": 3,
    "audio_str": "zvn/tarotistas/maria&zvn/tarotistas/jose&zvn/tarotistas/ana"}
```

`audio_str` está construido desde `Operator.audio_file`, ordenado por
`Operator.option`. Los operadores sin un `audio_file` cuentan hacia
`disponibles` pero se omiten de la cadena de audio.

### Selección de operador (atómica)

Usa `SELECT FOR UPDATE` para que dos llamadores concurrentes no puedan agarrar el mismo
operador. El modo aleatorio baraja candidatos y bloquea uno a la vez.

```
POST /agi/operators/select
form: mode=random
form: mode=option&selection=03

éxito:
-> {"ok": true,
    "operador_numero":   "1001",
    "operador_nombre":   "Maria",
    "operador_telefono": "56912345678",
    "operador_trunk":    "claro1"}

fallo:
-> {"ok": false, "reason": "operator-busy"}
-> {"ok": false, "reason": "no-operators"}
-> {"ok": false, "reason": "no-phone-configured"}
```

### Liberación de operador

```
POST /agi/operators/{number}/release
form: _=1
-> {"ok": true}
```

Sella `lastcall` en Redis para que la detección "operador olvidó cerrar sesión" tenga una señal.

### Login / logout de operador (dialplan)

```
POST /agi/operators/by-phone/{ani}/login   -> {"ok": true}
POST /agi/operators/by-phone/{ani}/logout  -> {"ok": true}
```

### Información de operador (búsqueda, sin reclamo)

Búsquedas de solo lectura usadas entre `/operators/menu` y `/operators/select`.
El dialplan reproduce el menú, la llamada elige una opción, el dialplan
llama uno de estos para traducir la entrada en la información de contacto del operador,
luego posteriormente llama a `/operators/select` para reclamar atómicamente. Dividir
la búsqueda del reclamo mantiene a los operadores libres durante la ventana de 5-10s de menú/audio;
el `SELECT FOR UPDATE` atómico en `/operators/select` resuelve la carrera resultante.
`loggedin` y `available` en la respuesta son solo informativos - confía en `/operators/select` para el reclamo real.

```
GET /agi/operators/by-option/{option}     (option: "1" o "01", relleno de cero internamente)
GET /agi/operators/by-ani/{ani}           (ani: número de teléfono registrado al operador)

éxito (misma forma de ambos):
-> {"ok": true,
    "operador_numero":   "1001",
    "operador_nombre":   "Maria",
    "operador_telefono": "56912345678",
    "operador_trunk":    "claro1",
    "loggedin":          true,
    "available":         true}

fallo:
-> {"ok": false, "reason": "not-found"}
-> {"ok": false, "reason": "no-phone-configured"}
```

## Redis / Valkey

Conexión gestionada por `firenze.redis.get_redis()` (dependencia FastAPI).
Degradación elegante: si Redis no está disponible, las llamadas de servicio registran una advertencia
y continúan con solo MySQL.

### Claves

```
firenze:operator:{number}    Campos Hash: loggedin, available, lastcall
firenze:call:{service}:{ani} Campos Hash: did, operator, client_id, created_at
```

TTL en ambos: 24h.

### Consumidores

- `services/operator_service.py` y `services/call_service.py` escriben en
  MySQL y Redis.
- `api/agi.py` lee a través de esos servicios.
- `asterisk_config/legacy-php/onlinecalls_redis.php` y
  `operators_redis.php` son lectores externos usados por dashboards heredados.
  Consumen las mismas claves.

## Dialplan

Tres copias viven bajo `asterisk_config/`:

| Ruta | Rol |
|---|---|
| `current/*.conf` (nivel superior) | Snapshot más antiguo, puro AGI. No cargado. Mantenido como referencia. |
| `current/new_config/*.conf` | Actualmente cargado por Asterisk. Híbrido: llamadas AGI antiguas + llamadas CURL nuevas lado a lado. |
| `new/*.conf` | Objetivo: solo CURL, `[prepago-service]` unificado. No desplegado. |

### Híbrido (en vivo) - `current/new_config/`

La parte superior de cada contexto de servicio ejecuta ambas rutas. Ejemplo de
`extensions_fonotarot.conf` `[prepago-fonotarot-cl]`:

```ini
; ruta nueva (CURL)
same => n,Set(response=${CURL(${FIRENZE_API}/calls/online/${servicio}/${ani})})
; ruta antigua (aún escribe al heredado)
same => n,Agi(${FIRENZE},online-calls,search,${servicio},${ani},${clientid})
```

Ambos tiempos de ejecución ven el evento. Los consumidores `JSON_DECODE` aún leen desde
las variables de canal de la ruta antigua donde la ruta nueva aún no la ha reemplazado completamente.

### Objetivo - `asterisk_config/new/`

Solo tres archivos:

```
extensions.conf            - globales, trampa, #include zvn + servicios
extensions_zvn.conf        - troncales entrantes, [selecciona-servicio],
                             supervisor, tarotista-login/-logout (CURL)
extensions_services.conf   - flujo unificado:
                              [prepago-service]   -> DNC + intro + despacho
                              [auth-ani]          -> búsqueda de cliente por ANI
                              [auth-pin]          -> búsqueda de cliente por PIN
                              [sub-post-auth]     -> límite de crédito + insertar llamada
                              [saldo-insuficiente]
                              [selecciona-operador] (menú + seleccionar + asignar)
                              [llama-operador]    (marcar + ganchos post-llamada)
```

Dos archivos por servicio (`extensions_alotarot.conf`,
`extensions_fonotarot.conf`) desaparecen completamente - `Service.auth_method` y
`Service.intro_audio` impulsan la ramificación dentro de `[prepago-service]`.

### Convenciones CURL en el dialplan objetivo

- GET: `${CURL(url)}`
- POST con cuerpo: `${CURL(url,field=val&field2=val2)}`
- Sin `CURLOPT()` - esta construcción de Asterisk no soporta `httpcustom` o
  `postfields`.
- Los endpoints que no necesitan un cuerpo semántico toman `_=1` como un campo de formulario ficticio,
  porque `CURL()` de Asterisk solo hace confiablemente GET o POST-con-cuerpo.

### Tabla de eliminación de troncales

Todos los números de teléfono de operadores se almacenan como E.164 (`56XXXXXXXXX`). Cada
troncal saliente espera un prefijo diferente. El dialplan elimina en tiempo de marcado usando
una búsqueda de globales:

```ini
same => n,Set(dial_num=${OPERATOR_TEL:${TRUNK_STRIP_${OPERATOR_TRUNK}}})
same => n,Dial(PJSIP/${dial_num}@${OPERATOR_TRUNK})
```

El default es strip=0 (E.164 completo) cuando la troncal no está en la tabla.

## Código muerto a eliminar (referencia cruzada tasks.md)

- `firenze/tarot.py`, `firenze/core.py`, `firenze/asterisk/`
- `firenze/audiotex/` + dependencia `peewee` + configuración `AUDIOTEX_DSN`
- `asterisk_agi/` (scripts AGI CLI antiguos)
- Dependencia `pystrix` (ya no importada)
- `asterisk_config/current/*.conf` snapshot de nivel superior (una vez que `new/` está en vivo)
