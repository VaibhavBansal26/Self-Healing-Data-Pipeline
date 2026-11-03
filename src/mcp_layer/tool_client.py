"""Client wrapper for pipeline tools.

Default mode is local: LangGraph calls the same tool functions that the MCP
server exposes. This keeps the demo easy to run.

Set MCP_CLIENT_MODE=stdio to call the real MCP server over stdio for testing.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict

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

MCP_CLIENT_MODE = os.getenv("MCP_CLIENT_MODE", "local").lower()

_LOCAL_TOOLS = {
    "search_similar_incidents": search_similar_incidents_tool,
    "get_redis_retry_count": get_redis_retry_count_tool,
    "query_recent_incidents": query_recent_incidents_tool,
    "get_order": get_order_tool,
    "get_dlq_count": get_dlq_count_tool,
    "peek_dlq": peek_dlq_tool,
    "replay_dlq_event": replay_dlq_event_tool,
    "run_reconciliation": run_reconciliation_tool,
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


async def _call_stdio_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            content = getattr(result, "content", [])
            if not content:
                return None
            if len(content) == 1 and hasattr(content[0], "text"):
                return _json_safe(content[0].text)
            return [_json_safe(getattr(item, "text", item)) for item in content]


def call_pipeline_tool(tool_name: str, **arguments: Any) -> Any:
    """Call a pipeline tool through local or MCP stdio mode."""
    if MCP_CLIENT_MODE == "stdio":
        return asyncio.run(_call_stdio_tool(tool_name, arguments))

    if tool_name not in _LOCAL_TOOLS:
        raise ValueError(f"Unknown pipeline tool: {tool_name}")
    return _LOCAL_TOOLS[tool_name](**arguments)


if __name__ == "__main__":
    print("Available local/MCP tools:")
    for name in sorted(_LOCAL_TOOLS):
        print(f"- {name}")
