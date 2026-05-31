# What the Jury Meeting reads from the DB

The jury-meeting app is independent from the decision engine. Its **only** coupling is
reading a finished decision out of Supabase (`backend/db.py` → `get_record(session_id)`).
We map your existing tables — nothing new strictly required. This note is so you know which
fields we depend on; if any are routinely empty, that's the feedback.

## Tables / fields we read (all already in `backend/db/migrations.sql`)

| Source | Field | We use it for |
|---|---|---|
| `sessions` | `final_verdict` (jsonb) | `decision` → PICK/ELIMINATE/CONDITIONAL, `weighted_score` → overall, `summary` |
| `sessions` | `question`, `context` | the "subject under review" shown to the room |
| `sessions` | `weave_trace_url` | the "View on Weave" link |
| `positions` | `stance`, `score`, `rationale` (latest round per agent) | each juror's opening + the grounding for their Q&A answers |
| `agents` | `name`, `role`, `weight`, `voice_id` | who the juror is + which ElevenLabs voice speaks |

## The two asks (nice-to-have, not blocking)

1. **`positions.rationale` should be populated** for every agent in the final round — it's
   what each juror "explains" and is grounded against. Empty rationale → thin feedback.
2. **`agents.voice_id`** ideally set per persona (the persona files have `voice_id: null`
   right now). If null, we auto-assign a stock ElevenLabs voice by seat order, so it still
   works — but real per-persona voices are better for the demo.

## Verdict vocabulary mapping

`YES → PICK`, `NO → ELIMINATE`, `CONDITIONAL → CONDITIONAL`.

## How to point us at a real session

Set `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` in `jury-meeting/backend/.env`, then call
`POST /meeting/init {"meeting_id": "<session_id>"}`. With those unset we run on
`backend/sample_decision.json` offline.
