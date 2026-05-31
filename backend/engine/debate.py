"""The debate loop (ROADMAP §7.2). Persists every step as an event, streams it
live, and is fully traced by Weave. Mock agent bodies live in agent_runner.py."""
from __future__ import annotations

import asyncio
from typing import Optional

import weave

from ..schemas import Agent, EventType, Position, Session, SessionStatus, Stance, Verdict
from . import stream
from .agent_runner import agent_position, agent_turn
from .orchestrator import orchestrate_verdict
from .scoring import normalized_variance

CONVERGE_THRESHOLD = 0.15  # normalized score variance below which we stop early


def _render_board(positions: dict[str, Position], agents: list[Agent]) -> str:
    by_id = {a.id: a for a in agents}
    return "\n".join(
        f"- {by_id[aid].name} ({by_id[aid].role}): {p.stance.value} {p.score}/10 — {p.rationale}"
        for aid, p in positions.items()
    )


@weave.op()
async def run_debate(session: Session, agents: list[Agent], repo,
                     weights: Optional[dict[str, float]] = None) -> Verdict:
    weights = weights or session.weights_override or {a.id: a.weight for a in agents}

    def emit(round, etype, content, agent_id=None, parent=None, influenced=None):
        ev = repo.append_event(session.id, round, etype, content, agent_id=agent_id,
                               parent_event=parent, influenced_by=influenced)
        stream.publish(session.id, ev.model_dump(mode="json"))
        return ev

    repo.update_session(session.id, status=SessionStatus.running)
    emit(0, EventType.orchestrator, {"action": "start", "question": session.question})

    # ── Round 0: independent positions (parallel) ──
    positions: dict[str, Position] = {}
    results = await asyncio.gather(
        *[agent_position(a, session.question, session.context) for a in agents])
    for a, p in zip(agents, results):
        positions[a.id] = p
        repo.save_position(session.id, 0, a.id, p)
        emit(0, EventType.position, p.model_dump(), agent_id=a.id)

    # ── Rounds 1..N: debate ──
    for rnd in range(1, session.rounds + 1):
        conflict = round(normalized_variance([p.score for p in positions.values()]), 3)
        emit(rnd, EventType.orchestrator, {"action": "continue", "conflict_level": conflict})
        if conflict < CONVERGE_THRESHOLD and rnd > 1:
            emit(rnd, EventType.orchestrator, {"action": "converge", "conflict_level": conflict})
            break

        board = _render_board(positions, agents)
        turns = await asyncio.gather(
            *[agent_turn(a, positions[a.id], board, agents, rnd) for a in agents])

        tool_tasks = [
            _maybe_call_tool(t.tool_call, session.question) for t in turns
        ]
        tool_results = await asyncio.gather(*tool_tasks)

        for a, t, tool_result in zip(agents, turns, tool_results):
            emit(rnd, EventType.message, {"text": t.message, "to": "all"}, agent_id=a.id)
            if t.peer_request:
                emit(rnd, EventType.peer_request, t.peer_request, agent_id=a.id)
            if t.tool_call and tool_result is not None:
                tc = emit(rnd, EventType.tool_call, t.tool_call, agent_id=a.id)
                emit(rnd, EventType.tool_result,
                     {"tool": t.tool_call["tool"], "result": tool_result},
                     agent_id=a.id, parent=tc.id)
            emit(rnd, EventType.position_update, t.position.model_dump(),
                 agent_id=a.id, influenced=t.influenced_by)
            repo.save_position(session.id, rnd, a.id, t.position)
            positions[a.id] = t.position

    # ── Verdict ──
    events = repo.list_events(session.id)
    verdict = await orchestrate_verdict(agents, positions, weights, events)
    weave_url = None
    try:
        call = weave.get_current_call()
        weave_url = getattr(call, "ui_url", None)
    except Exception:
        pass
    emit(session.rounds + 1, EventType.verdict, verdict.model_dump())
    repo.update_session(session.id, status=SessionStatus.done,
                        final_verdict=verdict, weave_trace_url=weave_url)
    stream.close(session.id)
    return verdict


async def _maybe_call_tool(tool_call: dict | None, question: str) -> str | None:
    if not tool_call:
        return None
    try:
        from ..mcp_servers.research import call_tool
        return await call_tool(tool_call["tool"], tool_call.get("args", {}), question)
    except Exception:
        return "[tool unavailable]"
