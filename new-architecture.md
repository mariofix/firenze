# Firenze - Arquitectura

> Estado actual de la migración: [tasks.md](tasks.md)
> Referencia de implementación (endpoints, configuraciones, código): [tech.md](tech.md)

## Qué es Firenze

Firenze es la capa de comunicaciones y gestión de Asterisk para la plataforma FonoTarot. 
Es responsable del enrutamiento de llamadas, estado de operadores, seguimiento de créditos 
y estado de llamadas activas. Es uno de los dos servicios en la pila.

| Responsabilidad | Propietario |
|---|---|
| Tienda frontal, pagos, cuentas de usuario | nuevo-fonotarot (Flask) |
| Flujo de llamadas Asterisk, operadores, créditos, DIDs, DNC | Firenze (FastAPI) |
| Comunicación | nuevo-fonotarot -> Firenze HTTP API |

Firenze conoce: identificadores de cliente, saldos de crédito, operadores, servicios,
llamadas activas, lista DNC.

Firenze no conoce: cómo se compraron los créditos, proveedores de pago,
contraseñas de tienda frontal, contactos de marketing.

## Integración Asterisk: CURL desde el dialplan

Asterisk habla con Firenze a través de HTTP en localhost. Cada punto de decisión 
del dialplan que antes generaba un subproceso Python AGI (~500-1500ms por generación) 
se convierte en una `CURL()` + `JSON_DECODE()` al servicio FastAPI siempre en ejecución 
(~5-10ms por llamada).

```
; antes: generar proceso Python
same => n,Agi(${FIRENZE},services,did,${did})

; después: HTTP al servidor en ejecución
same => n,Set(resp=${CURL(${FIRENZE_API}/services/did/${did})})
same => n,Set(siguiente=${JSON_DECODE(resp,siguiente)})
```

Una llamada típica solía invocar AGI 5-6 veces (3-9s de silencio percibido por la llamada).
El objetivo es 2-4 llamadas CURL totalizando 10-60ms.

### ¿Por qué no ARI?

ARI (Interfaz REST de Asterisk, impulsada por WebSocket) hace que Firenze sea una 
dependencia siempre activa con estado: si muere, las llamadas mueren. También requiere 
reescribir toda la lógica del dialplan en Python y es más difícil de depurar que HTTP sin estado. 
Con ~6 canales concurrentes ese costo no está justificado.

### ¿Por qué no mantener AGI?

AGI funciona pero genera un nuevo intérprete Python por paso de llamada. Cargar 
SQLAlchemy + Typer + Redis en cada generación domina la latencia de llamada en un 
Linode de 2GB.

### Seguridad de endpoints AGI

Los endpoints `/agi/` están orientados al dialplan y deben ser rápidos. El `CURL()` 
de Asterisk no puede gestionar flujos de tokens. La protección es vinculación a localhost 
más una cabecera de clave API estática opcional. Los endpoints públicos protegidos de Firenze 
usan `x-api-key` + `x-api-secret`, y SQLAdmin usa sesiones de cookies.

## Descripción general del modelo de dominio

- **Service** - un servicio vendible (`fonotarot-cl`, `alotarot`, `fonotarot-latam`).
  Lleva `auth_method` ("ani" o "pin") e `intro_audio`. Tiene muchos `ServiceNumber`s (DIDs).
- **Client** - tabla unificada con clave `(service_id, client_id)`. Contiene
  `credits` (segundos), `pin` cuando auth_method es pin. Una tabla secundaria `ClientAni` 
  mapea N ANIs a un cliente para servicios con autenticación ANI.
- **Operator** - número interno, dígitos de opción IVR, `audio_file`. Las filas 
  relacionadas `OperatorPhone` contienen números de contacto y troncales salientes.
- **OnlineCall** - fila por llamada activa, única en `(service, ani)`. Se elimina
  al colgar.
- **DoNotCall** - ANIs que deben ser rechazados inmediatamente.

Consulta [tech.md](tech.md) para las columnas exactas.

## Estado de operador: MySQL como fuente de verdad + caché caliente Redis

MySQL es autoritario. Redis/Valkey es un caché de lectura rápida consumido por 
el flujo de llamadas (`/agi/operators/menu`) y lectores heredados PHP externos.

- Ruta de escritura: cada cambio de estado (login, logout, select, release) escribe 
  en MySQL y Redis. La escritura en Redis es un espejo de mejor esfuerzo - si Redis 
  está caído, MySQL aún se compromete y registramos la degradación.
- Ruta de lectura: menú + disponibilidad leen primero desde Redis, retroceden a MySQL.
- TTL 24h: maneja naturalmente "operador olvidó cerrar sesión".
- Opt-in por operador a través de `Operator.enable_valkey` - nos permite migrar
  operadores al caché uno a uno.

El mismo patrón para llamadas activas (`firenze:call:{service}:{ani}`).

## Despliegue

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
|   CURL a localhost:9002              |
+--------------------------------------+
```

- Firenze se ejecuta como servicio systemd: `gunicorn run:app -k uvicorn.workers.UvicornWorker`
- Un worker es suficiente con la carga actual
- Asterisk golpea Firenze a través de `${FIRENZE_API}` en localhost
- Escalado = duplicar todo el Linode (p. ej. región europea)
- Sin Docker para Asterisk - metal desnudo, enrollado a mano

## Pila de tecnología

| Capa | Tecnología |
|---|---|
| API Web | FastAPI + Uvicorn + Gunicorn |
| ORM | SQLAlchemy 2.0 (`Mapped` / `mapped_column`) |
| Migraciones | Alembic, configuración en `pyproject.toml` |
| Validación | Pydantic v2 + pydantic-settings |
| Base de datos | MySQL a través de PyMySQL |
| Caché / estado caliente | Redis/Valkey a través de `redis-py` |
| Admin | sqladmin en `/boss` |
| CLI | Typer - admin + migración + depuración solo, ya no en la ruta caliente de llamada |
| Autenticación | Credenciales API (`x-api-key` + `x-api-secret`) + sesiones de cookies SQLAdmin |

El CLI todavía se distribuye (punto de entrada `firenze`) pero Asterisk ya no 
lo invoca durante las llamadas. Todo el tráfico en tiempo de llamada es HTTP.
