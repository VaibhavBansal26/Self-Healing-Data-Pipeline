import os
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
RAW_TOPIC = os.getenv("RAW_TOPIC", "raw_orders")
DLQ_TOPIC = os.getenv("DLQ_TOPIC", "dead_letter_events")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "self_healing_pipeline_group")

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "pipeline_db"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "pipeline_incidents")

AUTO_APPROVE_LOW_RISK = os.getenv("AUTO_APPROVE_LOW_RISK", "true").lower() == "true"
ENABLE_TERMINAL_HUMAN_APPROVAL = os.getenv("ENABLE_TERMINAL_HUMAN_APPROVAL", "true").lower() == "true"

MCP_CLIENT_MODE = os.getenv("MCP_CLIENT_MODE", "local")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9108"))
ENABLE_PROMETHEUS_SERVER = os.getenv("ENABLE_PROMETHEUS_SERVER", "false").lower() == "true"

MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", "3"))
LLM_CONFIDENCE_THRESHOLD = float(os.getenv("LLM_CONFIDENCE_THRESHOLD", "0.80"))
DEFAULT_SCHEMA_VERSION = int(os.getenv("DEFAULT_SCHEMA_VERSION", "1"))
PII_FIELDS = {field.strip() for field in os.getenv("PII_FIELDS", "email,phone,ssn,address").split(",") if field.strip()}


AUTO_HEAL_PIPELINE_STEPS = os.getenv("AUTO_HEAL_PIPELINE_STEPS", "true").lower() == "true"
PIPELINE_HEALTH_CHECK_TIMEOUT_SECONDS = int(os.getenv("PIPELINE_HEALTH_CHECK_TIMEOUT_SECONDS", "3"))
AIRFLOW_API_BASE_URL = os.getenv("AIRFLOW_API_BASE_URL", "http://airflow-webserver:8080")
