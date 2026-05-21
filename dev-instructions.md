# Instrucciones de Desarrollo

## Configuración

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mkdir -p logs
```

Crear `.env` en la raíz del proyecto:

```env
SQLALCHEMY_DATABASE_URL=mysql+pymysql://user:pass@localhost/zvn_firenze
SECRET_KEY=dev-secret
DEBUG=True
```

Ejecutar migraciones:

```bash
alembic upgrade head
```

## Ejecutar

```bash
fastapi dev run.py --port 9002
```

## Probar puntos finales

**Verificación de DNC — número no en la lista:**
```bash
curl http://localhost:9002/agi/dnc/5551234567
# {"dnc":"NO"}
```

**Verificación de DNC — agregar un número primero, luego verificar:**
```bash
# Agregar a través del panel de administración en http://localhost:9002/boss
# o directamente en MySQL:
# INSERT INTO dnc (ani, reason) VALUES ('5551234567', 'test');

curl http://localhost:9002/agi/dnc/5551234567
# {"dnc":"YES"}
```

**Límite de crédito — saldo cero:**
```bash
curl "http://localhost:9002/agi/credits/limit?seconds=0"
# {"timeout":1,"audio":"","minutes":0}
```

**Límite de crédito — 5 minutos (300s):**
```bash
curl "http://localhost:9002/agi/credits/limit?seconds=300"
# {"timeout":300,"audio":"zvn/saldo/5","minutes":5}
```

**Límite de crédito — 1 hora (3600s):**
```bash
curl "http://localhost:9002/agi/credits/limit?seconds=3600"
# {"timeout":3600,"audio":"zvn/saldo/60","minutes":60}
```

**Límite de crédito — más que el máximo (límite de 7200s):**
```bash
curl "http://localhost:9002/agi/credits/limit?seconds=9999"
# {"timeout":7200,"audio":"zvn/saldo/121","minutes":121}
```

## Dialplan de Asterisk

Agregar a su `extensions.conf` (Firenze se ejecuta en el puerto 9002):

```ini
; Verificación de DNC — colgar si la persona que llama está en la lista de no llamar
same => n,Set(DNC_RESULT=${CURL(http://localhost:9002/agi/dnc/${CALLERID(num)})})
same => n,Set(DNC=${JSON_DECODE(DNC_RESULT,dnc)})
same => n,GotoIf($["${DNC}" = "YES"]?dnc_hangup)

; Límite de crédito — establecer tiempo de espera de llamada y reproducir audio de saldo
same => n,Set(LIMIT_RESULT=${CURL(http://localhost:9002/agi/credits/limit?seconds=${CREDIT_SECONDS})})
same => n,Set(TIMEOUT(absolute)=${JSON_DECODE(LIMIT_RESULT,timeout)})
same => n,Playback(${JSON_DECODE(LIMIT_RESULT,audio)})

; Objetivo de cuelgue de DNC
same => n(dnc_hangup),Playback(zvn/dnc)
same => n,Hangup()
```

Recargar dialplan después de cambios:

```bash
asterisk -rx "dialplan reload"
```

## Panel de administración

```
http://localhost:9002/boss
```

Administrar la lista de DNC desde aquí (agregar, editar, eliminar entradas).

## Documentación de API

```
http://localhost:9002/office
```
