"""Decision source for the jury meeting.

We are independent from the decision engine: our ONLY coupling is reading the
finished decision + reasoning out of the team's Supabase (same env names as
their backend/config.py). If Supabase isn't configured we fall back to
sample_decision.json so the meeting still runs offline.

Team schema we read (see backend/db/migrations.sql):
  sessions(final_verdict jsonb, question, context, weave_trace_url, ...)
  positions(session_id, round, agent_id, stance, score, confidence, rationale)
  agents(id, name, role, weight, voice_id)

We map that into one flat `record` the meeting uses:
  { meeting_id, subject{title,summary,details}, verdict, overall_score,
    summary, jurors[{agent_id,name,role,weight,voice_id,stance,score,rationale}],
    trace_url }
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_HERE = Path(__file__).parent
SAMPLE = _HERE / "sample_decision.json"

# YES/NO/CONDITIONAL (engine) -> the meeting's verdict vocabulary.
_VERDICT_MAP = {"YES": "PICK", "NO": "ELIMINATE", "CONDITIONAL": "CONDITIONAL"}


def _supabase():
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY")
    if not (url and key):
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception as e:  # noqa: BLE001
        print(f"[db] supabase unavailable ({e}); using sample.")
        return None


def _latest_positions(positions: list[dict]) -> dict[str, dict]:
    """Keep the last (highest-round) position per agent."""
    by_agent: dict[str, dict] = {}
    for p in sorted(positions, key=lambda r: r.get("round", 0)):
        by_agent[p["agent_id"]] = p
    return by_agent


def _from_supabase(session_id: str) -> dict | None:
    sb = _supabase()
    if sb is None:
        return None
    srow = sb.table("sessions").select("*").eq("id", session_id).execute().data
    if not srow:
        return None
    session = srow[0]
    positions = sb.table("positions").select("*").eq("session_id", session_id).execute().data
    agents = sb.table("agents").select("*").eq("org_id", session["org_id"]).execute().data
    agents_by_id = {a["id"]: a for a in agents}
    latest = _latest_positions(positions)

    jurors = []
    for agent_id, pos in latest.items():
        a = agents_by_id.get(agent_id, {})
        jurors.append(
            {
                "agent_id": agent_id,
                "name": a.get("name", "Juror"),
                "role": a.get("role", ""),
                "weight": float(a.get("weight", 1.0)),
                "voice_id": a.get("voice_id"),
                "stance": pos.get("stance"),
                "score": pos.get("score"),
                "rationale": pos.get("rationale", ""),
            }
        )
    jurors.sort(key=lambda j: j["weight"], reverse=True)

    verdict = session.get("final_verdict") or {}
    return {
        "meeting_id": session_id,
        "subject": {
            "title": session.get("question", "Decision"),
            "summary": session.get("question", ""),
            "details": {"context": session.get("context", "")},
        },
        "verdict": _VERDICT_MAP.get(verdict.get("decision"), verdict.get("decision", "")),
        "overall_score": verdict.get("weighted_score"),
        "summary": verdict.get("summary", ""),
        "jurors": jurors,
        "trace_url": session.get("weave_trace_url"),
    }


def get_record(meeting_id: str | None = None) -> dict:
    """Fetch the decision record from Supabase, else the local sample."""
    if meeting_id:
        rec = _from_supabase(meeting_id)
        if rec:
            return rec
    return json.loads(SAMPLE.read_text())
