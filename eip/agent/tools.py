import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from eip.runner.automated_runner import extract_items
from eip.store.json_store import JsonStore


class AgentTools:
    def __init__(self, store: JsonStore) -> None:
        self.store = store

    async def fetch_page(self, url: str) -> Dict:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            return {
                "html": response.text[:50000],  # Truncate for LLM context
                "status_code": response.status_code,
                "url": str(response.url),
            }

    async def extract_with_selectors(
        self, url: str, selectors: Dict, base_url: str = ""
    ) -> Dict:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            config = {
                "strategy": "css_selector",
                "selectors": selectors,
                "base_url": base_url or url,
            }
            items = extract_items(response.text, config)
            return {"items": items, "count": len(items)}

    def save_job(self, job_definition: Dict, extraction_config: Dict) -> Dict:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        job = {
            "id": job_id,
            "name": job_definition.get("name", "Unnamed job"),
            "target_url": job_definition["target_url"],
            "description": job_definition.get("description", ""),
            "schedule": job_definition.get("schedule", "0 * * * *"),
            "status": "active",
            "created_at": now,
        }
        self.store.save("jobs", job_id, job)

        config = {
            "job_id": job_id,
            **extraction_config,
            "created_at": now,
        }
        self.store.save("configs", job_id, config)

        return {"job_id": job_id, "job": job, "config": config}

    async def execute_tool(self, name: str, arguments: Dict) -> Any:
        if name == "fetch_page":
            return await self.fetch_page(**arguments)
        elif name == "extract_with_selectors":
            return await self.extract_with_selectors(**arguments)
        elif name == "save_job":
            return self.save_job(**arguments)
        else:
            return {"error": f"Unknown tool: {name}"}

    def get_tool_definitions(self) -> List[Dict]:
        return [
            {
                "name": "fetch_page",
                "description": (
                    "Fetch a web page and return its HTML content. "
                    "Use this to examine the structure of a target website."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to fetch",
                        },
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "extract_with_selectors",
                "description": (
                    "Test CSS selectors against a web page to extract structured "
                    "items. Use '@attr' syntax for attributes (e.g. 'a@href' to "
                    "get the href). The 'item_container' selector identifies "
                    "repeating items. Other selectors extract fields within each "
                    "item."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to extract from",
                        },
                        "selectors": {
                            "type": "object",
                            "description": (
                                "Map of field names to CSS selectors. Must include "
                                "'item_container'. Use '@attr' for attributes "
                                "(e.g. 'a@href')."
                            ),
                        },
                        "base_url": {
                            "type": "string",
                            "description": "Base URL for resolving relative links",
                        },
                    },
                    "required": ["url", "selectors"],
                },
            },
            {
                "name": "save_job",
                "description": (
                    "Save a monitoring job and its extraction config. Call this "
                    "after you have validated that the selectors extract the "
                    "right data."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "job_definition": {
                            "type": "object",
                            "description": (
                                "Job metadata: name, target_url, description, "
                                "schedule (cron expression)"
                            ),
                            "properties": {
                                "name": {"type": "string"},
                                "target_url": {"type": "string"},
                                "description": {"type": "string"},
                                "schedule": {"type": "string"},
                            },
                            "required": ["name", "target_url"],
                        },
                        "extraction_config": {
                            "type": "object",
                            "description": (
                                "Extraction strategy: strategy, selectors, base_url"
                            ),
                        },
                    },
                    "required": ["job_definition", "extraction_config"],
                },
            },
        ]
