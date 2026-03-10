# Dev Instructions

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mkdir -p logs
```

Create `.env` in the project root:

```env
SQLALCHEMY_DATABASE_URL=mysql+pymysql://user:pass@localhost/zvn_firenze
SECRET_KEY=dev-secret
DEBUG=True
```

Run migrations:

```bash
alembic upgrade head
```

## Run

```bash
fastapi dev run.py --port 8000
```

## Test endpoints

**DNC check — number not in list:**
```bash
curl http://localhost:8000/agi/dnc/5551234567
# {"dnc":"NO"}
```

**DNC check — add a number first, then check:**
```bash
# Add via admin panel at http://localhost:8000/boss
# or directly in MySQL:
# INSERT INTO dnc (ani, reason) VALUES ('5551234567', 'test');

curl http://localhost:8000/agi/dnc/5551234567
# {"dnc":"YES"}
```

**Credit limit — zero balance:**
```bash
curl "http://localhost:8000/agi/credits/limit?seconds=0"
# {"timeout":1,"audio":"","minutes":0}
```

**Credit limit — 5 minutes (300s):**
```bash
curl "http://localhost:8000/agi/credits/limit?seconds=300"
# {"timeout":300,"audio":"zvn/saldo/5","minutes":5}
```

**Credit limit — 1 hour (3600s):**
```bash
curl "http://localhost:8000/agi/credits/limit?seconds=3600"
# {"timeout":3600,"audio":"zvn/saldo/60","minutes":60}
```

**Credit limit — over max (7200s cap):**
```bash
curl "http://localhost:8000/agi/credits/limit?seconds=9999"
# {"timeout":7200,"audio":"zvn/saldo/121","minutes":121}
```

## Admin panel

```
http://localhost:8000/boss
```

Manage the DNC list from here (add, edit, delete entries).

## API docs

```
http://localhost:8000/office
```
