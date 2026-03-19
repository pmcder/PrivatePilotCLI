from __future__ import annotations

from privatepilotcli.mcp_manager import MCPManager


class ToolRouter:
    def __init__(self, mcp_manager: MCPManager) -> None:
        self._mcp = mcp_manager
        self._schemas: list[dict] | None = None

    async def refresh_schemas(self) -> None:
        self._schemas = await self._mcp.list_tools()

    def get_tool_schemas(self) -> list[dict]:
        return self._schemas or []

    async def dispatch(self, tool_name: str, arguments: dict) -> str:
        return await self._mcp.call_tool(tool_name, arguments)
