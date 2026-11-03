from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator


def reconciliation_task():
    # Airflow executes this in its own runtime, so imports stay inside the callable.
    import sys
    sys.path.append('/opt/airflow/project')
    from src.reconciliation import run_daily_reconciliation
    return run_daily_reconciliation()


with DAG(
    dag_id="daily_self_healing_pipeline_reconciliation",
    description="Daily reconciliation between Kafka DLQ, PostgreSQL orders, and incident records.",
    start_date=datetime(2026, 1, 1),
    schedule_interval="@daily",
    catchup=False,
    default_args={
        "owner": "data-platform",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["kafka", "reconciliation", "self-healing", "langgraph"],
) as dag:
    reconcile = PythonOperator(
        task_id="reconcile_orders_incidents_and_dlq",
        python_callable=reconciliation_task,
    )
