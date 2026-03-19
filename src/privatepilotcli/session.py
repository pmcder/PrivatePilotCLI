from __future__ import annotations

import json
from collections.abc import AsyncIterator

from privatepilotcli.ollama_client import OllamaClient
from privatepilotcli.tool_router import ToolRouter

_TOOL_CALL_SENTINEL = "\x00TOOL_CALL\x00"


class ConversationSession:
    def __init__(
        self,
        ollama_client: OllamaClient,
        tool_router: ToolRouter,
        system_prompt: str,
    ) -> None:
        self._ollama = ollama_client
        self._router = tool_router
        self._system_prompt = system_prompt
        self._messages: list[dict] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

    async def chat_stream(self, user_message: str) -> AsyncIterator[str]:
        """
        Agentic streaming loop. Yields text chunks as they arrive.
        Tool call events are yielded as sentinel-wrapped JSON for the REPL to handle.
        """
        self._messages.append({"role": "user", "content": user_message})
        tools = self._router.get_tool_schemas() or None

        while True:
            accumulated_content = ""
            accumulated_tool_calls: list[dict] = []

            async for chunk in self._ollama.stream_chat(self._messages, tools=tools):
                if chunk.content:
                    accumulated_content += chunk.content
                    yield chunk.content
                if chunk.tool_calls:
                    accumulated_tool_calls.extend(chunk.tool_calls)

            # Append assistant message to history
            assistant_msg: dict = {"role": "assistant"}
            if accumulated_tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        }
                    }
                    for tc in accumulated_tool_calls
                ]
                if accumulated_content:
                    assistant_msg["content"] = accumulated_content
            else:
                assistant_msg["content"] = accumulated_content

            self._messages.append(assistant_msg)

            if not accumulated_tool_calls:
                break

            # Execute tool calls and append results
            for tc in accumulated_tool_calls:
                fn = tc["function"]
                name = fn["name"]
                args = fn["arguments"]

                # Signal the REPL that a tool call is happening
                yield f"{_TOOL_CALL_SENTINEL}{json.dumps({'name': name, 'args': args})}"

                try:
                    result = await self._router.dispatch(name, args)
                except Exception as e:
                    result = f"Error calling tool '{name}': {e}"

                yield f"{_TOOL_CALL_SENTINEL}{json.dumps({'name': name, 'result': result[:200]})}"

                self._messages.append({
                    "role": "tool",
                    "content": result,
                })

    def reset(self) -> None:
        self._messages = []
        if self._system_prompt:
            self._messages.append({"role": "system", "content": self._system_prompt})

    def update_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt
        if self._messages and self._messages[0]["role"] == "system":
            self._messages[0]["content"] = prompt
        elif prompt:
            self._messages.insert(0, {"role": "system", "content": prompt})

    @property
    def message_count(self) -> int:
        return sum(1 for m in self._messages if m["role"] != "system")

    @property
    def tool_call_sentinel(self) -> str:
        return _TOOL_CALL_SENTINEL
