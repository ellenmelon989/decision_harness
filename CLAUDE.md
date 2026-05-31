# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Decision Harness** — a configurable AI decision council. A panel of weighted persona-agents (judges / a board / a VC committee) debates a question over N rounds and produces a **weighted, fully-inspectable verdict** plus an **influence graph** showing who swayed whom. Every step is emitted as a typed event, streamed live, and traced in W&B Weave.

The authoritative product spec is [ROADMAP.md](ROADMAP.md); [START_HERE.md](START_HERE.md) is the orientation doc; [docs/CONTRACT.md](docs/CONTRACT.md) is the API/event contract.

## Repo layout

- [backend/](backend/) — FastAPI app, the debate engine, repositories, eval harness. **This is the product.**
- [frontend/](frontend/) — Next.js 16 / React 18 boardroom UI (SSE-driven).
- [voice/](voice/) — ElevenLabs TTS bridge (stretch goal, mostly stubs).
- [personas/](personas/) — `*.md` persona files that seed the demo "Judge Panel" org.
- [jury-meeting/](jury-meeting/) — a **separate, standalone package** (its own backend + single-file frontend). It only couples to the main app by *reading* a finished decision from Supabase; it shares no engine code. Changes here don't affect the main app.
- [main.py](main.py) — root-level Weave + W&B Inference smoke test, unrelated to the backend app (`python main.py`).

## Central design principle: graceful degradation

**The entire stack boots and runs end-to-end with zero API keys.** This is the most important constraint to preserve — never make a code path hard-require a key.

- No Supabase configured → `InMemoryRepository`, auto-seeded with the Judge Panel ([backend/db/repository.py](backend/db/repository.py), [backend/db/seed.py](backend/db/seed.py)).
- No model keys → agents and the orchestrator summary fall back to **deterministic mocks** ([backend/engine/agent_runner.py](backend/engine/agent_runner.py)).
- No `WANDB_API_KEY` → Weave tracing silently off.
- Auth: a missing token is the demo user **only** in local dev; the moment `SUPABASE_URL` is set, a valid Bearer token is required ([backend/api/deps.py](backend/api/deps.py)).

`get_settings()` ([backend/config.py](backend/config.py)) reads `backend/.env` (resolved by absolute path, so it works regardless of launch CWD) and exposes `*_enabled` properties that gate every optional subsystem.

## Architecture

### The frozen contract
[backend/schemas.py](backend/schemas.py) (Pydantic) ↔ [frontend/lib/types.ts](frontend/lib/types.ts) (TypeScript), documented in [docs/CONTRACT.md](docs/CONTRACT.md). These are the seam between backend, frontend, and voice. **Do not rename a field on one side without updating the other and the contract doc.**

### Event-sourced debate
The whole debate is a stream of typed `Event`s (`position`, `message`, `peer_request`, `tool_call`/`tool_result`, `position_update` with `influenced_by`, `orchestrator`, `verdict`). State (boardroom, transcript, verdict, influence) is **reconstructed by replaying events** — on the backend, the frontend ([frontend/lib/useEventStream.ts](frontend/lib/useEventStream.ts)), and the voice bridge alike. The taxonomy is the table in [docs/CONTRACT.md](docs/CONTRACT.md).

### Debate loop — [backend/engine/debate.py](backend/engine/debate.py)
1. **Round 0**: every agent forms an independent position in parallel (`asyncio.gather`).
2. **Rounds 1..N**: each agent takes a turn seeing the rendered board; emits a message, optional peer_request / tool_call, and a position_update carrying `influenced_by`. Early-converges when normalized score variance drops below `CONVERGE_THRESHOLD` (0.15).
3. **Verdict** ([backend/engine/orchestrator.py](backend/engine/orchestrator.py)): the weighted score, conflicts, and dissent are computed with **real, deterministic math** ([backend/engine/scoring.py](backend/engine/scoring.py)); only the natural-language `summary` comes from an LLM (with a terse fallback). Influence ranking is derived from `position_update.influenced_by` edges.

Every engine function is decorated `@weave.op()` so the full debate auto-traces.

