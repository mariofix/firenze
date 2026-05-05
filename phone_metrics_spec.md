# Phone Service Metrics — Implementation Spec

## Overview

Two independent metrics derived from Asterisk CDR records:

1. **Operator Load** — capacity utilization per agent, modeled after Linux load average
2. **Client Usage Index (CVI)** — consumption pattern per client, normalized against their own baseline

No queue logic exists. Clients call a specific agent; if unavailable, they hang up and retry.

---

## Data Source

All metrics are derived from the **Asterisk CDR (Call Detail Records)** table. The minimum required fields are:

| Field | Description |
|---|---|
| `calldate` | Call start timestamp |
| `duration` | Total call duration in seconds |
| `billsec` | Answered duration in seconds |
| `src` | Caller ID (maps to client) |
| `dst` | Destination extension (maps to operator) |
| `disposition` | `ANSWERED`, `NO ANSWER`, `BUSY`, `FAILED` |

Client and operator identity must be resolved by mapping `src`/`dst` to your own records. CDR is read-only — do not modify the Asterisk schema.

---

## Metric 1: Operator Load

### Concept

Measures how busy an operator is relative to their capacity. Mirrors Linux load average: `1.0` = fully occupied, `>1.0` = overloaded, `<1.0` = available headroom.

### Windows

Scaled to the average call duration of ~30 minutes (1×, 5×, 15×):

| Window | Duration |
|---|---|
| Short | 30 minutes |
| Medium | 2.5 hours |
| Long | 7.5 hours |

### Calculation

```
operator_load = active_calls / operator_capacity
```

- `operator_capacity` = maximum concurrent calls the operator handles (typically 1)
- `active_calls` = calls with `disposition = ANSWERED` and `calldate + duration > now`
- Apply EMA across each window independently (see EMA formula below)

### Output Format

```
agent: silva    0.00  0.45  0.80  0.60   ← current / 30m / 2.5h / 7.5h
agent: rojas    1.00  1.20  0.95  0.75
agent: perez    0.00  0.10  0.30  0.55
```

### Alert Threshold

Sustained `medium_window > 0.85` warrants an alert or scheduling review.

---

## Metric 2: Client Usage Index (CVI)

### Concept

Measures how active a client is relative to their own normal behavior. `1.0` = typical day for that client. Deviations are significant regardless of absolute call volume.

### Calculation

```
cvi = ema_call_rate / client_personal_baseline
```

- `ema_call_rate` = EMA of calls per hour for this client, same three windows as Operator Load
- `client_personal_baseline` = rolling 30-day EMA of their historical call rate (updates daily)
- Only count `disposition = ANSWERED` and `disposition = NO ANSWER` — exclude `FAILED`

### Secondary Dimensions

Compute these as EMAs alongside CVI:

| Dimension | Source field | Notes |
|---|---|---|
| Avg call duration | `billsec` | Trend over time, not a single value |
| Unique agents contacted | `dst` | Distinct count per window |
| First-attempt success rate | `disposition` | `ANSWERED / total attempts` |
| Retry gap | `calldate` delta between consecutive `NO ANSWER` → `ANSWERED` for same `src` | Urgency proxy |

### Output Format

```
client: acme      cvi: 1.8 / 1.2 / 0.9    dur: 28m / 31m / 35m    agents: 3
client: initech   cvi: 0.0 / 0.1 / 0.2    dur:  —  / 22m / 29m    agents: 1
```

### Interpretation Signals

- **CVI trending to 0 + single agent relationship** → churn risk
- **High CVI + decreasing duration** → routine check-ins replacing deep consultations
- **Tight retry gaps on NO ANSWER** → urgent issue, consider proactive outreach

---

## EMA Formula

Standard exponential moving average, identical to Linux kernel `loadavg.c`:

```python
import math

def update_ema(previous_ema: float, current_value: float, dt: float, tau: float) -> float:
    """
    previous_ema : last stored EMA value
    current_value: instantaneous measurement (e.g. 0 or 1 for active call)
    dt           : seconds elapsed since last update
    tau          : window size in seconds (1800, 9000, 27000)
    """
    alpha = 1 - math.exp(-dt / tau)
    return alpha * current_value + (1 - alpha) * previous_ema

TAUS = {
    "30m":  1800,
    "2.5h": 9000,
    "7.5h": 27000,
}
```

- Update on every CDR insert (call end) or on a scheduler tick (every 60 seconds for active calls)
- Storage: one float per window per entity — no history buffer required

---

## Storage

Persist EMA state between restarts. Minimum schema:

```sql
-- Operator load EMA state
CREATE TABLE operator_load_ema (
    operator_id   VARCHAR(64) PRIMARY KEY,
    ema_30m       FLOAT NOT NULL DEFAULT 0,
    ema_2h5       FLOAT NOT NULL DEFAULT 0,
    ema_7h5       FLOAT NOT NULL DEFAULT 0,
    updated_at    TIMESTAMP NOT NULL
);

-- Client CVI EMA state
CREATE TABLE client_cvi_ema (
    client_id         VARCHAR(64) PRIMARY KEY,
    ema_30m           FLOAT NOT NULL DEFAULT 0,
    ema_2h5           FLOAT NOT NULL DEFAULT 0,
    ema_7h5           FLOAT NOT NULL DEFAULT 0,
    baseline_30d      FLOAT NOT NULL DEFAULT 0,
    baseline_updated  DATE NOT NULL,
    updated_at        TIMESTAMP NOT NULL
);
```

These tables live in your application database, not in Asterisk.

---

## Implementation Notes

- **Poll CDR** via read-only DB connection or AMI event `cdr` — do not tail log files
- **Scheduler tick**: run every 60 seconds to update EMAs for currently active calls (so load decays correctly even without a new CDR insert)
- **Bootstrap baseline**: on first run, compute `client_personal_baseline` from last 30 days of CDR history before starting live EMA updates
- **Operator capacity** should be configurable per operator, defaulting to 1
- CDR `duration` includes ring time; use `billsec` for actual talk time in duration metrics
