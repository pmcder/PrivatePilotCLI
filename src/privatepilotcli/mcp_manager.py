from __future__ import annotations

import json
import os
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from privatepilotcli.config import MCPServerConfig


class MCPManager:
    def __init__(self, server_configs: dict[str, MCPServerConfig]) -> None:
        self._configs = server_configs
        self._sessions: dict[str, ClientSession] = {}
        self._exit_stack = AsyncExitStack()

    async def startup(self) -> None:
        await self._exit_stack.__aenter__()
        for name, cfg in self._configs.items():
            try:
                session = await self._connect(name, cfg)
                self._sessions[name] = session
            except Exception as e:
                print(f"[mcp] Warning: could not connect to server '{name}': {e}")

    async def _connect(self, name: str, cfg: MCPServerConfig) -> ClientSession:
        if cfg.transport == "stdio":
            if not cfg.command:
                raise ValueError(f"stdio server '{name}' requires 'command'")
            merged_env = {**os.environ, **cfg.env}
            params = StdioServerParameters(
                command=cfg.command,
                args=cfg.args,
                env=merged_env,
            )
            read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        elif cfg.transport == "sse":
            if not cfg.url:
                raise ValueError(f"sse server '{name}' requires 'url'")
            read, write = await self._exit_stack.enter_async_context(sse_client(cfg.url))
        else:
            raise ValueError(f"Unknown transport '{cfg.transport}' for server '{name}'")

        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return session

    async def shutdown(self) -> None:
        await self._exit_stack.aclose()
        self._sessions.clear()

    async def list_tools(self) -> list[dict]:
        """Return all tools in Ollama function-calling schema format."""
        result = []
        for server_name, session in self._sessions.items():
            try:
                tools_response = await session.list_tools()
                for tool in tools_response.tools:
                    namespaced = f"{server_name}__{tool.name}"
                    result.append({
                        "type": "function",
                        "function": {
                            "name": namespaced,
                            "description": tool.description or "",
                            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                        },
                    })
            except Exception as e:
                print(f"[mcp] Warning: could not list tools for '{server_name}': {e}")
        return result

    async def call_tool(self, namespaced_name: str, arguments: dict) -> str:
        """Dispatch tool call to the appropriate MCP server."""
        if "__" not in namespaced_name:
            raise ValueError(f"Tool name '{namespaced_name}' is not namespaced (expected 'server__tool')")

        server_name, tool_name = namespaced_name.split("__", 1)
        session = self._sessions.get(server_name)
        if session is None:
            raise ValueError(f"No connected MCP server named '{server_name}'")

        response = await session.call_tool(tool_name, arguments)

        # Flatten result content to string
        parts = []
        for item in response.content:
            if hasattr(item, "text"):
                parts.append(item.text)
            else:
                parts.append(str(item))
        return "\n".join(parts) if parts else ""

    @property
    def connected_servers(self) -> list[str]:
        return list(self._sessions.keys())

    async def server_tool_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for server_name, session in self._sessions.items():
            try:
                tools_response = await session.list_tools()
                counts[server_name] = len(tools_response.tools)
            except Exception:
                counts[server_name] = 0
        return counts
