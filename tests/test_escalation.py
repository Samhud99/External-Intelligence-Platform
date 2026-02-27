import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from eip.agent.events import EventType
from eip.agent.setup_agent import SetupAgent
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


def _make_mock_provider(responses):
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=responses)
    return provider


@pytest.mark.asyncio
async def test_escalation_proposal_emitted_on_zero_items(store: JsonStore) -> None:
    """When CSS extraction finds 0 items, agent should propose escalation to Playwright."""
    provider = _make_mock_provider([
        {
            "content": [{"type": "tool_use", "id": "call_1", "name": "fetch_page", "input": {"url": "https://spa-site.com"}}],
            "stop_reason": "tool_use",
        },
        {
            "content": [{"type": "tool_use", "id": "call_2", "name": "extract_with_selectors", "input": {"url": "https://spa-site.com", "selectors": {"item_container": ".items", "title": "h2"}}}],
            "stop_reason": "tool_use",
        },
        {
            "content": [{"type": "text", "text": "CSS extraction found 0 items. This appears to be a JavaScript-rendered site. I recommend trying Playwright browser rendering."}],
            "stop_reason": "end_turn",
        },
    ])

    agent = SetupAgent(provider=provider, store=store)
    agent.tools.fetch_page = AsyncMock(
        return_value={"html": "<html><div id='app'></div></html>", "status_code": 200, "url": "https://spa-site.com"}
    )
    agent.tools.extract_with_selectors = AsyncMock(
        return_value={"items": [], "count": 0}
    )

    events = []
    input_queue = asyncio.Queue()

    async for event in agent.run_streaming("Monitor spa-site.com", input_queue):
        events.append(event)
        if event.type == EventType.PROPOSAL:
            break

    event_types = [e.type for e in events]
    assert EventType.STATUS in event_types
    assert EventType.EXTRACTION_TEST in event_types
    assert EventType.PROPOSAL in event_types


@pytest.mark.asyncio
async def test_memory_loaded_into_system_prompt(store: JsonStore) -> None:
    """When agent has memory for a domain, it should be included in the prompt."""
    from eip.agent.memory import AgentMemory
    memory = AgentMemory(store=store)
    memory.remember("example.com", "site_profile", "React SPA, needs Playwright")

    provider = _make_mock_provider([
        {
            "content": [{"type": "text", "text": "Based on my memory, I know this is a React SPA."}],
            "stop_reason": "end_turn",
        },
    ])

    agent = SetupAgent(provider=provider, store=store)
    input_queue = asyncio.Queue()

    events = []
    async for event in agent.run_streaming("Monitor https://example.com/news", input_queue):
        events.append(event)
        if event.type == EventType.PROPOSAL:
            break

    # Verify the system prompt included memory
    call_args = provider.complete.call_args_list[0]
    system = call_args.kwargs.get("system") or call_args[1].get("system") or call_args[0][0]
    assert "React SPA" in system or "memory" in system.lower()
