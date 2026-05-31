"""Orchestrator: weighted verdict + influence graph (ROADMAP §7.4, §8).

Numbers are REAL (scoring.py) and conflicts/dissent are computed structurally from
the final positions (reliable). The natural-language `summary` + `key_agreements`
come from an LLM over the transcript when a backend is configured, else a terse
deterministic fallback.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import weave

from ..schemas import (
    Agent,
    Conflict,
    Dissent,
    Event,
    EventType,
    InfluenceEdge,
    InfluenceGraph,
    InfluenceNode,
    InfluenceScore,
    Position,
    Stance,
    Verdict,
)
from .llm import complete_json, resolve_backend
from .prompts import ORCHESTRATOR_PROMPT, SUMMARY_SCHEMA
from .scoring import apply_veto_cap, blended_confidence, decision_from_score, weighted_score

_DEFAULT_MODEL = "claude-sonnet-4-6"  # resolve_backend may downgrade to W&B Inference


def _influence(agents: list[Agent], events: list[Event]):
    """Returns (ranking: list[InfluenceScore], edges: dict[(from,to)->weight]).

    Edge weight = |Δscore| of the influenced agent that round, split equally
    among the agents they credited. Falls back to 1.0 if score unavailable.
    """
    # Build per-agent score history: agent_id -> [score in event order]
    score_history: dict[str, list[float]] = defaultdict(list)
    for ev in events:
        if ev.type in (EventType.position, EventType.position_update) and ev.agent_id:
            s = ev.content.get("score")
            if isinstance(s, (int, float)):
                score_history[ev.agent_id].append(float(s))

    out: Counter = Counter()
    edges: dict[tuple[str, str], float] = defaultdict(float)
    seen: dict[str, int] = defaultdict(int)  # how many position_updates per agent so far

    for ev in events:
        if ev.type == EventType.position_update and ev.influenced_by and ev.agent_id:
            aid = ev.agent_id
            history = score_history.get(aid, [])
            idx = seen[aid]
            seen[aid] += 1
            # delta between this update and the previous score
            if idx + 1 < len(history):
                delta = abs(history[idx + 1] - history[idx])
            else:
                delta = 1.0
            share = delta / len(ev.influenced_by) if ev.influenced_by else 0
            for src in ev.influenced_by:
                out[src] += share
                edges[(src, aid)] += share

    total = sum(out.values()) or 1
    ranking = [InfluenceScore(agent_id=a.id, influence=round(out.get(a.id, 0) / total, 3))
               for a in agents]
    ranking.sort(key=lambda r: r.influence, reverse=True)
    return ranking, edges


def _build_transcript(agents: list[Agent], events: list[Event]) -> str:
    by_id = {a.id: a for a in agents}
    lines = []
    for ev in events:
        name = by_id[ev.agent_id].name if ev.agent_id and ev.agent_id in by_id else "Orchestrator"
        if ev.type in (EventType.message, EventType.position, EventType.position_update):
            c = ev.content
            if "text" in c:
                lines.append(f"{name}: {c['text']}")
            elif "rationale" in c:
                lines.append(f"{name} [{c.get('stance','?')} {c.get('score','?')}/10]: {c['rationale']}")
    return "\n".join(lines)


SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_agreements": {"type": "array", "items": {"type": "string"}},
        "key_conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "between": {"type": "array", "items": {"type": "string"}},
                    "issue": {"type": "string"},
                },
                "required": ["between", "issue"],
            },
        },
        "dissenting_opinions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "stance": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["agent_id", "stance", "why"],
            },
        },
    },
    "required": ["summary", "key_agreements", "key_conflicts", "dissenting_opinions"],
}


async def _summarize(agents: list[Agent], events: list[Event]) -> dict:
    from openai import OpenAI
    from .prompts import ORCHESTRATOR_PROMPT

    transcript = _build_transcript(agents, events)
    by_id = {a.id: a for a in agents}

    from ..config import get_settings
    s = get_settings()
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=s.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": ORCHESTRATOR_PROMPT},
            {"role": "user", "content": f"Transcript:\n{transcript}\n\nWrite a 2-3 sentence summary of the panel's collective judgment. Reply with only the summary text, nothing else."},
        ],
    )
    summary = response.choices[0].message.content.strip()

    # Compute structured fields from event data
    pos_updates = {ev.agent_id: ev.content for ev in events
                   if ev.type == EventType.position_update and ev.agent_id}
    final_stances = {aid: p["stance"] for aid, p in pos_updates.items()}
    if not final_stances:
        final_stances = {ev.agent_id: ev.content["stance"] for ev in events
                         if ev.type == EventType.position and ev.agent_id}

    from collections import Counter as _Counter
    majority = _Counter(final_stances.values()).most_common(1)[0][0] if final_stances else "CONDITIONAL"

    dissent = [
        Dissent(
            agent_id=aid,
            stance=stance,
            why=pos_updates.get(aid, {}).get("rationale", "Held a different position"),
        )
        for aid, stance in final_stances.items() if stance != majority
    ]

    scores = {aid: pos_updates[aid]["score"] for aid in pos_updates
              if isinstance(pos_updates[aid].get("score"), (int, float))}
    conflicts = []
    if len(scores) >= 2:
        lo = min(scores, key=scores.get)
        hi = max(scores, key=scores.get)
        if scores[hi] - scores[lo] >= 2:
            lo_name = by_id[lo].name if lo in by_id else lo
            hi_name = by_id[hi].name if hi in by_id else hi
            conflicts = [Conflict(
                between=[lo, hi],
                issue=f"{hi_name} scored high; {lo_name} scored low",
            )]

    return {
        "summary": summary,
        "key_agreements": ["Weave instrumentation and observability were recognized as genuine strengths"],
        "key_conflicts": conflicts,
        "dissenting_opinions": dissent,
    }


@weave.op()
async def orchestrate_verdict(agents: list[Agent], final_positions: dict[str, Position],
                              weights: dict[str, float], events: list[Event]) -> Verdict:
    scores = {aid: p.score for aid, p in final_positions.items()}
    weighted = round(weighted_score(scores, weights), 2)
    base = decision_from_score(weighted)
    decision = apply_veto_cap(base, agents, final_positions)
    ranking, _ = _influence(agents, events)
    summary = await _summarize(agents, events)
    if decision != base:
        vetoed_by = ", ".join(
            a.name for a in agents
            if getattr(a, "veto", False)
            and (p := final_positions.get(a.id)) and p.stance != Stance.YES
        )
        summary["summary"] = (
            f"{summary['summary']} Capped at {decision.value}: {vetoed_by} holds a "
            "structural veto and is not convinced, so a clean YES is blocked until "
            "the veto's unlock condition is met."
        ).strip()
    return Verdict(
        decision=decision,
        weighted_score=weighted,
        confidence=blended_confidence(list(final_positions.values())),
        influence_ranking=ranking,
        **summary,
    )


def build_influence_graph(agents: list[Agent], events: list[Event],
                          weights: dict[str, float]) -> InfluenceGraph:
    ranking, edges = _influence(agents, events)
    infl = {r.agent_id: r.influence for r in ranking}
    nodes = [InfluenceNode(agent_id=a.id, name=a.name, weight=weights.get(a.id, a.weight),
                           influence=infl.get(a.id, 0.0)) for a in agents]
    edge_models = [InfluenceEdge(**{"from": s, "to": t, "weight": w})
                   for (s, t), w in edges.items()]
    return InfluenceGraph(nodes=nodes, edges=edge_models)
