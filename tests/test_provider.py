import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eip.agent.provider import ClaudeProvider, ModelProvider


def test_claude_provider_implements_protocol() -> None:
    provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
    assert isinstance(provider, ModelProvider)


async def test_claude_provider_complete_calls_api() -> None:
    provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Hello")]
    mock_response.stop_reason = "end_turn"
    mock_response.model = "claude-sonnet-4-6"

    with patch.object(
        provider.client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        result = await provider.complete(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert result["stop_reason"] == "end_turn"
        mock_create.assert_called_once()