### Provider routing — [backend/engine/llm.py](backend/engine/llm.py)
`resolve_backend(provider)` picks the actual backend: `"wandb"` (W&B Inference, OpenAI-compatible async client, JSON mode) | `"anthropic"` (Messages API with **forced tool-use** to guarantee structured JSON) | `None` (→ caller uses its mock). If an agent's declared provider has no creds, it falls back to whatever IS configured. All structured calls go through `complete_json(...)`.

### Streaming — [backend/engine/stream.py](backend/engine/stream.py) + [backend/api/sessions.py](backend/api/sessions.py)
In-process `asyncio.Queue` pub/sub. `POST /sessions` kicks off the debate as a background `asyncio.create_task`; `GET /sessions/{id}/stream` is an SSE endpoint that **replays event history, then goes live**. For multi-process deploys this would be swapped for Supabase Realtime on the `events` table.

### Repository pattern — [backend/db/repository.py](backend/db/repository.py)
`get_repo()` returns `SupabaseRepository` or `InMemoryRepository` behind one interface. Routers never know which is live. The Supabase client uses the **service key and bypasses RLS** — ownership is enforced in `deps.py`, where guards return **404 (not 403)** so resource existence isn't leaked.

### Persona seeding
Each [personas/](personas/)`*.md` file becomes one agent. The loader ([backend/db/seed.py](backend/db/seed.py)) reads the file's **YAML frontmatter** (`name`, `role`, `weight`, `position`, `model`, `provider`, `voice_id`, `tools`, `structural`; `veto` is set when an agent declares `veto: true` or carries a `cap_rule` block) to configure the agent, and uses the body — **with the fenced "demo-prep reference" block and HTML comments stripped** — as the `system_prompt`. That demo-prep block is the answer key (predicted scores / "natural verdict") and must never reach the model. `seed_judge_panel` runs both for the in-memory demo org and on first login (`POST /orgs/ensure-seed`). A `veto` agent (the Skeptic) caps a clean YES to CONDITIONAL via `apply_veto_cap` in the orchestrator. Frontmatter keys with no schema field (`conflict_partner`, `conflict_dimension`, `cap_rule.unlock_condition`, …) are not yet wired in.

## Commands

All Python commands run from the repo root with the venv active:
```bash
source .venv/bin/activate          # Python 3.12 venv with deps preinstalled
```

| Task | Command |
|---|---|
| Run backend (no keys needed) | `uvicorn backend.main:app --reload --port 8000` |
| Health check | `curl localhost:8000/health` → `{"ok":true,...,"repo":"in-memory"}` |
| Run all tests (8, no network, mock mode) | `python -m pytest` |
| Run a single test | `python -m pytest tests/test_engine.py::test_mock_debate_produces_verdict` |
| Weave Evaluation harness | `python -m backend.evaluation` (append `1` for a one-question smoke) |
| Apply DB schema (needs `SUPABASE_DB_URL` + `psql`) | `python -m backend.db.migrate` |
| Run frontend | `cd frontend && npm install && npm run dev` |
| Frontend build / lint | `npm run build` · `npm run lint` |

Install deps freshly with `pip install -r backend/requirements.txt`. **`backend/requirements.txt` is the complete, canonical list** — the root [requirements.txt](requirements.txt) is a stale subset used only by the root `main.py` smoke test.

## Database

There are two parallel ways to apply the schema (same DDL, ROADMAP §4):
- [backend/db/migrations.sql](backend/db/migrations.sql) via `python -m backend.db.migrate` (the one wired to the app/repository).
- [supabase/migrations/](supabase/migrations/) (timestamped) via the Supabase CLI `supabase db push`.

Keep them in sync if you change the schema. **When adding a foreign key, set its `ON DELETE` rule** or deleting a parent row FK-violates: `events.agent_id` → `cascade`, `events.parent_event` / `sessions.parent_session` → `set null`; `owner_id` / `created_by` are plain `uuid` (deliberately **not** FKs to `auth.users`, so the synthetic DEMO_USER can own rows). `migrations.sql` ends with self-healing `ALTER`s that re-apply these rules on existing DBs. Auth verifies user JWTs against the project's published JWKS (ES256/RS256) — there is no shared JWT secret; verification is keyed off `SUPABASE_URL`.

## Infrastructure is managed via CLI, not dashboards

