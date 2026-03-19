from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

CONFIG_DIR = Path.home() / ".privatepilotcli"
CONFIG_FILE = CONFIG_DIR / "config.json"
GLOBAL_SKILLS_FILE = CONFIG_DIR / "skills.md"

DEFAULT_SKILLS_CONTENT = """\
# System Instructions

You are a helpful, knowledgeable assistant. Be concise and accurate.
When writing code, prefer modern idiomatic Python 3.14+.
"""

DEFAULT_CONFIG_CONTENT = {
    "model": "llama3.2",
    "ollama_host": "http://localhost:11434",
    "stream": True,
    "mcp_servers": {},
}


@dataclass
class MCPServerConfig:
    transport: str  # "stdio" | "sse"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "MCPServerConfig":
        return cls(
            transport=d.get("transport", "stdio"),
            command=d.get("command"),
            args=d.get("args", []),
            env=d.get("env", {}),
            url=d.get("url"),
        )


@dataclass
class AppConfig:
    model: str = "llama3.2"
    ollama_host: str = "http://localhost:11434"
    stream: bool = True
    mcp_servers: dict[str, MCPServerConfig] = field(default_factory=dict)


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG_CONTENT, indent=2))
    if not GLOBAL_SKILLS_FILE.exists():
        GLOBAL_SKILLS_FILE.write_text(DEFAULT_SKILLS_CONTENT)


def load_config(mcp_config_path: str | None = None) -> AppConfig:
    ensure_config_dir()

    source_path = Path(mcp_config_path) if mcp_config_path else CONFIG_FILE
    if source_path.exists():
        try:
            data = json.loads(source_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    servers: dict[str, MCPServerConfig] = {}
    for name, srv in data.get("mcp_servers", {}).items():
        servers[name] = MCPServerConfig.from_dict(srv)

    return AppConfig(
        model=data.get("model", "llama3.2"),
        ollama_host=data.get("ollama_host", "http://localhost:11434"),
        stream=data.get("stream", True),
        mcp_servers=servers,
    )


def save_config(config: AppConfig) -> None:
    ensure_config_dir()
    data: dict = {
        "model": config.model,
        "ollama_host": config.ollama_host,
        "stream": config.stream,
        "mcp_servers": {
            name: {
                "transport": srv.transport,
                **({"command": srv.command} if srv.command else {}),
                **({"args": srv.args} if srv.args else {}),
                **({"env": srv.env} if srv.env else {}),
                **({"url": srv.url} if srv.url else {}),
            }
            for name, srv in config.mcp_servers.items()
        },
    }
    CONFIG_FILE.write_text(json.dumps(data, indent=2))
