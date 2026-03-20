from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import ollama


@dataclass
class StreamChunk:
    content: str | None
    tool_calls: list[dict] | None
    done: bool


class OllamaClient:
    def __init__(self, host: str, model: str) -> None:
        self.host = host
        self.model = model
        self._client = ollama.AsyncClient(host=host)

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        kwargs: dict = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools

        async for chunk in await self._client.chat(**kwargs):
            msg = chunk.message
            content = msg.content if msg.content else None
            tool_calls = None
            if msg.tool_calls:
                tool_calls = []
                for tc in msg.tool_calls:
                    try:
                        tool_calls.append({
                            "function": {
                                "name": tc.function.name,
                                "arguments": dict(tc.function.arguments),
                            }
                        })
                    except Exception:
                        pass
            yield StreamChunk(
                content=content,
                tool_calls=tool_calls,
                done=chunk.done,
            )

    async def list_models(self) -> list[str]:
        try:
            response = await self._client.list()
            return [m.model for m in response.models]
        except Exception:
            return []

    async def health_check(self) -> bool:
        try:
            await self._client.list()
            return True
        except Exception:
            return False