The **Vercel**, **Supabase**, and **Railway** CLIs are all installed and logged in in this terminal (Vercel `yamanbicer-8788`; Supabase project `decision-harness` / ref `cutoewanmhbkmcxdtxda` is linked; Railway authed as the project owner). **Manage their configuration yourself through these CLIs** — set env vars, link/inspect projects, trigger deploys, run migrations, read logs, etc. Do **not** tell the user to go configure something in a web dashboard/settings page; if it can be done from the CLI, do it from the CLI.

- Vercel: `vercel env`, `vercel deploy`, `vercel link`, `vercel logs`, `vercel project ls`
- Supabase: `supabase projects list`, `supabase link`, `supabase db push`, `supabase secrets set`
- Railway: `railway variables`, `railway up`, `railway logs`, `railway status`, `railway link`

## Deploy

- **Backend → Railway** via [Dockerfile](Dockerfile) + [railway.json](railway.json) (`python:3.11-slim`, installs `backend/requirements.txt`). Railway watches the **`yamanbicer/decisive` fork**, not this repo: a `PostToolUse` hook in `.claude/settings.local.json` force-pushes `HEAD:main` to `decisive` on every `git push`, which triggers the deploy. `railway up` (from a linked dir) also deploys directly.
- **Live:** frontend **https://decisiveai.vercel.app**, backend **https://decisive-production-3b01.up.railway.app** (`/health` shows live subsystem status).
- **Frontend → Vercel** (project slug `decisive`, team `yamanns`). The backend's CORS `allow_origin_regex` is pinned to both slugs to keep look-alike Vercel projects out (see `cors_origin_regex` in [backend/config.py](backend/config.py)); don't loosen it to `*.vercel.app`.

## Gotchas

- **Use `127.0.0.1`, not `localhost`**, for the API URL. macOS resolves `localhost` to IPv6 `::1` first, but uvicorn binds IPv4-only by default → `TypeError: Failed to fetch`. This is baked into `API_URL` defaults and the `.env.example` files.
- **Railway runs `startCommand` without a shell** → keep the `sh -c "... --port ${PORT:-8000}"` wrapper in [railway.json](railway.json) + the `PORT` service var, or uvicorn gets a literal `$PORT` and crash-loops the healthcheck. `weave.init()` runs in a daemon thread ([main.py](main.py)) so it can't block uvicorn from serving `/health` during the healthcheck window.
- **Supabase email confirmation is OFF** (disabled 2026-06-01 so demo signups get a session instantly and don't trip the built-in email cap of **2 emails/hr, project-wide**, which is raisable only via custom SMTP — that cap is what surfaced `email rate limit exceeded` on the signup form). Password auth is unaffected; confirmation is an independent gate. Don't try to re-toggle it from code/CLI: `supabase config` has only `push` (a whole-`config.toml` sync, no `pull` to baseline → would clobber other live auth settings), and the CLI's macOS-Keychain credential (`Supabase CLI`/`supabase`) is an OAuth **session** token, *not* a Management API PAT (`sbp_…`) — it 401s ("JWT could not be decoded") against `api.supabase.com`. Script it with a PAT (supabase.com/dashboard/account/tokens) → `PATCH /v1/projects/<ref>/config/auth {"mailer_autoconfirm":true}`, or just use the dashboard (Auth → Sign In/Providers → Email).
- **Auth smoke tests:** mint a pre-confirmed user with `POST {SUPABASE_URL}/auth/v1/admin/users` `{"email_confirm":true}` (service key), then password-grant for a real ES256 token. Admin-create **accepts `@example.com`** — it bypasses email validation (verified end-to-end); only the public `signUp` form rejects look-alike domains. `python -m backend.db.integration_smoke` runs the whole flow (login → ensure-seed → debate → IDOR) and self-cleans.
- **zsh reserves `$UID`** — never assign to `UID` in a Bash-tool script (throws "bad math expression"); use another name.
- `pytest.ini` sets `asyncio_mode = auto`, so `async def test_*` runs without an explicit marker.
- Tests force mock mode by monkeypatching `resolve_backend` to return `None` — keep new engine code routing through `resolve_backend` so it stays testable offline.
