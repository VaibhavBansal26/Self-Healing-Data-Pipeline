"""MCP server exposing self healing pipeline tools.

Run directly:
    python -m mcp_server.server

Test with MCP Inspector:
    npx @modelcontextprotocol/inspector python -m mcp_server.server
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from src.pipeline_tools import (
    get_dlq_count_tool,
    get_order_tool,
    get_redis_retry_count_tool,
    peek_dlq_tool,
    query_recent_incidents_tool,
    replay_dlq_event_tool,
    run_reconciliation_tool,
    search_similar_incidents_tool,
)

mcp = FastMCP("self-healing-data-pipeline")


@mcp.tool()
def search_similar_incidents(payload: Dict[str, Any], error_message: str, k: int = 3) -> List[Dict[str, Any]]:
    """Search vector memory for similar data pipeline incidents."""
    return search_similar_incidents_tool(payload, error_message, k)


@mcp.tool()
def get_redis_retry_count(fingerprint: str) -> Dict[str, Any]:
    """Get Redis retry count for a payload fingerprint."""
    return get_redis_retry_count_tool(fingerprint)


@mcp.tool()
def query_recent_incidents(limit: int = 10, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Query recent PostgreSQL incident records."""
    return query_recent_incidents_tool(limit, status)


@mcp.tool()
def get_order(event_id: str) -> Dict[str, Any]:
    """Look up an order by event_id in PostgreSQL."""
    return get_order_tool(event_id)


@mcp.tool()
def get_dlq_count() -> Dict[str, Any]:
    """Return DLQ message count."""
    return get_dlq_count_tool()


@mcp.tool()
def peek_dlq(max_messages: int = 5) -> List[Dict[str, Any]]:
    """Peek a small sample of DLQ records."""
    return peek_dlq_tool(max_messages)


@mcp.tool()
def replay_dlq_event(
    payload: Dict[str, Any],
    target_topic: str = "raw_orders",
    reviewer: Optional[str] = None,
    reviewer_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Replay a reviewed DLQ payload back to a Kafka topic and write an audit record."""
    return replay_dlq_event_tool(payload, target_topic, reviewer, reviewer_notes)


@mcp.tool()
def run_reconciliation() -> Dict[str, Any]:
    """Run daily reconciliation between PostgreSQL and Kafka DLQ."""
    return run_reconciliation_tool()


if __name__ == "__main__":
    mcp.run()
