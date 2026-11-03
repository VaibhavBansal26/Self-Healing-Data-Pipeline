# PostgreSQL demo queries

Run:

```bash
docker exec -it healing_postgres psql -U postgres -d pipeline_db
```

Show inserted clean records:

```sql
SELECT event_id, customer_id, amount, currency, status, created_at
FROM orders
ORDER BY created_at DESC
LIMIT 20;
```

Show problem, reason, action, risk, and status:

```sql
SELECT incident_id, event_id, error_type, healing_action, risk_level, confidence, status, created_at
FROM pipeline_incidents
ORDER BY created_at DESC
LIMIT 20;
```

Show healed by agent:

```sql
SELECT event_id, healing_action, risk_level, confidence, original_payload, healed_payload
FROM pipeline_incidents
WHERE status = 'healed'
ORDER BY created_at DESC;
```

Show pending human approvals:

```sql
SELECT incident_id, event_id, error_message, original_payload, healing_action, risk_level
FROM pipeline_incidents
WHERE status = 'manual_review'
ORDER BY created_at DESC;
```

Show failed and DLQ routed records:

```sql
SELECT incident_id, event_id, error_message, original_payload, healing_action, status
FROM pipeline_incidents
WHERE status = 'failed'
ORDER BY created_at DESC;
```

Risk summary:

```sql
SELECT COALESCE(risk_level, 'unknown') AS risk_level, status, COUNT(*)
FROM pipeline_incidents
GROUP BY risk_level, status
ORDER BY risk_level, status;
```

Agent action summary:

```sql
SELECT healing_action, status, COUNT(*)
FROM pipeline_incidents
GROUP BY healing_action, status
ORDER BY healing_action, status;
```
