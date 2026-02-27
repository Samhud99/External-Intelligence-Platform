import json

from eip.agent.events import AgentEvent, EventType


def test_status_event_to_dict() -> None:
    event = AgentEvent(type=EventType.STATUS, message="Fetching page...")
    d = event.to_dict()
    assert d["type"] == "status"
    assert d["message"] == "Fetching page..."


def test_extraction_test_event_to_dict() -> None:
    event = AgentEvent(
        type=EventType.EXTRACTION_TEST,
        selectors={"item_container": ".article", "title": "h2"},
        sample_items=[{"title": "Test"}],
        count=1,
    )
    d = event.to_dict()
    assert d["type"] == "extraction_test"
    assert d["count"] == 1
    assert len(d["sample_items"]) == 1


def test_proposal_event_to_dict() -> None:
    event = AgentEvent(
        type=EventType.PROPOSAL,
        job={"name": "Test Job", "target_url": "https://example.com"},
        config={"strategy": "css_selector", "selectors": {}},
        sample_data=[{"title": "Article 1"}],
    )
    d = event.to_dict()
    assert d["type"] == "proposal"
    assert d["job"]["name"] == "Test Job"
    assert len(d["sample_data"]) == 1


def test_event_to_sse_format() -> None:
    event = AgentEvent(type=EventType.STATUS, message="Working...")
    sse = event.to_sse()
    assert sse.startswith("event: status\ndata: ")
    payload = json.loads(sse.split("data: ", 1)[1])
    assert payload["message"] == "Working..."


def test_all_event_types_exist() -> None:
    expected = {"status", "page_fetched", "thinking", "extraction_test", "proposal", "done", "error"}
    actual = {e.value for e in EventType}
    assert expected == actual
