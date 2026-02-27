from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from eip.agent.tools import AgentTools
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


@pytest.fixture
def tools(store: JsonStore) -> AgentTools:
    return AgentTools(store=store)


SAMPLE_HTML = """
<html><body>
<div class="items"><div class="item">
  <h3><a href="/page/1">Title One</a></h3>
  <p class="desc">Description one</p>
</div></div>
</body></html>
"""


async def test_fetch_page(httpx_mock: HTTPXMock, tools: AgentTools) -> None:
    httpx_mock.add_response(url="https://example.com", text="<html>Hello</html>")
    result = await tools.fetch_page("https://example.com")
    assert "Hello" in result["html"]
    assert result["status_code"] == 200


async def test_extract_with_selectors(
    httpx_mock: HTTPXMock, tools: AgentTools
) -> None:
    httpx_mock.add_response(url="https://example.com/page", text=SAMPLE_HTML)
    result = await tools.extract_with_selectors(
        url="https://example.com/page",
        selectors={
            "item_container": ".items .item",
            "title": "h3 a",
            "desc": ".desc",
            "link": "h3 a@href",
        },
        base_url="https://example.com",
    )
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "Title One"


def test_save_job(tools: AgentTools, store: JsonStore) -> None:
    job_def = {
        "name": "Test",
        "target_url": "https://example.com",
        "schedule": "0 * * * *",
    }
    extraction_config = {
        "strategy": "css_selector",
        "selectors": {"item_container": ".item", "title": "h3"},
        "base_url": "https://example.com",
    }
    result = tools.save_job(job_def, extraction_config)
    assert "job_id" in result
    # Verify persisted
    job = store.load("jobs", result["job_id"])
    assert job is not None
    assert job["name"] == "Test"
    config = store.load("configs", result["job_id"])
    assert config is not None


def test_tool_definitions(tools: AgentTools) -> None:
    defs = tools.get_tool_definitions()
    names = {d["name"] for d in defs}
    assert names == {"fetch_page", "extract_with_selectors", "save_job"}
