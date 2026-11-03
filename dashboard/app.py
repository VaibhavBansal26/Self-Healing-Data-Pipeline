from __future__ import annotations

import json
from typing import Any, Dict

import pandas as pd
import streamlit as st

from src.dashboard_service import (
    build_test_event,
    get_agent_decision_traces,
    get_consumer_state,
    get_demo_catalog,
    get_pipeline_summary,
    list_incidents,
    list_orders,
    list_reconciliation_runs,
    peek_dlq,
    preview_transformation,
    publish_custom_event,
    publish_demo_dataset,
    publish_test_event,
    replay_payload_to_raw_topic,
    run_reconciliation_now,
    set_consumer_paused,
    update_incident_status,
)


st.set_page_config(page_title="Self Healing Pipeline Dashboard", layout="wide")
st.title("Self Healing Data Pipeline Dashboard")
st.caption(
    "Visualize the Kafka pipeline, generate test data, control producer/consumer flow, preview transformations, and inspect LangGraph agent repairs."
)


PIPELINE_CSS = """
<style>
.pipeline-grid {display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 12px 0 20px 0;}
.pipeline-card {border: 1px solid #ddd; border-radius: 14px; padding: 14px; min-height: 95px; background: #fafafa; box-shadow: 0 1px 2px rgba(0,0,0,.05);}
.pipeline-card b {font-size: 15px;}
.pipeline-card small {color: #555;}
.arrow {text-align: center; font-size: 26px; padding-top: 28px; color: #777;}
.trace-card {border: 1px solid #ddd; border-radius: 12px; padding: 12px; margin: 8px 0; background: #fbfbfb;}
.badge {display: inline-block; padding: 3px 9px; border-radius: 999px; background: #eee; margin-right: 6px; font-size: 12px;}
</style>
"""
st.markdown(PIPELINE_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=5)
def cached_summary() -> Dict[str, Any]:
    return get_pipeline_summary()


@st.cache_data(ttl=5)
def cached_incidents(status: str, limit: int):
    return list_incidents(limit=limit, status=status)


@st.cache_data(ttl=5)
def cached_traces(status: str, limit: int):
    return get_agent_decision_traces(limit=limit, status=status)


@st.cache_data(ttl=5)
def cached_orders(limit: int):
    return list_orders(limit=limit)


@st.cache_data(ttl=10)
def cached_reconciliation(limit: int):
    return list_reconciliation_runs(limit=limit)


def refresh_dashboard() -> None:
    st.cache_data.clear()


