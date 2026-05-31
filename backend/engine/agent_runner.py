"""One agent's turn (ROADMAP §7.3).

Real path: each agent is driven by an LLM (provider-routed in llm.py) and returns
structured JSON. If no model credentials are configured — or a call fails — we fall
back to a deterministic MOCK so the pipeline always completes (keyless dev/demo).

WS-A next steps: attach MCP tools per agent (the tool_call flow is already wired in
tools.py + debate.py) and, for `provider=anthropic`, swap the plain Messages call in
llm.py for the full Claude Agent SDK so subagents get native MCP tool loops.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

import weave

from ..schemas import Agent, Position, Provider, Stance
from .llm import complete_json, resolve_backend
from .prompts import AGENT_TURN_SCHEMA, DEBATE_RUBRIC, POSITION_SCHEMA
from .scoring import decision_from_score


@dataclass
class TurnResult:
    message: str
    position: Position
    influenced_by: list[str] = field(default_factory=list)
    peer_request: Optional[dict] = None
    tool_call: Optional[dict] = None


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:12], 16)


def _coerce_position(data: dict) -> Position:
    return Position(
        stance=Stance(str(data["stance"]).upper()),
        score=max(0.0, min(10.0, float(data["score"]))),
        confidence=max(0.0, min(1.0, float(data["confidence"]))),
        rationale=str(data.get("rationale", "")),
    )


def _pick_caller(agent: Agent):
    from ..config import get_settings
    key = get_settings().anthropic_api_key
    if agent.provider == Provider.anthropic and key and key.startswith("sk-ant-"):
        return _call_anthropic
    return _call_wandb_inference


# ───────────────────────── round 0 ─────────────────────────
@weave.op()
async def agent_position(agent: Agent, question: str, context: Optional[str]) -> Position:
    ctx = f"\nAdditional context: {context}" if context else ""
    system = f"You are {agent.name}. Your role: {agent.role}.\n{agent.system_prompt}"
    prompt = f"Decision question: {question}{ctx}\n\nGive your initial independent position before hearing others."
    schema = {
        "type": "object",
        "properties": {
            "stance": {"enum": ["YES", "NO", "CONDITIONAL"]},
            "score": {"type": "number", "minimum": 0, "maximum": 10},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
        },
        "required": ["stance", "score", "confidence", "rationale"],
    }
    caller = _pick_caller(agent)
    raw = await caller(agent, system, prompt, schema)
    return Position(**raw)

# ───────────────────────── rounds 1..N ─────────────────────────
@weave.op()
async def agent_turn(agent: Agent, prev: Position, board: str,
                     peers: list[Agent], rnd: int) -> TurnResult:
    from .prompts import DEBATE_RUBRIC, AGENT_TURN_SCHEMA
    peer_list = "\n".join(f"- {p.name} (id: {p.id}): {p.role}" for p in peers if p.id != agent.id)
    system = f"You are {agent.name}. Your role: {agent.role}.\n{agent.system_prompt}\n\n{DEBATE_RUBRIC}"
    prompt = f"Round {rnd}. Other panel members:\n{peer_list}\n\nCurrent board state:\n{board}\n\nYour current position: {prev.stance.value} ({prev.score}/10). Take your turn."
    caller = _pick_caller(agent)
    raw = await caller(agent, system, prompt, AGENT_TURN_SCHEMA)
    pos = raw["position"]
    if isinstance(pos.get("score"), str):
        pos["score"] = float(pos["score"].split("/")[0].strip())
    if isinstance(pos.get("confidence"), str):
        pos["confidence"] = float(pos["confidence"].split("/")[0].strip())
    return TurnResult(
        message=raw["message"],
        position=Position(**pos),
        influenced_by=raw.get("influenced_by", []),
        peer_request=raw.get("peer_request"),
        tool_call=raw.get("tool_call"),
    )

# ─────────────── real-call skeletons (WS-A wires these in H1-H2) ───────────────
async def _call_anthropic(agent: Agent, system: str, prompt: str, schema: dict) -> dict:
    import anthropic, json
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=agent.model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        tools=[{
            "name": "respond",
            "description": "Structured debate turn response",
            "input_schema": schema,
        }],
        tool_choice={"type": "tool", "name": "respond"},
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise ValueError("No tool_use block in response")


async def _call_wandb_inference(agent: Agent, system: str, prompt: str, schema: dict) -> dict:
    import json
    from openai import AsyncOpenAI
    from ..config import get_settings
    s = get_settings()
    model = agent.model if agent.model.startswith("llama") else "llama-3.3-70b-versatile"
    client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=s.groq_api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt + "\n\nRespond with valid JSON only matching this schema: " + json.dumps(schema)},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    return json.loads(raw)

