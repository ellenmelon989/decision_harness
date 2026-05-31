"""AI org-builder (ROADMAP §9.4).

`generate_org_agents` takes a natural-language prompt and returns a list of
AgentCreate objects representing a tailored decision panel.
"""
from __future__ import annotations

import json

import weave

from ..schemas import AgentCreate, Provider

_SCHEMA = {
    "type": "object",
    "properties": {
        "org_name": {"type": "string"},
        "org_description": {"type": "string"},
        "agents": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "system_prompt": {"type": "string"},
                    "weight": {"type": "number", "minimum": 0.5, "maximum": 2.0},
                    "tools": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "role", "system_prompt", "weight", "tools"],
            },
        },
    },
    "required": ["org_name", "org_description", "agents"],
}

_SYSTEM = """You design AI decision panels. Given a committee type, generate 3-5 distinct specialist agents.

Rules:
- Each agent has a unique perspective grounded in their domain expertise.
- system_prompt must be 3-5 sentences: their background, analytical lens, what they care about, and how they argue.
- Vary weights: 0.5 = advisory, 1.0 = standard vote, 2.0 = domain authority with veto-like influence.
- Assign tools: use "research" for agents who ground claims in data, "company_data" for finance/ops agents.
- Be opinionated — a panel of clones is useless. Include at least one skeptic.

Available tools: research, company_data"""


@weave.op()
async def generate_org_agents(prompt: str) -> tuple[str, str, list[AgentCreate]]:
    """Return (org_name, org_description, list[AgentCreate]) from a plain-English prompt."""
    from openai import AsyncOpenAI

    from ..config import get_settings

    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=get_settings().groq_api_key,
    )
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Create a decision panel for: {prompt}\n\n"
                    f"Respond with valid JSON matching this schema:\n{json.dumps(_SCHEMA)}"
                ),
            },
        ],
        response_format={"type": "json_object"},
    )
    raw = json.loads(response.choices[0].message.content)

    agents = [
        AgentCreate(
            name=a["name"],
            role=a["role"],
            system_prompt=a["system_prompt"],
            weight=float(a.get("weight", 1.0)),
            tools=a.get("tools", ["research"]),
            position=i,
            provider=Provider.wandb,
            model="llama-3.3-70b-versatile",
        )
        for i, a in enumerate(raw["agents"])
    ]
    return raw["org_name"], raw.get("org_description", ""), agents
