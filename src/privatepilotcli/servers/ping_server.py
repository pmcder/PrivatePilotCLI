"""Minimal MCP server with a ping tool."""

from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ping-server")


@mcp.tool()
def ping() -> str:
    """Returns pong with the current UTC timestamp."""
    ts = datetime.now(timezone.utc).isoformat()
    return f"pong — {ts}"


if __name__ == "__main__":
    mcp.run()
