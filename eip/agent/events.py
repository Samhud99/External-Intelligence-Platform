import json
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(Enum):
    STATUS = "status"
    PAGE_FETCHED = "page_fetched"
    THINKING = "thinking"
    EXTRACTION_TEST = "extraction_test"
    PROPOSAL = "proposal"
    DONE = "done"
    ERROR = "error"
    ESCALATION_PROPOSAL = "escalation_proposal"
    FAILURE = "failure"


class AgentEvent:
    def __init__(
        self,
        type: EventType,
        message: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        content_length: Optional[int] = None,
        selectors: Optional[Dict] = None,
        sample_items: Optional[List[Dict]] = None,
        count: Optional[int] = None,
        job: Optional[Dict] = None,
        config: Optional[Dict] = None,
        sample_data: Optional[List[Dict]] = None,
        status: Optional[str] = None,
        current_tier: Optional[str] = None,
        proposed_tier: Optional[str] = None,
        failure_code: Optional[str] = None,
        user_message: Optional[str] = None,
        next_steps: Optional[List[Dict]] = None,
        technical_details: Optional[Dict] = None,
    ) -> None:
        self.type = type
        self.message = message
        self.url = url
        self.title = title
        self.content_length = content_length
        self.selectors = selectors
        self.sample_items = sample_items
        self.count = count
        self.job = job
        self.config = config
        self.sample_data = sample_data
        self.status = status
        self.current_tier = current_tier
        self.proposed_tier = proposed_tier
        self.failure_code = failure_code
        self.user_message = user_message
        self.next_steps = next_steps
        self.technical_details = technical_details

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": self.type.value}
        for key in [
            "message", "url", "title", "content_length",
            "selectors", "sample_items", "count",
            "job", "config", "sample_data", "status",
            "current_tier", "proposed_tier",
            "failure_code", "user_message", "next_steps", "technical_details",
        ]:
            val = getattr(self, key)
            if val is not None:
                d[key] = val
        return d

    def to_sse(self) -> str:
        return f"event: {self.type.value}\ndata: {json.dumps(self.to_dict(), default=str)}"
