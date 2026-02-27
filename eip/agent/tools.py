import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from eip.agent.browser import BrowserTool
from eip.agent.memory import AgentMemory
from eip.runner.automated_runner import extract_items
from eip.store.json_store import JsonStore


class AgentTools:
    def __init__(self, store: JsonStore) -> None:
        self.store = store
        self.memory = AgentMemory(store=store)
        self.browser = BrowserTool()

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

    async def browse_page(
        self, url: str, actions: Optional[List[Dict]] = None
    ) -> Dict:
        return await self.browser.browse_page(url=url, actions=actions)

    def remember(self, domain: str, key: str, value: str) -> Dict:
        self.memory.remember(domain=domain, key=key, value=value)
        return {"status": "remembered", "domain": domain, "key": key}

    def recall(self, domain: str) -> Dict:
        entries = self.memory.recall(domain=domain)
        return {"domain": domain, "entries": entries}

    async def execute_tool(self, name: str, arguments: Dict) -> Any:
        if name == "fetch_page":
            return await self.fetch_page(**arguments)
        elif name == "extract_with_selectors":
            return await self.extract_with_selectors(**arguments)
        elif name == "save_job":
            return self.save_job(**arguments)
        elif name == "browse_page":
            return await self.browse_page(**arguments)
        elif name == "remember":
            return self.remember(**arguments)
        elif name == "recall":
            return self.recall(**arguments)
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
            {
                "name": "browse_page",
                "description": (
                    "Open a URL in a headless browser with full JavaScript "
                    "rendering. Use this when fetch_page fails to capture "
                    "dynamic content. Optionally supply a list of actions "
                    "(click, fill, scroll, wait, wait_for_selector) to "
                    "interact with the page before capturing its HTML."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to browse",
                        },
                        "actions": {
                            "type": "array",
                            "description": (
                                "Optional list of browser actions to execute "
                                "before capturing the page"
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "enum": [
                                            "click",
                                            "fill",
                                            "scroll",
                                            "wait",
                                            "wait_for_selector",
                                        ],
                                    },
                                    "selector": {"type": "string"},
                                    "value": {"type": "string"},
                                },
                                "required": ["action"],
                            },
                        },
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "remember",
                "description": (
                    "Store a piece of knowledge about a domain for future "
                    "use. Use this to save site profiles, login patterns, "
                    "or selector strategies you have discovered."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "The domain this knowledge relates to (e.g. 'example.com')",
                        },
                        "key": {
                            "type": "string",
                            "description": "A short label for this piece of knowledge (e.g. 'site_profile')",
                        },
                        "value": {
                            "type": "string",
                            "description": "The knowledge to store",
                        },
                    },
                    "required": ["domain", "key", "value"],
                },
            },
            {
                "name": "recall",
                "description": (
                    "Retrieve all stored knowledge about a domain. Use this "
                    "at the start of a task to recall what you previously "
                    "learned about a website."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "The domain to recall knowledge for (e.g. 'example.com')",
                        },
                    },
                    "required": ["domain"],
                },
            },
        ]
