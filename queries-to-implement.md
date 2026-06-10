# Queries to implement

```sql
-- 5. OPERATOR AVAILABILITY PATTERN BY HOUR
-- When is each operator actually taking calls (billsec >= 30)
-- Useful to understand peak hours and detect operators reducing activity
SELECT
    zvn_operator                AS operator_id,
    DAYOFWEEK(calldate)     AS day_of_week,
    HOUR(calldate)          AS hour,
    COUNT(*)                AS sessions,
    ROUND(AVG(billsec), 1) AS avg_duration
FROM cdr
WHERE calldate >= NOW() - INTERVAL 60 DAY
  AND billsec >= 30
  AND zvn_operator is not NULL
GROUP BY zvn_operator, DAYOFWEEK(calldate), HOUR(calldate)
ORDER BY zvn_operator, day_of_week, hour;

-- 2. CLIENT-OPERATOR AFFINITY
-- How loyal is each client to a specific operator
-- High concentration = high dependency = high churn risk if operator leaves
SELECT
    zvn_clientid,
    zvn_operator,
    COUNT(*)                                            AS calls_to_operator,
    SUM(billsec)                                        AS billsec_with_operator,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER 
        (PARTITION BY zvn_clientid), 1)                     AS pct_of_client_calls,
    ROUND(SUM(billsec) * 100.0 / SUM(SUM(billsec)) OVER 
        (PARTITION BY zvn_clientid), 1)                     AS pct_of_client_billsec
FROM cdr
WHERE calldate >= NOW() - INTERVAL 60 DAY
  AND zvn_clientid IS NOT NULL AND zvn_clientid != '' and zvn_operator is not null
GROUP BY zvn_clientid, zvn_operator
ORDER BY zvn_clientid, calls_to_operator DESC;
-- 1. OPERATOR PROFILE
-- Who they are, how many clients, total usage, avg session length
SELECT 
    zvn_operator,
    COUNT(DISTINCT zvn_clientid)            AS unique_clients,
    COUNT(*)                            AS total_calls,
    SUM(billsec)                        AS total_billsec,
    ROUND(SUM(billsec) / 60, 1)        AS total_minutes,
    ROUND(AVG(billsec), 1)             AS avg_duration_sec,
    COUNT(CASE WHEN billsec < 30 THEN 1 END) AS availability_checks,
    COUNT(CASE WHEN billsec >= 30 THEN 1 END) AS real_sessions
FROM cdr
WHERE calldate >= NOW() - INTERVAL 60 DAY
GROUP BY zvn_operator
ORDER BY unique_clients DESC;
```
