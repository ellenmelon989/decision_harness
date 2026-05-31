"""Tool executor for agent `tool_call`s (ROADMAP §7.5).

Dispatches to real implementations in mcp_servers/. Falls back to stubs
if keys are missing so the pipeline always completes.
"""
from __future__ import annotations

TOOLS = ["research", "company_data"]


async def execute_tool(tool: str, args: dict, question: str = "") -> dict:
    try:
        from ..mcp_servers.research import call_tool
        result = await call_tool(tool, args, question)
        return {"tool": tool, "result": result}
    except Exception as exc:
        return {"tool": tool, "result": f"[{tool} unavailable: {exc}]"}
