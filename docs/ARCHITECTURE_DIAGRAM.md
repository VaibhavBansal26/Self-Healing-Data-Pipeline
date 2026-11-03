# Short Architecture Diagram

![Architecture diagram](assets/architecture-diagram.svg)

## Mermaid view

```mermaid
flowchart LR
  UI[React Dashboard] --> API[FastAPI Control Plane]
  API --> KAFKA[Kafka raw_orders]
  KAFKA --> CONSUMER[Consumer Service]
  CONSUMER --> RULES[Rules Engine]
  RULES --> AGENT[LangGraph Agent]
  AGENT --> RAG[RAG / Vector Memory]
  AGENT --> MCP[MCP Tool Mesh]
  MCP --> DOCKER[Docker Recovery]
  MCP --> AIRFLOW[Airflow Recovery]
  MCP --> DBTOOLS[DB / Redis / DLQ Tools]
  AGENT --> APPROVAL[Human Approval]
  RULES --> POSTGRES[PostgreSQL]
  RULES --> DLQ[Dead Letter Queue]
  AUTO[Background Auto-Healer Worker] --> API
  API --> METRICS[Prometheus / Traces / Logs]
```

## Separation of responsibilities

- **Auto-healer worker:** detects unhealthy stages and triggers the recovery endpoint.
- **Agent decision layer:** decides safe vs risky recovery using policy, memory, and tool context.
- **Recovery adapters:** execute Docker/Kafka/Airflow actions.
- **Verifier:** reruns health checks before marking recovered.
- **Memory:** stores outcomes for future recovery decisions.
