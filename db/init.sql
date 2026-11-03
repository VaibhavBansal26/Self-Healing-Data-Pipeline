CREATE TABLE IF NOT EXISTS orders (
    event_id TEXT PRIMARY KEY,
    event_hash TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    customer_id TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_incidents (
    incident_id SERIAL PRIMARY KEY,
    event_id TEXT,
    event_hash TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    original_payload JSONB NOT NULL,
    healed_payload JSONB,
    healing_action TEXT,
    risk_level TEXT,
    confidence NUMERIC,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reconciliation_runs (
    run_id SERIAL PRIMARY KEY,
    run_date DATE DEFAULT CURRENT_DATE,
    orders_count INTEGER NOT NULL,
    incident_count INTEGER NOT NULL,
    dlq_count INTEGER NOT NULL DEFAULT 0,
    unresolved_incident_count INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dlq_replay_audit (
    replay_id SERIAL PRIMARY KEY,
    event_id TEXT,
    event_hash TEXT,
    original_payload JSONB NOT NULL,
    replayed_payload JSONB,
    replay_status TEXT NOT NULL,
    reviewer TEXT,
    reviewer_notes TEXT,
    failure_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_metrics_snapshot (
    snapshot_id SERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC NOT NULL,
    labels JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS pipeline_step_incidents (
    step_incident_id SERIAL PRIMARY KEY,
    component TEXT NOT NULL,
    problem_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    detected_state JSONB,
    recovery_action TEXT,
    verification_result JSONB,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'detected',
    requires_human_approval BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Upgrade: live event journey, RAG evidence, schema evolution, and failure simulations.
ALTER TABLE pipeline_incidents ADD COLUMN IF NOT EXISTS agent_trace JSONB;
ALTER TABLE pipeline_incidents ADD COLUMN IF NOT EXISTS rag_evidence JSONB;
ALTER TABLE pipeline_incidents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS event_journey (
    journey_id SERIAL PRIMARY KEY,
    event_id TEXT,
    event_hash TEXT,
    stage TEXT NOT NULL,
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    action TEXT,
    risk_level TEXT,
    payload JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_versions (
    schema_version INTEGER PRIMARY KEY,
    schema_name TEXT NOT NULL,
    compatibility TEXT NOT NULL DEFAULT 'backward',
    description TEXT,
    example_payload JSONB,
    is_supported BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_versions(schema_version, schema_name, compatibility, description, example_payload, is_supported)
VALUES
(1, 'order_v1', 'baseline', 'Baseline order schema with amount as dollars and status enum.', '{"event_id":"evt_1","customer_id":"cust_1","amount":49.99,"currency":"USD","status":"paid","schema_version":1}', TRUE),
(2, 'order_v2', 'backward', 'Schema v2 accepts amount_cents and order_state, then normalizes to v1 contract for the sink.', '{"event_id":"evt_2","customer_id":"cust_1","amount_cents":4999,"currency":"USD","order_state":"PAID","schema_version":2}', TRUE)
ON CONFLICT (schema_version) DO NOTHING;


-- Final production upgrade: operational recovery, alerting, approvals, log diagnosis, and learning memory.
CREATE TABLE IF NOT EXISTS human_approval_requests (
    approval_id SERIAL PRIMARY KEY,
    step_incident_id INTEGER,
    component TEXT NOT NULL,
    event_id TEXT,
    proposed_action TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    agent_reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewer TEXT,
    reviewer_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recovery_action_memory (
    memory_id SERIAL PRIMARY KEY,
    component TEXT NOT NULL,
    problem_type TEXT NOT NULL,
    recovery_action TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence JSONB,
    latency_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_events (
    alert_id SERIAL PRIMARY KEY,
    component TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'dashboard',
    delivered BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS log_diagnoses (
    diagnosis_id SERIAL PRIMARY KEY,
    component TEXT NOT NULL,
    pattern TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    sample TEXT,
    recommendation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_trace_events (
    trace_id SERIAL PRIMARY KEY,
    trace_name TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
