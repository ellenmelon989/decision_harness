"""FastAPI backend connecting the mock-Zoom frontend to the jury meeting.

    uvicorn api:app --reload --port 8000   (run from backend/)

Endpoints:
  POST /meeting/init  {meeting_id?}            -> record summary + voiced openings
  POST /meeting/ask   {meeting_id?, question}  -> routed, voiced juror answer
  GET  /audio/<file>                           -> served mp3
  GET  /health
"""
from __future__ import annotations

import weave
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import orchestrator
import voice
from llm import PROJECT_PATH

load_dotenv()

# Init Weave once at import so every request is traced. Tolerate a missing key
# so the server still boots for a text-only / no-key smoke test.
try:
    weave.init(PROJECT_PATH)
except Exception as e:  # noqa: BLE001
    print(f"[warn] weave.init failed ({e}); continuing without tracing.")

app = FastAPI(title="Decision Harness — Jury Meeting")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/audio", StaticFiles(directory=voice.AUDIO_DIR), name="audio")


class InitReq(BaseModel):
    meeting_id: str | None = None


class AskReq(BaseModel):
    meeting_id: str | None = None
    question: str


def _record(meeting_id: str | None) -> dict:
    # Reads the team DB (Supabase) by id, or the local sample when unset/unconfigured.
    return orchestrator.load_record(meeting_id)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "project": PROJECT_PATH}


@app.post("/meeting/init")
def meeting_init(req: InitReq) -> dict:
    record = _record(req.meeting_id)
    openings = [voice.voice_turn(t) for t in orchestrator.opening_statements(record)]
    return {
        "meeting_id": record.get("meeting_id"),
        "subject": record.get("subject"),
        "verdict": record.get("verdict"),
        "overall_score": record.get("overall_score"),
        "summary": record.get("summary"),
        "jurors": record.get("jurors"),
        "trace_url": record.get("trace_url"),
        "openings": openings,
    }


@app.post("/meeting/ask")
def meeting_ask(req: AskReq) -> dict:
    record = _record(req.meeting_id)
    turn = voice.voice_turn(orchestrator.ask(req.question, record))
    return turn
