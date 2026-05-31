# Supabase Auth + Data Enablement — Design Spec

**Date:** 2026-05-31
**Status:** Approved, implementing
**Context:** Real Supabase credentials are now wired (`backend/.env`, `frontend/.env.local`).
Setting `SUPABASE_URL` flips the app into production mode: the repo switches from
in-memory to Postgres (`get_repo()`), and `auth_enabled` becomes true (every request
needs a valid Bearer token). The app wasn't built for that yet — no login UI, no
Supabase-mode seeding, schema not applied. This spec covers closing those gaps so the
app runs end-to-end on Supabase.

## Decisions (locked)

- **Auth method:** Supabase email + password (instant, no SMTP/redirect setup, testable headlessly).
- **Token verification:** asymmetric JWKS / ES256 against the project's published keys
  (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`). No shared secret. Already implemented
  in `backend/api/deps.py` + `backend/config.py` (`jwks_url`, `auth_enabled = bool(supabase_url)`).
  5 tests pass in `tests/test_auth.py`.
- **Seeding:** auto-seed the Judge Panel per user on first login (idempotent — only when the
  user owns zero orgs). Owner is the real `auth.uid()`, satisfying `orgs.owner_id → auth.users(id)`.
- **SSE auth:** `EventSource` can't send headers, so the live debate stream authenticates via
  an `?access_token=` query param, verified by a stream-only dependency using the same JWKS path.

## Architecture

### Backend (Python) — contained changes in `backend/`
1. **`api/deps.py`**
   - Refactor verification into `_subject_from_token(token) -> str` (verify via JWKS, extract+validate `sub`), shared by both dependencies.
   - Keep `get_current_user(authorization: Header)` for all header-authed endpoints.
   - Add `get_current_user_sse(request: Request)` that reads `request.query_params["access_token"]` and runs the same verification. Used only by the stream endpoint.
2. **`api/sessions.py`** — `stream_session` swaps its dependency to `get_current_user_sse`.
3. **`api/orgs.py`** — add `POST /orgs/ensure-seed` (authed, idempotent): if `repo.list_orgs(user)` is empty, `seed_judge_panel(repo, user)`; return the org list either way.
4. **`main.py`** — remove the public `POST /seed/judges` (hardcoded demo user, unauthenticated). `/health` stays public.

### Frontend (Next.js) — `frontend/`
1. **`lib/auth.tsx`** — `AuthProvider` context: `{ session, user, signIn, signUp, signOut, loading }`, backed by `supabase.auth` + `onAuthStateChange`. supabase-js auto-refreshes tokens.
2. **`components/AuthGate.tsx`** — no session → minimal email+password form (sign-in/sign-up toggle, error display); session → render children. Wrap the app in `app/layout.tsx` (or `page.tsx`).
3. **`lib/api.ts`** — `j()` awaits `supabase.auth.getSession()` and sets `Authorization: Bearer <token>`. `streamUrl(id)` appends `?access_token=<token>`. New `ensureSeed()` method → `POST /orgs/ensure-seed`.
4. **`app/page.tsx`** — after auth, call `ensureSeed()` then `listOrgs()`; add a sign-out affordance.

### Data & migrations
- Apply `backend/db/migrations.sql` to the project (`psql` via the pooler connection string built from `SUPABASE_DB_PASSWORD`; Supabase SQL editor as fallback). Creates 5 tables + RLS policies.
- Backend uses the service key (bypasses RLS); RLS protects any direct client (anon-key) access. Ownership is also enforced in code (`require_org_access`, etc.).

## Testing
- **Backend (pytest, no network):** extend `tests/test_auth.py` — SSE query-param token accepted; missing/invalid query token → 401; reuse the EC-keypair + stub-JWKS harness. Seed idempotency: second `ensure-seed` for the same user doesn't duplicate.
- **Manual e2e (headless):** create a test user via the Supabase auth REST API, sign in for a real ES256 token, call `/orgs` with it (confirm seed), open a debate + stream with `?access_token=`.

## Out of scope (YAGNI)
Password reset, email verification, OAuth/magic link, multi-org management UI, mid-stream
token-refresh handling, RLS-only (no service key) mode. The in-memory dev path remains
available by blanking `SUPABASE_URL`.

## Consequences / risks
- Token in the stream URL can appear in server/proxy logs — accepted (short-lived ~1h tokens, stream-only endpoint).
- Access token can expire mid-stream → stream reconnect may 401. Accepted (debates are short); revisit if it bites.
- Enabling Supabase means local dev now requires login. The keyless in-memory demo is still reachable by blanking `SUPABASE_URL` in a local `backend/.env`.
