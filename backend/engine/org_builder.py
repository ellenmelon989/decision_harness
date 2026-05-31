"""AI org-builder (ROADMAP §9.4).

`generate_org_agents` takes a natural-language prompt and returns a list of
AgentCreate objects representing a tailored decision panel.
"""
from __future__ import annotations

import json

import weave

from ..schemas import AgentCreate, Provider
from .prompts import ORG_BUILDER_PROMPT, ORG_BUILDER_SCHEMA


@weave.op()
async def generate_org_agents(prompt: str) -> tuple[str, str, list[AgentCreate]]:
    """Return (org_name, org_description, list[AgentCreate]) from a plain-English prompt."""
    from openai import AsyncOpenAI

    from ..config import get_settings

    s = get_settings()
    client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=s.groq_api_key)
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": ORG_BUILDER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Create a decision panel for: {prompt}\n\n"
                    f"Respond with valid JSON matching this schema:\n{json.dumps(ORG_BUILDER_SCHEMA)}"
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
            tools=["research"],
            position=i,
            provider=Provider.wandb,
            model="llama-3.3-70b-versatile",
        )
        for i, a in enumerate(raw["agents"])
    ]
    return raw["org_name"], raw.get("description", ""), agents
