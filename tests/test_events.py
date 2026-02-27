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


def test_escalation_proposal_event() -> None:
    event = AgentEvent(
        type=EventType.ESCALATION_PROPOSAL,
        message="CSS selectors found 0 items. This site loads content with JavaScript.",
        current_tier="css",
        proposed_tier="playwright",
    )
    d = event.to_dict()
    assert d["type"] == "escalation_proposal"
    assert d["current_tier"] == "css"
    assert d["proposed_tier"] == "playwright"


def test_failure_event() -> None:
    event = AgentEvent(
        type=EventType.FAILURE,
        failure_code="login_required",
        user_message="This page requires authentication to access.",
        next_steps=[
            {"type": "provide_credentials", "label": "Provide login credentials"},
            {"type": "change_url", "label": "Try a different page"},
        ],
        technical_details={"http_status": 302, "redirect_url": "https://example.com/login"},
    )
    d = event.to_dict()
    assert d["type"] == "failure"
    assert d["failure_code"] == "login_required"
    assert len(d["next_steps"]) == 2
    assert d["technical_details"]["http_status"] == 302


def test_all_event_types_v3() -> None:
    expected = {
        "status", "page_fetched", "thinking", "extraction_test",
        "proposal", "done", "error", "escalation_proposal", "failure",
    }
    actual = {e.value for e in EventType}
    assert expected == actual
