# Frontend Supabase Auth Wiring — Design

**Date:** 2026-05-31
**Status:** Approved
**Author:** Claude + yaman

## Problem

`GET /orgs` (and every protected route) returns `401 {"detail":"authentication required"}`.

Root cause is a posture mismatch introduced by the `Harden auth + authorization` commit:

- `backend/.env` has a real `SUPABASE_URL`, so `Settings.auth_enabled` (`config.py`,
  `bool(supabase_url)`) is **True**.
- The demo-user fallback in `backend/api/deps.py` (`_resolve_user`) only fires when
  `dev_unauthenticated AND not auth_enabled`. With auth enabled, `DEV_UNAUTHENTICATED=true`
  is ignored, so any request lacking a verified Bearer token is rejected with
  `401 "authentication required"`.
- The frontend API client (`frontend/lib/api.ts` `j()`) never attaches an `Authorization`
  header, there is no login flow, and `NEXT_PUBLIC_SUPABASE_*` are blank (so the
  `frontend/lib/supabase.ts` client is `null`).

Net: the backend demands a verified token; the frontend has no way to obtain or send one.

## Decision

Wire **real Supabase auth** into the frontend (keep the Supabase Postgres DB + token
verification). Chosen over (a) reverting to in-memory/no-auth dev and (b) decoupling auth
from the DB flag (which would re-open the default-deny gap the security commit closed).

Locked choices:

- **Auth method:** Email + password (`signInWithPassword` / `signUp`). Simplest to build
  and test locally; OAuth/magic-link can be added later.
- **New-user data:** Auto-seed a personal Judge Panel on first sign-in via the existing
  idempotent `POST /orgs/ensure-seed` endpoint.
- **Login UX:** Dedicated `/login` route + a client-side auth guard that redirects
  unauthenticated users there and back after sign-in.
- **Session strategy:** Client-side `@supabase/supabase-js` (already installed) with the
  access token attached per request. No `@supabase/ssr`, no new dependencies. The entire
  frontend is `"use client"` calling an external FastAPI, so there is nothing
  server-rendered to protect, and the backend verifies every token regardless of where the
  browser stores the session.

## Scope

**Frontend-only. No backend changes.** The backend is already prepared:

- `get_current_user` / `_resolve_user` verify the `Authorization: Bearer` token against the
  project JWKS.
- `get_current_user_sse` (`deps.py`) reads the token from a `?access_token=` query param,
  because `EventSource` cannot set headers.
- `POST /orgs/ensure-seed` (`api/orgs.py`) idempotently seeds a personal Judge Panel for a
  user who owns zero orgs, then returns their orgs.

## Components

1. **Env** — `frontend/.env.local`:
   - `NEXT_PUBLIC_SUPABASE_URL=https://cutoewanmhbkmcxdtxda.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY=<project anon/publishable key>` — **external input
     required from the user.** This is the *anon* key from Supabase dashboard → Project
     Settings → API. It is NOT the `service_role` key in `backend/.env`, which stays
     server-side only. Must point at the same Supabase project as the backend so tokens
     verify.

2. **Token attachment** — `frontend/lib/api.ts`:
   - `j()` becomes token-aware: `await supabase.auth.getSession()`; if a session exists, add
     `Authorization: Bearer <access_token>`. If `supabase` is `null` (env unset → dev /
     in-memory mode), send no auth header — preserving the existing no-auth local path.
   - `streamUrl(id)` becomes async and appends `?access_token=<token>` to match
     `get_current_user_sse`.
   - Add `ensureSeed()` → `POST /orgs/ensure-seed` (returns `Org[]`).
   - On a `401` despite the guard (e.g. unrecoverable token failure): sign out + redirect to
     `/login` as a safety net.

3. **SSE update** — `frontend/lib/useEventStream.ts`: resolve the async `streamUrl(id)`
   before constructing the `EventSource` (await inside the effect, guard against the effect
   being torn down before the URL resolves).

4. **`/login` route** — `frontend/app/login/page.tsx`, a client component: email + password
   form with a sign-in / sign-up toggle, inline error display, redirect to `/` (or `?next=`)
   on success. If `supabase` is `null`, show a short "auth not configured" note rather than
   a broken form.

5. **Auth guard** — a client component `frontend/app/AuthGuard.tsx` wrapping `{children}`
   in `app/layout.tsx` (single place, applies to all routes). On mount `getSession()`,
   subscribe to `onAuthStateChange`. If `supabase` is configured and there is no session →
   redirect to `/login`. If `supabase` is `null` → render through (dev mode). Brief loading
   state while resolving so we don't flash the app or a redirect.
   - **Must exempt `/login`** (via `usePathname()`): the guard renders `/login` straight
     through regardless of session, otherwise an unauthenticated user redirected to `/login`
     would be redirected again → infinite loop.

6. **First-login bootstrap + header** — `frontend/app/page.tsx`: once authenticated, call
   `api.ensureSeed()` (seeds if empty, returns orgs) instead of bare `listOrgs()`. Header
   gains the signed-in email + a **Sign out** button (`supabase.auth.signOut()` → `/login`).

## Data flow

login (`/login`) → Supabase session stored in browser → guard allows app → `ensureSeed()`
with Bearer token → user owns a Judge Panel org → pick org / run debate → SSE stream carries
`?access_token=`. Sign out clears the session and redirects to `/login`.

## Error handling

- Invalid credentials → inline message on `/login`.
- Expired access token → supabase-js auto-refreshes; `getSession()` returns a fresh token.
- `401` from `j()` despite the guard → sign out + redirect to `/login`.
- `supabase === null` (no env) → app runs unauthenticated against the in-memory backend
  (existing graceful-degradation path), guard and `j()` both no-op the auth.

## Testing

- Manual end-to-end: sign up → land on the seeded Judge Panel → run a debate and watch the
  live SSE stream → sign out → redirected to `/login`.
- Backend `tests/test_auth.py` already covers token verification; no backend changes, so it
  stays green.
- Verify the running app (verification-before-completion skill) before claiming done.

## Non-goals (YAGNI)

- OAuth / magic-link sign-in.
- Org create/generate UI (auto-seed only for now).
- `@supabase/ssr`, cookie-based sessions, middleware route guards.
- Password reset / email confirmation flows beyond Supabase defaults.
