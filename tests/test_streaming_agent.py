import asyncio
import json
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
async def test_run_streaming_emits_events(store: JsonStore) -> None:
    provider = _make_mock_provider([
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "fetch_page",
                    "input": {"url": "https://example.com/news"},
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_2",
                    "name": "extract_with_selectors",
                    "input": {
                        "url": "https://example.com/news",
                        "selectors": {
                            "item_container": ".articles .article",
                            "title": "h2 a",
                            "link": "h2 a@href",
                        },
                        "base_url": "https://example.com",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "content": [{"type": "text", "text": "I found 2 articles. Here is my proposed configuration."}],
            "stop_reason": "end_turn",
        },
    ])

    agent = SetupAgent(provider=provider, store=store)
    agent.tools.fetch_page = AsyncMock(
        return_value={"html": "<html>page</html>", "status_code": 200, "url": "https://example.com/news"}
    )
    agent.tools.extract_with_selectors = AsyncMock(
        return_value={
            "items": [{"title": "Article 1", "url": "https://example.com/1"}],
            "count": 1,
        }
    )

    events = []
    input_queue = asyncio.Queue()

    async for event in agent.run_streaming("Monitor example.com", input_queue):
        events.append(event)
        # Break after proposal to avoid blocking on input_queue
        if event.type == EventType.PROPOSAL:
            break

    event_types = [e.type for e in events]
    assert EventType.STATUS in event_types
    assert EventType.PROPOSAL in event_types


@pytest.mark.asyncio
async def test_run_streaming_waits_for_confirmation(store: JsonStore) -> None:
    provider = _make_mock_provider([
        {
            "content": [{"type": "text", "text": "Here is my proposal."}],
            "stop_reason": "end_turn",
        },
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "save_job",
                    "input": {
                        "job_definition": {
                            "name": "Test",
                            "target_url": "https://example.com",
                        },
                        "extraction_config": {
                            "strategy": "css_selector",
                            "selectors": {"item_container": ".item", "title": "h2"},
                            "base_url": "https://example.com",
                        },
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "content": [{"type": "text", "text": "Job saved."}],
            "stop_reason": "end_turn",
        },
    ])

    agent = SetupAgent(provider=provider, store=store)
    input_queue = asyncio.Queue()

    # Pre-load confirmation so the agent doesn't block forever
    await input_queue.put({"type": "confirm"})

    events = []
    async for event in agent.run_streaming("Monitor example.com", input_queue):
        events.append(event)

    event_types = [e.type for e in events]
    assert EventType.PROPOSAL in event_types
    assert EventType.DONE in event_types
    # Job should be saved
    jobs = store.list("jobs")
    assert len(jobs) == 1
