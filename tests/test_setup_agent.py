import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from eip.agent.setup_agent import SetupAgent
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


def _make_mock_provider(responses):
    """Create a mock provider that returns a sequence of responses."""
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=responses)
    return provider


async def test_setup_agent_creates_job(store: JsonStore) -> None:
    """Simulate: agent fetches page, extracts, then saves job."""
    provider = _make_mock_provider([
        # First call: agent decides to fetch_page
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
        # Second call: agent tries extract_with_selectors
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
        # Third call: agent saves the job
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_3",
                    "name": "save_job",
                    "input": {
                        "job_definition": {
                            "name": "Monitor Example News",
                            "target_url": "https://example.com/news",
                            "description": "Track news articles",
                            "schedule": "0 */4 * * *",
                        },
                        "extraction_config": {
                            "strategy": "css_selector",
                            "selectors": {
                                "item_container": ".articles .article",
                                "title": "h2 a",
                                "link": "h2 a@href",
                            },
                            "base_url": "https://example.com",
                        },
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        # Fourth call: agent responds with summary
        {
            "content": [{"type": "text", "text": "Job created successfully."}],
            "stop_reason": "end_turn",
        },
    ])

    # Mock the agent tools' HTTP calls
    agent = SetupAgent(provider=provider, store=store)
    agent.tools.fetch_page = AsyncMock(
        return_value={"html": "<html>page html</html>", "status_code": 200, "url": "https://example.com/news"}
    )
    agent.tools.extract_with_selectors = AsyncMock(
        return_value={"items": [{"title": "Article 1", "url": "https://example.com/1"}], "count": 1}
    )

    result = await agent.run("Monitor example.com/news for new articles")

    assert result["success"] is True
    assert "job_id" in result
    # Job should be persisted
    jobs = store.list("jobs")
    assert len(jobs) == 1


async def test_setup_agent_max_turns_limit(store: JsonStore) -> None:
    """Agent should stop after max_turns to prevent infinite loops."""
    # Provider always returns tool calls — should hit limit
    infinite_tool_call = {
        "content": [
            {
                "type": "tool_use",
                "id": "call_1",
                "name": "fetch_page",
                "input": {"url": "https://example.com"},
            }
        ],
        "stop_reason": "tool_use",
    }
    provider = _make_mock_provider([infinite_tool_call] * 20)

    agent = SetupAgent(provider=provider, store=store, max_turns=3)
    agent.tools.fetch_page = AsyncMock(
        return_value={"html": "<html></html>", "status_code": 200, "url": "https://example.com"}
    )

    result = await agent.run("Monitor something")

    assert result["success"] is False
    assert "max turns" in result.get("error", "").lower()
