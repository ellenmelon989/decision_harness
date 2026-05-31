# Decision Harness — START HERE (Hour 0 done)

A configurable AI decision council that debates a question over multiple rounds and
produces a weighted, fully-inspectable verdict. Full plan in [ROADMAP.md](ROADMAP.md);
the integration seam is [docs/CONTRACT.md](docs/CONTRACT.md).

## ✅ What already works (verified end-to-end)
- FastAPI backend: orgs/agents/sessions, **live SSE stream**, weighted verdict, influence graph, HITL re-run.
- Debate engine runs on **real LLMs** — provider-routed (`engine/llm.py`): `provider=wandb` → W&B Inference, `provider=anthropic` → Anthropic; **deterministic mock fallback** when no creds, so it still runs keyless. Verified: real traced debate where agents address each other by name.
- Real tool_call→tool_result loop (`engine/tools.py` stubs; swap for MCP).
- `personas/` auto-seeds the **Judge Panel** org (Nico, Ryan, Uma, Ra'ad, Skeptic) with parsed weights.
- Weave: every engine step is `@weave.op()` and auto-traces the model calls. Auth + IDOR hardened.
- **AI org-builder** (`POST /orgs/generate`) builds a custom panel from a prompt; **Weave Evaluation** harness (`python -m backend.evaluation`) scores verdicts with 4 scorers → leaderboard; **pytest** suite (`python -m pytest`, 8 tests, no network).

## Run the backend (no keys needed)
```bash
cd /Users/yamanbicer/decision_harness
source .venv/bin/activate                       # Python 3.12 venv with deps
# (or: cd backend && pip install -r requirements.txt)
cp backend/.env.example backend/.env            # optional; works empty
uvicorn backend.main:app --reload --port 8000
# check: curl localhost:8000/health   → {"ok":true,...,"repo":"in-memory"}
```

## Run the frontend
```bash
cd frontend && cp .env.local.example .env.local && npm install && npm run dev
# http://localhost:3000 → pick Judge Panel → Run debate → watch it stream
```

## Workstreams (ROADMAP §3) — what each of you owns now
| WS | Owner | Start file(s) | First task |
|---|---|---|---|
| **A · Engine** | you | `backend/engine/` | real LLM calls already wired (`llm.py`). Next: point `WANDB_INFERENCE_MODEL` at a stronger model for JSON reliability; attach real **MCP tools** (replace `tools.py` stubs); for `provider=anthropic` swap `llm.py`'s Messages call for the full **Claude Agent SDK** subagent loop |
| **B · Backend/DB** | eng 2 | `backend/db/`, `backend/scorers.py` | create Supabase project, run `backend/db/migrations.sql`, set `SUPABASE_*` (flips repo from in-memory → Postgres automatically); wire `weave.Evaluation` |
| **C · Frontend** | eng 3 | `frontend/app/page.tsx`, `frontend/lib/` | grow boardroom-lite → Boardroom + Inspector + InfluenceGraph + VerdictPanel + HITL re-run |
| **D · Voice** | eng 4 | `voice/`, `frontend` | ElevenLabs streaming TTS per `voice_id` on each `message` event; realtime STT; Recall.ai bot (stretch). See `voice/README.md` |

## The contract
Everything talks through [docs/CONTRACT.md](docs/CONTRACT.md) — `backend/schemas.py` ↔ `frontend/lib/types.ts`.
Don't rename a field without telling the team.

## Keys to provision (parallel)
Supabase project · ElevenLabs Creator/Pro · Recall.ai (stretch) · Anthropic credits
(https://forms.gle/rj1tGQK6cBeYmvq38). W&B already done (entity `yamanbicer-mindra`). **Rotate the W&B key post-event.**
