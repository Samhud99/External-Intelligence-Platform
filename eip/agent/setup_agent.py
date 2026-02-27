import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from eip.agent.events import AgentEvent, EventType
from eip.agent.provider import ModelProvider
from eip.agent.tools import AgentTools
from eip.store.json_store import JsonStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an AI agent that sets up web monitoring jobs. The user will describe what external \
information they want to monitor. Your job is to:

1. Fetch the target web page to understand its structure.
2. Identify the right CSS selectors to extract the information the user wants.
3. Test your selectors by calling extract_with_selectors to verify they work.
4. If the extraction looks good, save the job using save_job.
5. If the extraction doesn't look right, try different selectors and test again.

Be methodical: fetch the page first, study the HTML structure, pick selectors, \
test them, iterate if needed, then save.

For the schedule, choose an appropriate cron expression based on the content type:
- News/media releases: every 4 hours (0 */4 * * *)
- Market data: every 15 minutes (*/15 * * * *)
- Research/publications: daily (0 9 * * *)
- General monitoring: hourly (0 * * * *)
"""


class SetupAgent:
    def __init__(
        self,
        provider: ModelProvider,
        store: JsonStore,
        max_turns: int = 10,
    ) -> None:
        self.provider = provider
        self.store = store
        self.tools = AgentTools(store=store)
        self.max_turns = max_turns

    async def run(self, user_request: str) -> Dict:
        messages: List[Dict] = [
            {"role": "user", "content": user_request},
        ]
        tool_defs = self.tools.get_tool_definitions()
        job_id = None

        for turn in range(self.max_turns):
            response = await self.provider.complete(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=tool_defs,
            )

            # Check if the model wants to use a tool
            if response["stop_reason"] == "tool_use":
                tool_results = []
                for block in response["content"]:
                    if block["type"] == "tool_use":
                        tool_name = block["name"]
                        tool_input = block["input"]
                        logger.info(f"Agent calling tool: {tool_name}")

                        tool_result = await self.tools.execute_tool(
                            tool_name, tool_input
                        )

                        # Track if save_job was called
                        if tool_name == "save_job" and "job_id" in tool_result:
                            job_id = tool_result["job_id"]

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": json.dumps(tool_result, default=str),
                            }
                        )

                # Add assistant message and tool results
                messages.append({"role": "assistant", "content": response["content"]})
                messages.append({"role": "user", "content": tool_results})

            elif response["stop_reason"] == "end_turn":
                # Agent is done
                text = ""
                for block in response["content"]:
                    if block["type"] == "text":
                        text += block.get("text", "")

                if job_id:
                    return {
                        "success": True,
                        "job_id": job_id,
                        "summary": text,
                    }
                else:
                    return {
                        "success": False,
                        "error": "Agent finished without creating a job",
                        "summary": text,
                    }
            else:
                return {
                    "success": False,
                    "error": f"Unexpected stop reason: {response['stop_reason']}",
                }

        return {
            "success": False,
            "error": f"Agent exceeded max turns ({self.max_turns})",
        }

    async def run_streaming(
        self, user_request: str, input_queue: asyncio.Queue
    ) -> AsyncIterator[AgentEvent]:
        """Yield AgentEvents as the agent works. Pauses at proposal for user input."""
        messages: List[Dict] = [
            {"role": "user", "content": user_request},
        ]
        tool_defs = self.tools.get_tool_definitions()
        job_id = None
        last_extraction = None
        last_selectors = None

        for turn in range(self.max_turns):
            response = await self.provider.complete(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=tool_defs,
            )

            if response["stop_reason"] == "tool_use":
                tool_results = []
                for block in response["content"]:
                    if block["type"] == "tool_use":
                        tool_name = block["name"]
                        tool_input = block["input"]

                        # Emit status event before tool execution
                        if tool_name == "fetch_page":
                            yield AgentEvent(
                                type=EventType.STATUS,
                                message=f"Fetching {tool_input.get('url', '')}...",
                            )
                        elif tool_name == "extract_with_selectors":
                            yield AgentEvent(
                                type=EventType.STATUS,
                                message="Testing extraction selectors...",
                            )
                        elif tool_name == "save_job":
                            yield AgentEvent(
                                type=EventType.STATUS,
                                message="Saving monitoring job...",
                            )

                        tool_result = await self.tools.execute_tool(
                            tool_name, tool_input
                        )

                        # Emit events after tool execution
                        if tool_name == "fetch_page":
                            yield AgentEvent(
                                type=EventType.PAGE_FETCHED,
                                url=tool_result.get("url", ""),
                                content_length=len(tool_result.get("html", "")),
                            )
                        elif tool_name == "extract_with_selectors":
                            last_extraction = tool_result
                            last_selectors = tool_input.get("selectors", {})
                            items = tool_result.get("items", [])
                            yield AgentEvent(
                                type=EventType.EXTRACTION_TEST,
                                selectors=last_selectors,
                                sample_items=items[:5],
                                count=tool_result.get("count", 0),
                            )
                        elif tool_name == "save_job" and "job_id" in tool_result:
                            job_id = tool_result["job_id"]

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": json.dumps(tool_result, default=str),
                            }
                        )

                messages.append({"role": "assistant", "content": response["content"]})
                messages.append({"role": "user", "content": tool_results})

            elif response["stop_reason"] == "end_turn":
                text = ""
                for block in response["content"]:
                    if block["type"] == "text":
                        text += block.get("text", "")

                if job_id:
                    # Job was saved -- we're done
                    yield AgentEvent(
                        type=EventType.DONE,
                        status="completed",
                        message=text,
                    )
                    return

                # Agent finished a round without saving -- present proposal
                proposal_job = {
                    "target_url": user_request,
                    "description": text,
                }
                proposal_config = {}  # type: Dict[str, Any]
                if last_selectors:
                    proposal_config["selectors"] = last_selectors
                sample = []  # type: List[Dict]
                if last_extraction:
                    sample = last_extraction.get("items", [])[:5]

                yield AgentEvent(
                    type=EventType.PROPOSAL,
                    job=proposal_job,
                    config=proposal_config,
                    sample_data=sample,
                    message=text,
                )

                # Wait for user input
                try:
                    user_input = await asyncio.wait_for(
                        input_queue.get(), timeout=300
                    )
                except asyncio.TimeoutError:
                    yield AgentEvent(
                        type=EventType.ERROR,
                        message="Session timed out waiting for input",
                    )
                    return

                if user_input.get("type") == "confirm":
                    # Tell agent to save the job
                    messages.append(
                        {"role": "assistant", "content": response["content"]}
                    )
                    messages.append({
                        "role": "user",
                        "content": (
                            "The user has approved this configuration. "
                            "Please save the job now using save_job."
                        ),
                    })
                elif user_input.get("type") == "reject":
                    yield AgentEvent(
                        type=EventType.DONE,
                        status="cancelled",
                        message="User rejected the proposal",
                    )
                    return
                elif user_input.get("type") == "message":
                    # User refinement
                    messages.append(
                        {"role": "assistant", "content": response["content"]}
                    )
                    messages.append({
                        "role": "user",
                        "content": user_input.get("content", ""),
                    })
                    yield AgentEvent(
                        type=EventType.STATUS,
                        message="Processing your feedback...",
                    )
            else:
                yield AgentEvent(
                    type=EventType.ERROR,
                    message=f"Unexpected stop reason: {response['stop_reason']}",
                )
                return

        yield AgentEvent(
            type=EventType.ERROR,
            message=f"Agent exceeded max turns ({self.max_turns})",
        )
