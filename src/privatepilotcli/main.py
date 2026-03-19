from __future__ import annotations

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console

from privatepilotcli.config import load_config, ensure_config_dir
from privatepilotcli.skills import load_skills, build_system_prompt
from privatepilotcli.ollama_client import OllamaClient
from privatepilotcli.mcp_manager import MCPManager
from privatepilotcli.tool_router import ToolRouter
from privatepilotcli.session import ConversationSession
from privatepilotcli.repl import InteractiveREPL

app = typer.Typer(
    help="ppilot — Local AI assistant powered by Ollama",
    add_completion=False,
)


@app.command()
def main(
    prompt: Optional[str] = typer.Argument(None, help="Run a single prompt and exit"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override default model"),
    no_skills: bool = typer.Option(False, "--no-skills", help="Skip loading skills.md"),
    mcp_config: Optional[str] = typer.Option(None, "--mcp-config", help="Path to config JSON with MCP servers"),
) -> None:
    """Start interactive REPL, or run a single prompt if provided."""
    asyncio.run(_async_main(prompt=prompt, model=model, no_skills=no_skills, mcp_config=mcp_config))


async def _async_main(
    prompt: str | None,
    model: str | None,
    no_skills: bool,
    mcp_config: str | None,
) -> None:
    console = Console()
    ensure_config_dir()

    # Load config
    config = load_config(mcp_config_path=mcp_config)
    if model:
        config.model = model

    # Check Ollama connectivity
    ollama_client = OllamaClient(host=config.ollama_host, model=config.model)
    if not await ollama_client.health_check():
        console.print(
            f"[red]Error:[/red] Cannot reach Ollama at [bold]{config.ollama_host}[/bold]\n"
            "Make sure Ollama is running: [cyan]ollama serve[/cyan]"
        )
        sys.exit(1)

    # Warn if configured model is not available
    available_models = await ollama_client.list_models()
    if available_models and config.model not in available_models:
        console.print(
            f"[yellow]Warning:[/yellow] Model [bold]{config.model}[/bold] not found. "
            f"Available: {', '.join(available_models)}\n"
            "Use [bold]/model <name>[/bold] to switch."
        )
        config.model = available_models[0]
        ollama_client.model = config.model

    # Load skills
    system_prompt = ""
    if not no_skills:
        skills_content = load_skills()
        system_prompt = build_system_prompt(skills_content)

    # Start MCP servers
    mcp_manager = MCPManager(config.mcp_servers)
    await mcp_manager.startup()

    # Build tool router and load schemas
    tool_router = ToolRouter(mcp_manager)
    await tool_router.refresh_schemas()

    # Create conversation session
    session = ConversationSession(
        ollama_client=ollama_client,
        tool_router=tool_router,
        system_prompt=system_prompt,
    )

    try:
        if prompt:
            # One-shot mode
            async for chunk in session.chat_stream(prompt):
                if not chunk.startswith(session.tool_call_sentinel):
                    print(chunk, end="", flush=True)
            print()
        else:
            # Interactive REPL
            repl = InteractiveREPL(
                session=session,
                mcp_manager=mcp_manager,
                config=config,
                console=console,
                ollama_client=ollama_client,
            )
            await repl.run()
    finally:
        await mcp_manager.shutdown()
