from __future__ import annotations

import asyncio
import json

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from privatepilotcli.config import AppConfig, CONFIG_DIR, save_config
from privatepilotcli.mcp_manager import MCPManager
from privatepilotcli.ollama_client import OllamaClient
from privatepilotcli.session import ConversationSession
from privatepilotcli.skills import load_skills, build_system_prompt

HISTORY_FILE = CONFIG_DIR / "history"

SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/model [name]": "Switch model or list available models",
    "/mcp": "Show connected MCP servers",
    "/tools": "List all available tools",
    "/reset": "Clear conversation history",
    "/skills": "Show loaded skills.md content",
    "/exit": "Exit (also Ctrl+D)",
}


class InteractiveREPL:
    def __init__(
        self,
        session: ConversationSession,
        mcp_manager: MCPManager,
        config: AppConfig,
        console: Console,
        ollama_client: OllamaClient,
    ) -> None:
        self._session = session
        self._mcp = mcp_manager
        self._config = config
        self._console = console
        self._ollama = ollama_client
        self._running = True

    def _make_prompt(self) -> HTML:
        tool_count = len(self._session._router.get_tool_schemas())
        tools_part = f" <ansicyan>[{tool_count} tools]</ansicyan>" if tool_count > 0 else ""
        return HTML(f"<ansigreen>[{self._config.model}]</ansigreen>{tools_part} <b>&gt;</b> ")

    async def run(self) -> None:
        self._console.print(
            Panel(
                f"[bold]ppilot[/bold] — Local AI powered by Ollama\n"
                f"Model: [cyan]{self._config.model}[/cyan]  |  "
                f"Type [bold]/help[/bold] for commands, Ctrl+D to exit",
                expand=False,
            )
        )

        ps: PromptSession = PromptSession(history=FileHistory(str(HISTORY_FILE)))

        while self._running:
            try:
                user_input = await ps.prompt_async(self._make_prompt)
            except EOFError:
                self._console.print("\n[dim]Goodbye.[/dim]")
                break
            except KeyboardInterrupt:
                continue

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.startswith("/"):
                await self._handle_slash(user_input)
            else:
                await self._stream_response(user_input)

    async def _handle_slash(self, command: str) -> None:
        parts = command.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            from rich.table import Table
            table = Table(show_header=False, box=None, padding=(0, 2))
            for name, desc in SLASH_COMMANDS.items():
                table.add_row(f"[bold cyan]{name}[/bold cyan]", desc)
            self._console.print(table)

        elif cmd == "/model":
            if arg:
                self._config.model = arg
                self._ollama.model = arg
                save_config(self._config)
                self._console.print(f"[green]Switched to model:[/green] {arg}")
            else:
                models = await self._ollama.list_models()
                if models:
                    self._console.print("[bold]Available models:[/bold]")
                    for m in models:
                        marker = " [cyan]←[/cyan]" if m == self._config.model else ""
                        self._console.print(f"  {m}{marker}")
                else:
                    self._console.print("[yellow]No models found. Is Ollama running?[/yellow]")

        elif cmd == "/mcp":
            servers = self._mcp.connected_servers
            if not servers:
                self._console.print("[dim]No MCP servers connected.[/dim]")
            else:
                counts = await self._mcp.server_tool_counts()
                from rich.table import Table
                table = Table(title="Connected MCP Servers", show_lines=False)
                table.add_column("Server")
                table.add_column("Tools", justify="right")
                for name in servers:
                    table.add_row(name, str(counts.get(name, 0)))
                self._console.print(table)

        elif cmd == "/tools":
            schemas = self._session._router.get_tool_schemas()
            if not schemas:
                self._console.print("[dim]No tools available.[/dim]")
            else:
                from rich.table import Table
                table = Table(title="Available Tools", show_lines=False)
                table.add_column("Tool")
                table.add_column("Description")
                for schema in schemas:
                    fn = schema.get("function", {})
                    table.add_row(fn.get("name", ""), fn.get("description", ""))
                self._console.print(table)

        elif cmd == "/reset":
            self._session.reset()
            self._console.print("[dim]Conversation cleared.[/dim]")

        elif cmd == "/skills":
            content = load_skills()
            if content:
                self._console.print(Markdown(content))
            else:
                self._console.print("[dim]No skills.md loaded.[/dim]")

        elif cmd == "/exit":
            self._running = False

        else:
            self._console.print(f"[yellow]Unknown command:[/yellow] {cmd}  (try /help)")

    async def _stream_response(self, user_input: str) -> None:
        sentinel = self._session.tool_call_sentinel
        accumulated = ""
        stream_task = None

        try:
            async for chunk in self._session.chat_stream(user_input):
                if chunk.startswith(sentinel):
                    # Tool call event
                    payload = json.loads(chunk[len(sentinel):])
                    if "args" in payload:
                        self._console.print(
                            f"\n[dim]  [tool] {payload['name']} "
                            f"{json.dumps(payload['args'])}[/dim]"
                        )
                    elif "result" in payload:
                        preview = payload["result"]
                        self._console.print(f"[dim]  [result] {preview[:120]}[/dim]")
                else:
                    accumulated += chunk
                    # Print chunk inline (streaming feel)
                    print(chunk, end="", flush=True)

        except KeyboardInterrupt:
            self._console.print("\n[dim][cancelled][/dim]")
            return

        if accumulated:
            # Re-render the full response as Markdown
            print()  # newline after raw stream
            self._console.print(Markdown(accumulated))
            self._console.print()
