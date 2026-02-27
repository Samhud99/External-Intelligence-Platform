import hashlib
from typing import Dict, List, Optional


def _item_key(item: Dict) -> str:
    if "url" in item and item["url"]:
        return item["url"]
    title = item.get("title", "")
    return hashlib.sha256(title.encode()).hexdigest()


def detect_changes(
    current: List[Dict], previous: Optional[List[Dict]]
) -> List[Dict]:
    if previous is None:
        return [{**item, "is_new": True} for item in current]

    previous_keys = {_item_key(item) for item in previous}
    result = []
    for item in current:
        key = _item_key(item)
        result.append({**item, "is_new": key not in previous_keys})
    return result
