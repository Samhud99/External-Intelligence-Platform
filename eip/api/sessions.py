import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from eip.store.json_store import JsonStore


class SessionStatus(Enum):
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class SessionManager:
    def __init__(self, store: JsonStore) -> None:
        self.store = store
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        self._event_queues: Dict[str, asyncio.Queue] = {}

    def create(self, request: str) -> str:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = {
            "session_id": session_id,
            "request": request,
            "status": SessionStatus.RUNNING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._queues[session_id] = asyncio.Queue()
        self._event_queues[session_id] = asyncio.Queue()
        return session_id

    def get(self, session_id: str) -> Optional[Dict]:
        return self._sessions.get(session_id)

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["status"] = status.value

    def get_input_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        return self._queues.get(session_id)

    def get_event_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        return self._event_queues.get(session_id)

    def send_message(self, session_id: str, message: Dict) -> None:
        queue = self._queues.get(session_id)
        if queue:
            queue.put_nowait(message)

    def send_event(self, session_id: str, event: Any) -> None:
        queue = self._event_queues.get(session_id)
        if queue:
            queue.put_nowait(event)

    def cancel(self, session_id: str) -> None:
        self.update_status(session_id, SessionStatus.CANCELLED)
        queue = self._queues.get(session_id)
        if queue:
            queue.put_nowait({"type": "reject"})

    def list_sessions(self) -> List[Dict]:
        return list(self._sessions.values())
