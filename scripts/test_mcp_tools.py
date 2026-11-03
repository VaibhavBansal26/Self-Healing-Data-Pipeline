"""Small smoke test for the MCP tool layer.

Local mode:
    python scripts/test_mcp_tools.py

Real MCP stdio mode:
    MCP_CLIENT_MODE=stdio python scripts/test_mcp_tools.py
"""

from src.mcp_layer.tool_client import call_pipeline_tool


if __name__ == "__main__":
    print("DLQ count:")
    print(call_pipeline_tool("get_dlq_count"))

    print("Recent incidents:")
    print(call_pipeline_tool("query_recent_incidents", limit=5))

    print("Similar incident search:")
    print(
        call_pipeline_tool(
            "search_similar_incidents",
            payload={
                "event_id": "demo",
                "customer_id": "c1",
                "amount": "12.5",
                "status": "paid",
            },
            error_message="amount should be a valid number, currency missing",
            k=2,
        )
    )
