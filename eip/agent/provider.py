from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import anthropic


@runtime_checkable
class ModelProvider(Protocol):
    async def complete(
        self,
        system: str,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
    ) -> Dict: ...


class ClaudeProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def complete(
        self,
        system: str,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
    ) -> Dict:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self.client.messages.create(**kwargs)

        return {
            "content": [
                {"type": block.type, "text": getattr(block, "text", None)}
                if block.type == "text"
                else {
                    "type": block.type,
                    "id": getattr(block, "id", None),
                    "name": getattr(block, "name", None),
                    "input": getattr(block, "input", None),
                }
                for block in response.content
            ],
            "stop_reason": response.stop_reason,
            "model": response.model,
        }
