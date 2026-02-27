import json
import logging
from typing import Any, Dict, List, Optional

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
