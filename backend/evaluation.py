"""Weave Evaluation harness (ROADMAP §9.3) — the Best-of-Weave path.

Runs the panel over a dataset of decision questions and scores each verdict with
the four scorers, producing a Weave leaderboard you can hill-climb.

    python -m backend.evaluation        # full dataset
    python -m backend.evaluation 1      # first question only (cheap smoke)
"""
from __future__ import annotations

import asyncio
from typing import Optional

import weave

from .config import get_settings
from .db.repository import InMemoryRepository
from .db.seed import seed_judge_panel
from .engine.debate import run_debate
from .schemas import EventType
from .scorers import ALL_SCORERS

EVAL_QUESTIONS = [
    "Should this project win Most Sophisticated Harness?",
    "Should we invest $2M in a seed-stage AI devtools startup with no revenue yet?",
    "Should we ship the feature now or delay two weeks for more testing?",
]


def _final_scores(repo, session_id: str) -> list[float]:
    latest: dict[str, dict] = {}
    for r in repo.list_positions(session_id):
        cur = latest.get(r["agent_id"])
        if cur is None or r["round"] > cur["round"]:
            latest[r["agent_id"]] = r
    return [float(r["score"]) for r in latest.values()]


@weave.op()
async def run_panel(question: str) -> dict:
    """Run one full debate and return a scorer-ready output (verdict + eval extras)."""
    repo = InMemoryRepository()
    org = seed_judge_panel(repo, "eval-user")
    if org is None:
        raise RuntimeError("no personas/ to seed the eval panel")
    agents = repo.list_agents(org.id)
    sess = repo.create_session(org.id, question, rounds=2)
    verdict = await run_debate(sess, agents, repo)
    events = repo.list_events(sess.id)
    out = verdict.model_dump()
    out["agent_scores"] = _final_scores(repo, sess.id)
    out["tool_calls"] = sum(1 for e in events if e.type == EventType.tool_call)
    out["n_agents"] = len(agents)
    return out


async def main(limit: Optional[int] = None) -> None:
    s = get_settings()
    if s.weave_enabled:
        weave.init(s.project_path)
    else:
        print("! WANDB_API_KEY not set — running without Weave logging.")
    questions = EVAL_QUESTIONS[:limit] if limit else EVAL_QUESTIONS
    evaluation = weave.Evaluation(dataset=[{"question": q} for q in questions],
                                  scorers=ALL_SCORERS)
    await evaluation.evaluate(run_panel)


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(n))