def render_pipeline_diagram() -> None:
    st.markdown(
        """
<div class="pipeline-grid">
  <div class="pipeline-card"><b>1. Producer or Data API</b><br/><small>Demo generator, custom JSON, batch API, or Python producer sends order events.</small></div>
  <div class="arrow">→</div>
  <div class="pipeline-card"><b>2. Kafka raw_orders</b><br/><small>Raw ecommerce order stream with valid and malformed records.</small></div>
  <div class="arrow">→</div>
  <div class="pipeline-card"><b>3. Consumer</b><br/><small>Reads Kafka, supports pause/resume, tracks metrics, and commits offsets after processing.</small></div>
  <div class="arrow">→</div>
  <div class="pipeline-card"><b>4. Transform</b><br/><small>Trims fields, casts amount, normalizes status, fills safe defaults, adds schema version.</small></div>
  <div class="pipeline-card"><b>5. Validate</b><br/><small>Pydantic/schema contract validates required fields, positive amount, status enum, version.</small></div>
  <div class="arrow">→</div>
  <div class="pipeline-card"><b>6A. Valid Path</b><br/><small>Idempotent insert into PostgreSQL orders with event_id and event_hash protection.</small></div>
  <div class="pipeline-card"><b>6B. Failure Path</b><br/><small>Invalid records move to the LangGraph healing workflow.</small></div>
  <div class="pipeline-card"><b>7. LangGraph Agent</b><br/><small>Retrieves similar incidents, asks OpenAI for a structured safe action, applies guardrails.</small></div>
  <div class="arrow">→</div>
  <div class="pipeline-card"><b>8. Route Result</b><br/><small>Healed records are verified and inserted. Risky records go to manual review or DLQ.</small></div>
  <div class="arrow">→</div>
  <div class="pipeline-card"><b>9. Observability</b><br/><small>Dashboard, FastAPI, Prometheus, incidents, DLQ, reconciliation, replay audit.</small></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_payload_pair(original: Any, healed: Any) -> None:
    left, right = st.columns(2)
    with left:
        st.markdown("**Original payload**")
        st.json(original or {})
    with right:
        st.markdown("**Healed payload**")
        st.json(healed or {})


summary = cached_summary()
consumer_state = get_consumer_state()

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Orders", summary["orders_count"])
c2.metric("Incidents", summary["incident_count"])
c3.metric("Healed", summary["healed_count"])
c4.metric("Manual Review", summary["manual_review_count"])
c5.metric("Failed", summary["failed_count"])
c6.metric("DLQ", summary["dlq_count"])
c7.metric("Consumer", "Paused" if consumer_state.get("paused") else "Running")

st.divider()

tabs = st.tabs(
    [
        "Overview",
        "Pipeline Visualization",
        "Producer & Consumer",
        "Data API Playground",
        "Transformation Playground",
        "Agent Decision Trace",
        "Repairs & Approvals",
        "DLQ",
        "Reconciliation",
        "Testing",
    ]
)
(
    tab_overview,
    tab_pipeline,
    tab_controls,
    tab_data_api,
    tab_transform,
    tab_agent_trace,
    tab_incidents,
    tab_dlq,
    tab_reconciliation,
    tab_testing,
) = tabs

with tab_overview:
    st.subheader("What data are we using?")
    catalog = get_demo_catalog()
    st.write(catalog["dataset"])
    st.write(
        "The current demo uses synthetic ecommerce order events flowing through Kafka topic `raw_orders`, PostgreSQL table `orders`, and Kafka DLQ topic `dead_letter_events`."
    )
    st.dataframe(pd.DataFrame(catalog["fields"]), use_container_width=True)
    st.markdown("**Failure scenarios covered**")
    st.write(catalog["failure_scenarios"])

    st.subheader("Clean orders")
    orders = cached_orders(25)
    if orders:
        st.dataframe(pd.DataFrame(orders), use_container_width=True)
    else:
        st.info("No clean orders yet. Use the test event generator or demo producer tab to publish data.")

    st.subheader("Healing status")
    chart_data = pd.DataFrame(
        [
            {"status": "healed", "count": summary["healed_count"]},
            {"status": "manual_review", "count": summary["manual_review_count"]},
            {"status": "failed", "count": summary["failed_count"]},
        ]
    )
    st.bar_chart(chart_data, x="status", y="count")

with tab_pipeline:
    st.subheader("Visual pipeline diagram")
    render_pipeline_diagram()
    st.markdown("### Runtime endpoints")
    endpoint_cols = st.columns(5)
    endpoint_cols[0].link_button("Dashboard", "http://localhost:8501")
    endpoint_cols[1].link_button("Data API docs", "http://localhost:8000/docs")
    endpoint_cols[2].link_button("Airflow", "http://localhost:8080")
    endpoint_cols[3].link_button("Prometheus", "http://localhost:9090")
    endpoint_cols[4].link_button("Metrics", "http://localhost:9108/metrics")

with tab_controls:
    st.subheader("Producer and consumer controls")
    left, right = st.columns(2)

    with left:
        st.markdown("### Producer")
        transform_before_publish = st.checkbox("Apply deterministic transformation before publishing demo batch", value=False)
        if st.button("Publish demo dataset to Kafka"):
            result = publish_demo_dataset(transform=transform_before_publish)
            refresh_dashboard()
            st.success(f"Published {result['published_count']} events to {result['topic']}.")
            st.json(result)

        st.markdown("### Test event generator")
        scenario = st.selectbox("Scenario", get_demo_catalog().get("scenarios", []))
        scenario_transform = st.checkbox("Transform generated event before publish", value=False)
        preview = build_test_event(scenario=scenario)
        st.markdown("Generated payload preview")
        st.json(preview)
        col_one, col_batch = st.columns(2)
        if col_one.button("Publish selected test event"):
            result = publish_test_event(scenario=scenario, transform=scenario_transform)
            refresh_dashboard()
            st.success(f"Published {scenario} event.")
            st.json(result)
        if col_batch.button("Publish one event per scenario"):
            results = [publish_test_event(s, transform=scenario_transform) for s in get_demo_catalog().get("scenarios", [])]
            refresh_dashboard()
            st.success(f"Published {len(results)} scenario events.")
            st.json(results)

        st.markdown("### Custom event producer")
        default_event = {
            "event_id": "manual_evt_1",
            "customer_id": "cust_manual",
            "amount": "45.25",
            "currency": "usd",
            "status": "PAY",
        }
        custom_text = st.text_area("Custom event JSON", value=json.dumps(default_event, indent=2), height=220)
        custom_transform = st.checkbox("Transform custom event before publishing", value=True)
        if st.button("Publish custom event"):
            try:
                payload = json.loads(custom_text)
                result = publish_custom_event(payload, transform=custom_transform)
                refresh_dashboard()
                st.success("Custom event published.")
                st.json(result)
            except Exception as exc:
                st.error(f"Could not publish event: {exc}")

    with right:
        st.markdown("### Consumer")
        state = get_consumer_state()
        st.write("Current state:", "Paused" if state.get("paused") else "Running")
        col_a, col_b, col_c = st.columns(3)
        if col_a.button("Pause consumer"):
            set_consumer_paused(True)
            refresh_dashboard()
            st.warning("Consumer pause flag enabled. The container stays alive but stops polling Kafka.")
        if col_b.button("Resume consumer"):
            set_consumer_paused(False)
            refresh_dashboard()
            st.success("Consumer resumed.")
        if col_c.button("Refresh dashboard cache"):
            refresh_dashboard()
            st.success("Dashboard refreshed.")

        st.markdown("### Useful endpoints")
        st.code(
            """
Dashboard:        http://localhost:8501
Data API:         http://localhost:8000/docs
Airflow:          http://localhost:8080
Prometheus:       http://localhost:9090
Metrics API:      http://localhost:9108/metrics
Consumer metrics: http://localhost:9109/metrics
""",
            language="text",
        )

with tab_data_api:
    st.subheader("Data API Playground")
    st.write("Use the FastAPI service to publish events, preview transformations, inspect summary, and control the consumer.")
    st.link_button("Open Swagger UI", "http://localhost:8000/docs")
    st.link_button("Open API health", "http://localhost:8000/health")
    st.code(
        """
GET  /health
GET  /data/catalog
GET  /events/demo
POST /events
POST /events/batch
POST /events/demo?transform=false
POST /transform
POST /transform/batch
GET  /summary
GET  /consumer/state
POST /consumer/state
""",
        language="text",
    )
    st.markdown("### Example curl commands")
    st.code(
        """
curl http://localhost:8000/health
curl http://localhost:8000/data/catalog
curl -X POST "http://localhost:8000/events/demo?transform=false"
curl -X POST http://localhost:8000/transform \\
  -H "Content-Type: application/json" \\
  -d '{"payload":{"event_id":"api_1","customer_id":"cust_1","amount":"10.50","currency":"usd","status":"PAY"},"transform":true}'
""",
        language="bash",
    )

with tab_transform:
    st.subheader("Transformation playground")
    st.write("Preview deterministic cleaning before the record enters validation or the LangGraph healing path.")
    sample = {
        "event_id": "transform_preview_1",
        "customer_id": " cust_99 ",
        "amount": "1,250.75",
        "currency": "usd",
        "status": "PAY",
    }
    transform_text = st.text_area("Payload to transform", value=json.dumps(sample, indent=2), height=250)
    if st.button("Preview transformation"):
        try:
            result = preview_transformation(json.loads(transform_text))
            render_payload_pair(result["original"], result["transformed"])
            st.markdown("**Transformation steps**")
            st.write(result["steps"] or ["No deterministic changes were needed."])
        except Exception as exc:
            st.error(f"Transformation failed: {exc}")

with tab_agent_trace:
    st.subheader("Agent decision trace")
    st.write("This screen explains how malformed records moved through validation, LangGraph diagnosis, guardrails, repair, verification, and final routing.")
    trace_left, trace_right = st.columns([1, 1])
    with trace_left:
        trace_status = st.selectbox("Trace status filter", ["all", "healed", "manual_review", "failed", "approved_for_replay", "closed"])
    with trace_right:
        trace_limit = st.slider("Trace rows", 5, 100, 25, key="trace_limit")
    traces = cached_traces(trace_status, trace_limit)
    if not traces:
        st.info("No agent traces yet. Publish malformed events from the Producer & Consumer tab.")
    for trace in traces:
        title = f"Incident {trace['incident_id']} | {trace.get('event_id')} | {trace.get('status')}"
        with st.expander(title):
            st.markdown(
                f"<span class='badge'>Action: {trace.get('healing_action') or 'none'}</span>"
                f"<span class='badge'>Risk: {trace.get('risk_level') or 'n/a'}</span>"
                f"<span class='badge'>Status: {trace.get('status')}</span>",
                unsafe_allow_html=True,
            )
            steps = pd.DataFrame(trace.get("agent_steps", []))
            if not steps.empty:
                st.dataframe(steps, use_container_width=True, hide_index=True)
            st.markdown("**Validation error**")
            st.code(trace.get("error_message") or "", language="text")
            render_payload_pair(trace.get("original_payload"), trace.get("healed_payload"))

with tab_incidents:
    st.subheader("Repairs and human approval queue")
    left, right = st.columns([1, 1])
    with left:
        status_filter = st.selectbox("Filter by status", ["all", "healed", "manual_review", "failed", "approved_for_replay", "closed"])
    with right:
        limit = st.slider("Rows", 5, 100, 25)

    incidents = cached_incidents(status_filter, limit)
    if incidents:
        table_rows = [
            {
                "incident_id": item["incident_id"],
                "event_id": item["event_id"],
                "status": item["status"],
                "risk_level": item["risk_level"],
                "healing_action": item["healing_action"],
                "created_at": item["created_at"],
            }
            for item in incidents
        ]
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

        selected_id = st.number_input("Incident id to inspect", min_value=1, step=1)
        selected = next((item for item in incidents if item["incident_id"] == selected_id), None)
        if selected:
            render_payload_pair(selected.get("original_payload"), selected.get("healed_payload"))
            st.markdown("**Full incident record**")
            st.json(selected)
            reviewer_notes = st.text_area("Reviewer notes")
            col_a, col_b, col_c = st.columns(3)
            if col_a.button("Approve for replay"):
                update_incident_status(selected_id, "approved_for_replay", reviewer_notes)
                refresh_dashboard()
                st.success("Incident approved for replay.")
            if col_b.button("Close as healed"):
                update_incident_status(selected_id, "healed", reviewer_notes)
                refresh_dashboard()
                st.success("Incident marked healed.")
            if col_c.button("Reject or keep failed"):
                update_incident_status(selected_id, "failed", reviewer_notes)
                refresh_dashboard()
                st.warning("Incident marked failed.")

            payload = selected.get("healed_payload") or selected.get("original_payload")
            if st.button("Replay selected payload to raw_orders"):
                result = replay_payload_to_raw_topic(payload)
                st.success(result)
        else:
            st.info("Enter an incident id shown in the table to inspect payloads and approve repairs.")
    else:
        st.info("No incidents found for this filter.")

with tab_dlq:
    st.subheader("Dead Letter Queue")
    if st.button("Peek DLQ"):
        records = peek_dlq(max_messages=10)
        if records:
            st.json(records)
        else:
            st.info("No DLQ records found.")

with tab_reconciliation:
    st.subheader("Airflow reconciliation runs")
    if st.button("Run reconciliation now"):
        result = run_reconciliation_now()
        refresh_dashboard()
        st.success(result)

    runs = cached_reconciliation(20)
    if runs:
        st.dataframe(pd.DataFrame(runs), use_container_width=True)
    else:
        st.info("No reconciliation runs yet. Start Airflow or run reconciliation manually.")

with tab_testing:
    st.subheader("How to test this project")
    st.code(
        """
# Unit tests
PYTHONPATH=. pytest -q tests

# Start infra and app services
cp .env.example .env
docker compose up -d

# Create Kafka topics
./scripts/create_topics.sh

# Publish demo events through Python producer
PYTHONPATH=. KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python -m src.producer

# Publish demo events through API
curl -X POST "http://localhost:8000/events/demo?transform=false"

# Open the dashboard and use the Producer & Consumer tab
open http://localhost:8501
""",
        language="bash",
    )
    st.write(
        "The dashboard validates that the pipeline is observable and controllable: produce events, pause or resume the consumer, preview transformations, inspect agent decisions, replay payloads, check DLQ records, and trigger reconciliation."
    )
