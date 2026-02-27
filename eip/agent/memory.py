from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

from eip.store.json_store import JsonStore


class AgentMemory:
    """Persistent agent memory scoped by domain."""

    def __init__(self, store: JsonStore) -> None:
        self.store = store

    def _domain_id(self, domain: str) -> str:
        return domain.replace(".", "_").replace("/", "_")

    def remember(self, domain: str, key: str, value: str) -> None:
        domain_id = self._domain_id(domain)
        existing = self.store.load("memory", domain_id)
        if existing is None:
            existing = {"domain": domain, "entries": []}
        existing["entries"].append({
            "key": key,
            "value": value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        self.store.save("memory", domain_id, existing)

    def recall(self, domain: str) -> List[Dict]:
        domain_id = self._domain_id(domain)
        data = self.store.load("memory", domain_id)
        if data is None:
            return []
        return data.get("entries", [])

    def recall_as_text(self, domain: str) -> str:
        entries = self.recall(domain)
        if not entries:
            return ""
        lines = [f"- {e['key']}: {e['value']}" for e in entries]
        return "\n".join(lines)

    @staticmethod
    def extract_domain(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc or url
