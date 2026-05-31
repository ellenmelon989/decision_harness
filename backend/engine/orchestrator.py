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
    """(ranking, edges). Weight = |Δscore| of influenced agent, split across credited peers."""
    out: Counter = Counter()
    edges: dict[tuple[str, str], float] = defaultdict(float)
    for ev in events:
        if ev.type == EventType.position_update and ev.influenced_by:
            w = abs(float(ev.content.get("delta") or 0)) or 0.5
            for src in ev.influenced_by:
                out[src] += w
                edges[(src, ev.agent_id)] += w
    total = sum(out.values()) or 1
    ranking = [InfluenceScore(agent_id=a.id, influence=round(out.get(a.id, 0) / total, 3))
               for a in agents]
    ranking.sort(key=lambda r: r.influence, reverse=True)
    return ranking, edges


def _structural(positions: dict[str, Position], agents: list[Agent]):
    by_id = {a.id: a for a in agents}
    majority = Counter(p.stance.value for p in positions.values()).most_common(1)[0][0]
    dissent = [Dissent(agent_id=aid, stance=p.stance,
                       why=f"{by_id[aid].role} held {p.stance.value} at {p.score}/10")
               for aid, p in positions.items() if p.stance.value != majority]
    ordered = sorted(positions.items(), key=lambda kv: kv[1].score)
    conflicts: list[Conflict] = []
    if len(ordered) >= 2 and ordered[-1][1].score - ordered[0][1].score >= 2:
        lo, hi = ordered[0], ordered[-1]
        conflicts = [Conflict(between=[lo[0], hi[0]],
                              issue=f"widest gap: {hi[1].score} vs {lo[1].score} / 10")]
    return majority, conflicts, dissent


def _transcript(events: list[Event], agents: list[Agent]) -> str:
    by_id = {a.id: a.name for a in agents}
    lines = []
    for e in events:
        who = by_id.get(e.agent_id, "Orchestrator")
        if e.type == EventType.message:
            lines.append(f"{who}: {e.content.get('text', '')}")
        elif e.type in (EventType.position, EventType.position_update):
            lines.append(f"{who} [{e.content.get('stance')} {e.content.get('score')}/10]: "
                         f"{e.content.get('rationale', '')}")
    return "\n".join(lines)[:6000]


async def _summarize(transcript: str, positions: dict[str, Position],
                     agents: list[Agent]) -> dict:
    majority, conflicts, dissent = _structural(positions, agents)
    summary = f"Panel leans {majority} on the weighted vote."
    agreements: list[str] = []
    backend = resolve_backend("anthropic")
    if backend:
        try:
            d = await complete_json(backend, _DEFAULT_MODEL, ORCHESTRATOR_PROMPT,
                                    transcript, SUMMARY_SCHEMA)
            summary = str(d.get("summary") or summary)
            agreements = [str(x) for x in (d.get("key_agreements") or [])]
        except Exception:
            pass
    return {"summary": summary, "key_agreements": agreements,
            "key_conflicts": conflicts, "dissenting_opinions": dissent}


@weave.op()
async def orchestrate_verdict(agents: list[Agent], final_positions: dict[str, Position],
                              weights: dict[str, float], events: list[Event]) -> Verdict:
    scores = {aid: p.score for aid, p in final_positions.items()}
    weighted = round(weighted_score(scores, weights), 2)
    base = decision_from_score(weighted)
    decision = apply_veto_cap(base, agents, final_positions)
    ranking, _ = _influence(agents, events)
    summary = await _summarize(_transcript(events, agents), final_positions, agents)
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
