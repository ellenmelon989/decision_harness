"""Research tool — grounds agent claims with synthesized facts (ROADMAP §7.5).

For the hackathon this uses an LLM to generate plausible, relevant research
rather than hitting a real search API. Replace `_llm_research` with a Tavily
or Firecrawl call once you have the key.
"""
from __future__ import annotations


async def call_tool(tool: str, args: dict, session_question: str = "") -> str:
    """Dispatch a tool call from an agent turn. Returns the result string."""
    if tool == "research":
        return await _llm_research(args, session_question)
    if tool == "company_data":
        return _company_data(args)
    return f"[unknown tool: {tool}]"


async def _llm_research(args: dict, question: str) -> str:
    import json
    from openai import AsyncOpenAI
    from ..config import get_settings

    query = args.get("query") or args.get("question") or json.dumps(args)
    s = get_settings()
    client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=s.groq_api_key)
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a research assistant. Return 3-4 concise, factual bullet points "
                    "relevant to the query. Be specific — cite numbers, dates, or named examples "
                    "where possible. Do not editorialize."
                ),
            },
            {
                "role": "user",
                "content": f"Decision context: {question}\n\nResearch query: {query}",
            },
        ],
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


def _company_data(args: dict) -> str:
    metric = args.get("metric", "general")
    return (
        f"[Company Data] {metric}: "
        "Revenue $4.2M ARR (+180% YoY), Burn rate $320K/mo, "
        "Runway 14 months, Team 12 FTE, NPS 67, Churn 2.1%/mo"
    )
