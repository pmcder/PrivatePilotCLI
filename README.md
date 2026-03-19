# ppilot

A local AI assistant CLI powered by [Ollama](https://ollama.com) with [Model Context Protocol (MCP)](https://modelcontextprotocol.io) tool support and a customizable skills system.

## Features

- **Interactive REPL** — persistent conversation history, slash commands, streaming responses
- **One-shot mode** — pipe prompts directly from the command line
- **MCP tool support** — connect any MCP-compatible server via stdio or SSE transport
- **Skills system** — customize AI behavior with plain Markdown files, no code changes required
- **Agentic loop** — automatically executes tool calls and feeds results back to the model

## Requirements

- Python 3.14+
- [Ollama](https://ollama.com) running locally (or accessible over the network)

## Installation

```bash
pip install -e .
```

This installs the `ppilot` command.

## Quickstart

```bash
# Start an interactive session
ppilot

# One-shot prompt
ppilot "Summarize the key ideas in REST API design"

# Use a specific model
ppilot --model mistral "Write a Python decorator that retries on failure"

# Connect MCP servers
ppilot --mcp-config ./mcp-servers.json
```

## Configuration

On first run, `ppilot` creates `~/.privatepilotcli/config.json` with defaults:

```json
{
  "model": "llama3.2",
  "ollama_host": "http://localhost:11434",
  "stream": true,
  "mcp_servers": {}
}
```

| Field | Default | Description |
|---|---|---|
| `model` | `llama3.2` | Default Ollama model |
| `ollama_host` | `http://localhost:11434` | Ollama server URL |
| `stream` | `true` | Stream responses token-by-token |
| `mcp_servers` | `{}` | MCP server definitions (see below) |

### MCP Servers

Add MCP servers to `~/.privatepilotcli/config.json` or pass a separate file with `--mcp-config`:

```json
{
  "mcp_servers": {
    "filesystem": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "remote-tools": {
      "transport": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

Tools from each server are namespaced as `servername__toolname` to prevent collisions.

## CLI Options

```
ppilot [OPTIONS] [PROMPT]
```

| Option | Short | Description |
|---|---|---|
| `PROMPT` | — | Run a single prompt and exit |
| `--model NAME` | `-m` | Override the configured default model |
| `--no-skills` | — | Disable skills.md loading |
| `--mcp-config PATH` | — | Path to an MCP servers config JSON file |

## REPL Commands

| Command | Description |
|---|---|
| `/help` | List all available commands |
| `/model [NAME]` | Switch model or list available models |
| `/mcp` | Show connected MCP servers and tool counts |
| `/tools` | List all tools available from connected servers |
| `/skills` | Display the loaded skills.md content |
| `/reset` | Clear conversation history |
| `/exit` | Exit (also `Ctrl+D`) |

**Keyboard shortcuts:**
- `Ctrl+C` — Cancel the current response and stay in the REPL
- `Ctrl+D` — Exit

## Skills

Skills let you customize the AI's behavior using a Markdown file — no code changes needed.

`ppilot` loads skills from (in priority order):
1. `./skills.md` in the current working directory
2. `~/.privatepilotcli/skills.md` (global default)

### Format

```markdown
# System Instructions

You are a helpful assistant. Be concise and accurate.

---

## Skill: code-review

**Description:** Review code for bugs, style, and performance issues

**Triggers:** review, audit, check this code

**Instructions:** When reviewing code, look for off-by-one errors, missing error
handling, inefficient algorithms, and deviations from language idioms. Structure
feedback as: Issues Found, Suggestions, and a Summary rating.
```

Content before the first `## Skill:` heading becomes the base system prompt. Each skill's instructions are appended to it automatically.

Disable skills for a session with `--no-skills`.

## File Locations

| Path | Purpose |
|---|---|
| `~/.privatepilotcli/config.json` | Application configuration |
| `~/.privatepilotcli/skills.md` | Global skills and system prompt |
| `~/.privatepilotcli/history` | REPL input history |
| `./skills.md` | Local skills override (current directory) |

## Architecture

```
src/privatepilotcli/
├── main.py           # CLI entry point (Typer)
├── config.py         # Config loading/saving
├── skills.py         # Skills.md parser and system prompt builder
├── ollama_client.py  # Async Ollama API wrapper
├── mcp_manager.py    # MCP server lifecycle management
├── tool_router.py    # Routes tool calls to MCP servers
├── session.py        # Agentic conversation loop
└── repl.py           # Interactive REPL (prompt_toolkit + rich)
```

The agentic loop in `session.py` streams from Ollama, detects tool calls, dispatches them through the MCP manager, and feeds results back — repeating until the model produces a final response with no further tool calls.

## License

MIT
