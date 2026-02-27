import json
from pathlib import Path
from typing import List, Optional


class JsonStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def _collection_dir(self, collection: str) -> Path:
        d = self.base_dir / collection
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, collection: str, item_id: str, data: dict) -> None:
        path = self._collection_dir(collection) / f"{item_id}.json"
        path.write_text(json.dumps(data, indent=2, default=str))

    def load(self, collection: str, item_id: str) -> Optional[dict]:
        path = self._collection_dir(collection) / f"{item_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list(self, collection: str) -> List[dict]:
        d = self._collection_dir(collection)
        items = []
        for path in sorted(d.glob("*.json")):
            items.append(json.loads(path.read_text()))
        return items

    def delete(self, collection: str, item_id: str) -> None:
        path = self._collection_dir(collection) / f"{item_id}.json"
        if path.exists():
            path.unlink()
