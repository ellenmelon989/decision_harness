# Frontend + Vercel deploy — handoff

Context for an agent/engineer taking over **frontend hosting on Vercel**. The
Supabase auth + data layer is already built, wired, and verified end-to-end
(see `docs/superpowers/specs/2026-05-31-supabase-auth-data-design.md`). This doc
is everything you need to deploy `frontend/` and not re-derive the auth design.

## Project facts

- **Supabase project:** `decision-harness` · ref `cutoewanmhbkmcxdtxda` · region `us-east-1`
- **Supabase URL:** `https://cutoewanmhbkmcxdtxda.supabase.co`
- **Frontend:** Next.js app in `frontend/` (App Router, `@supabase/supabase-js`)
- **Vercel:** account already authenticated locally as `yamanbicer-8788`. The
  frontend is **not yet linked** to a Vercel project (`frontend/.vercel/` absent).

## What already works (don't rebuild)

- **Auth:** email + password via Supabase. `frontend/lib/auth.tsx` (`AuthProvider` +
  `useAuth`) and `frontend/components/AuthGate.tsx` (login/signup form gate, wired in
  `app/layout.tsx`). The app renders only when a session exists.
- **Token flow:** `frontend/lib/api.ts` holds the access token (`setAccessToken`,
  kept in sync by `AuthProvider` on every sign-in / refresh) and attaches
  `Authorization: Bearer <token>` to every REST call. `streamUrl()` appends
  `?access_token=<token>` because `EventSource` can't send headers; the backend
  verifies it via `get_current_user_sse`.
- **Seeding:** `api.ensureSeed()` → `POST /orgs/ensure-seed` runs on load; the
  backend seeds the user's personal Judge Panel on first login (idempotent).
- **Backend auth:** asymmetric JWKS/ES256 verification against the project's
  published keys (no shared secret). `auth_enabled` is on whenever `SUPABASE_URL`
  is set. Verified e2e: valid token accepted, missing/bad token → 401, IDOR → 404.

## Frontend env vars (Vercel → Project → Settings → Environment Variables)

All three are **public** (`NEXT_PUBLIC_*`, shipped to the browser). The actual
values are in the local gitignored `frontend/.env.local`; the anon key can also be
re-fetched with `supabase projects api-keys --project-ref cutoewanmhbkmcxdtxda`.

| Var | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://cutoewanmhbkmcxdtxda.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | the `anon` key (see `frontend/.env.local`) |
| `NEXT_PUBLIC_API_URL` | URL of the **deployed FastAPI backend** (see blocker below) |

The Supabase **anon key is RLS-protected and safe to expose**; the `service_role`
key and `SUPABASE_DB_URL` are backend-only secrets — never put them in the frontend.

## Deploy steps

```bash
cd frontend
vercel link                 # link/create a Vercel project; Root Directory = frontend
# set the three env vars for Production (repeat for Preview/Development as needed):
vercel env add NEXT_PUBLIC_SUPABASE_URL production
vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY production
vercel env add NEXT_PUBLIC_API_URL production
vercel --prod               # build + deploy
```

(Or set the env vars in the Vercel dashboard and connect the GitHub repo for
auto-deploys — if you do, set **Root Directory = `frontend`** in project settings.)

## ⚠️ Blocker: the backend needs a host first

Vercel hosts only the Next.js frontend. The **FastAPI backend** (`backend/main.py`)
must be deployed somewhere (Render / Railway / Fly / a VM) before the deployed
frontend is usable, because:

1. `NEXT_PUBLIC_API_URL` must point at that backend over **HTTPS** (browsers block
   mixed content; SSE works fine over HTTPS).
2. The backend's `FRONTEND_ORIGIN` env var must include the Vercel domain, or CORS
   will block the browser. It currently defaults to `http://localhost:3000`.
   Set `FRONTEND_ORIGIN=https://<your-vercel-domain>` on the backend host.
3. The backend host needs `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (+ `WANDB_API_KEY`,
   `ANTHROPIC_API_KEY`) set. Auth turns on automatically once `SUPABASE_URL` is set.

Until the backend is hosted, a Vercel deploy will load the login screen but API
calls will fail. For local end-to-end, `NEXT_PUBLIC_API_URL=http://localhost:8000`
already works against `uvicorn backend.main:app`.

## Supabase dashboard settings to set (important)

- **Auth → Providers → Email:** ensure Email is enabled. For a hackathon, **turn OFF
  "Confirm email"** so `signUp` signs the user in immediately. If it's ON, new users
  can't sign in until they click an email link (our UI shows a "check your inbox"
  notice for that case).
- **Auth → URL Configuration:** add the Vercel production URL to **Site URL** /
  **Redirect URLs** (needed for email confirmation/password-reset links later; not
  required for plain password sign-in).
- RLS is already enabled on all tables (`backend/db/migrations.sql`); the backend
  uses the service key and bypasses it, while RLS protects any direct anon-key access.

## Next frontend work (WS-C, not done here)

The app is "boardroom-lite" (`app/page.tsx`). The auth/data plumbing is complete;
remaining UI work is the Boardroom + Inspector + InfluenceGraph + VerdictPanel +
HITL re-run per `ROADMAP.md` §6. All API calls already carry auth automatically, so
new calls just use the `api` object in `frontend/lib/api.ts`.
