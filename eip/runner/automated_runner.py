import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from eip.runner.change_detector import detect_changes
from eip.store.json_store import JsonStore


def extract_items(html: str, config: dict) -> List[Dict]:
    """Extract structured items from HTML using CSS selectors.

    Args:
        html: Raw HTML string to parse.
        config: Extraction configuration with keys:
            - strategy: Currently only "css_selector" is supported.
            - selectors: Mapping of field names to CSS selectors.
              Use "item_container" for the repeating element.
              Append ``@attr`` to a selector to extract an attribute
              instead of text (e.g. ``"a@href"``).
            - base_url: Base URL used to resolve relative links.

    Returns:
        A list of dicts, one per matched container.
    """
    soup = BeautifulSoup(html, "html.parser")
    selectors = config.get("selectors", {})
    base_url = config.get("base_url", "")

    container_selector = selectors.get("item_container", "")
    if not container_selector:
        return []

    containers = soup.select(container_selector)
    items: List[Dict] = []

    for container in containers:
        item: Dict = {}
        for field, selector in selectors.items():
            if field == "item_container":
                continue

            # Handle @attr syntax for extracting attributes (e.g. "a@href")
            attr: Optional[str] = None
            if "@" in selector:
                selector, attr = selector.rsplit("@", 1)

            el = container.select_one(selector)
            if el is None:
                continue

            if attr:
                value = el.get(attr, "")
            else:
                value = el.get_text(strip=True)

            # Resolve relative URLs for link fields
            if field == "link" and value and not value.startswith(("http://", "https://")):
                value = urljoin(base_url, value)

            # Store link fields as "url" in output
            if field == "link":
                item["url"] = value
            else:
                item[field] = value

        if item:
            items.append(item)

    return items


async def run_job(job_id: str, store: JsonStore) -> Dict:
    """Fetch a page, extract items, detect changes, and store results.

    Orchestrates the full automated pipeline:
    1. Load job and config from the store.
    2. Fetch the target URL.
    3. Extract items using CSS selectors.
    4. Detect changes against the previous run.
    5. Persist the result.

    Args:
        job_id: Identifier of the job to run.
        store: ``JsonStore`` instance used for persistence.

    Returns:
        A dict with run metadata and extracted items.
    """
    job = store.load("jobs", job_id)
    if job is None:
        return {"success": False, "error": f"Job {job_id} not found"}

    config = store.load("configs", job_id)
    if config is None:
        return {"success": False, "error": f"No extraction config for job {job_id}"}

    target_url = job["target_url"]
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(target_url)
            response.raise_for_status()
    except httpx.HTTPError as e:
        return {"success": False, "error": f"HTTP error: {e}", "run_id": run_id}

    items = extract_items(response.text, config)

    if not items:
        job["status"] = "needs_reagent"
        store.save("jobs", job_id, job)
        return {
            "success": False,
            "error": "Extraction returned no items — site may have changed",
            "run_id": run_id,
            "job_id": job_id,
        }

    # Load previous run for change detection
    previous_results = store.list(f"results/{job_id}")
    previous_items = None
    if previous_results:
        latest = sorted(previous_results, key=lambda r: r.get("ran_at", ""))[-1]
        previous_items = latest.get("items")

    items_with_changes = detect_changes(items, previous_items)
    new_count = sum(1 for i in items_with_changes if i.get("is_new"))

    result = {
        "run_id": run_id,
        "job_id": job_id,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "runner_type": "automated",
        "items": items_with_changes,
        "items_total": len(items_with_changes),
        "items_new": new_count,
        "success": True,
    }

    store.save(f"results/{job_id}", run_id, result)
    return result
