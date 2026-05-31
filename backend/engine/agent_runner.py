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

from ..schemas import Agent, Position, Stance
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


# ───────────────────────── round 0 ─────────────────────────
@weave.op()
async def agent_position(agent: Agent, question: str, context: Optional[str]) -> Position:
    backend = resolve_backend(agent.provider)
    if backend is None:
        return _mock_position(agent, question)
    system = agent.system_prompt + (
        "\n\nYou are forming your INITIAL position on the decision below, before "
        "hearing the other panelists. Stay fully in character.")
    prompt = (f"DECISION QUESTION:\n{question}\n\n"
              f"CONTEXT:\n{context or '(none provided)'}\n\nGive your initial position.")
    try:
        data = await complete_json(backend, agent.model, system, prompt, POSITION_SCHEMA)
        return _coerce_position(data)
    except Exception:
        return _mock_position(agent, question)


# ───────────────────────── rounds 1..N ─────────────────────────
@weave.op()
async def agent_turn(agent: Agent, prev: Position, board: str,
                     peers: list[Agent], rnd: int) -> TurnResult:
    backend = resolve_backend(agent.provider)
    if backend is None:
        return _mock_turn(agent, prev, peers, rnd)

    peer_ids = {p.id for p in peers if p.id != agent.id}
    peer_list = "\n".join(f"- {p.name} (id={p.id}): {p.role}"
                          for p in peers if p.id != agent.id)
    prompt = (
        f"{DEBATE_RUBRIC}\n\n"
        f"THE PANEL SO FAR (round {rnd}):\n{board}\n\n"
        f"PEERS YOU MAY ADDRESS (use their id in peer_request.to_agent_id):\n{peer_list}\n\n"
        f"YOUR PREVIOUS POSITION: {prev.stance.value} {prev.score}/10 "
        f"(confidence {prev.confidence}).\n\nTake your deliberation turn now."
    )
    try:
        d = await complete_json(backend, agent.model, agent.system_prompt, prompt, AGENT_TURN_SCHEMA)
        influenced = [i for i in (d.get("influenced_by") or []) if i in peer_ids]
        pr = d.get("peer_request") or None
        if pr and pr.get("to_agent_id") not in peer_ids:
            pr = None
        tc = d.get("tool_call") or None
        if tc and not tc.get("tool"):
            tc = None
        return TurnResult(message=str(d.get("message", "")),
                          position=_coerce_position(d["position"]),
                          influenced_by=influenced, peer_request=pr, tool_call=tc)
    except Exception:
        return _mock_turn(agent, prev, peers, rnd)


# ───────────────────────── deterministic mock fallback ─────────────────────────
def _mock_position(agent: Agent, question: str) -> Position:
    r = _seed(agent.name, question)
    score = round(4.0 + (r % 60) / 10.0, 1)
    return Position(stance=decision_from_score(score), score=score,
                    confidence=round(0.5 + (r % 40) / 100.0, 2),
                    rationale=f"[mock] {agent.role}: initial read (no model configured).")


def _mock_turn(agent: Agent, prev: Position, peers: list[Agent], rnd: int) -> TurnResult:
    r = _seed(agent.name, str(rnd))
    pull = (6.5 - prev.score) * 0.25
    new_score = max(0.0, min(10.0, round(prev.score + pull, 1)))
    influenced = []
    if peers and abs(pull) > 0.4:
        cand = peers[r % len(peers)]
        if cand.id != agent.id:
            influenced = [cand.id]
    return TurnResult(
        message=f"[mock] {agent.name}: after round {rnd} I "
                f"{'hold' if abs(pull) < 0.4 else 'adjust'} my position.",
        position=Position(stance=decision_from_score(new_score), score=new_score,
                          confidence=min(1.0, round(prev.confidence + 0.05, 2)),
                          rationale=f"[mock] {agent.role}: updated after the debate."),
        influenced_by=influenced)
