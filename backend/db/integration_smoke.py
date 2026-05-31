"""End-to-end authenticated smoke test against the LIVE Supabase project.

Mints real Supabase JWTs for two throwaway users (via the admin API), then drives
the full authenticated flow through the in-process app and asserts tenant isolation:

    login → JWKS auth → ensure-seed → create org → run debate → persist → IDOR check

Requires real creds (backend/.env SUPABASE_URL/SERVICE_KEY + an anon key) and makes
~10 live LLM calls, so it's a MANUAL smoke, not a CI test. Cleans up after itself.

    python -m backend.db.integration_smoke
"""
from __future__ import annotations

import base64
import json
import time

import httpx
from dotenv import dotenv_values

from .repository import SupabaseRepository, get_repo

PW = "Str0ng-pw-123!"


def _config() -> tuple[str, str, str]:
    be = dotenv_values("backend/.env")
    fe = dotenv_values("frontend/.env.local")
    url = be.get("SUPABASE_URL")
    service = be.get("SUPABASE_SERVICE_KEY")
    anon = be.get("SUPABASE_ANON_KEY") or fe.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not (url and service and anon):
        raise SystemExit("Need SUPABASE_URL + SUPABASE_SERVICE_KEY (backend/.env) and an "
                         "anon key (backend/.env SUPABASE_ANON_KEY or frontend/.env.local).")
    return url, service, anon


def _jwt_alg(token: str) -> str:
    return json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "==")).get("alg")


def main() -> None:
    url, service, anon = _config()
    admin_h = {"apikey": service, "Authorization": f"Bearer {service}"}

    def create_user(email: str) -> str:
        r = httpx.post(f"{url}/auth/v1/admin/users", headers=admin_h,
                       json={"email": email, "password": PW, "email_confirm": True}, timeout=30)
        r.raise_for_status()
        return r.json()["id"]

    def token_for(email: str) -> str:
        r = httpx.post(f"{url}/auth/v1/token?grant_type=password",
                       headers={"apikey": anon, "Content-Type": "application/json"},
                       json={"email": email, "password": PW}, timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]

    ts = str(int(time.time()))
    a_email, b_email = f"dh-a-{ts}@example.com", f"dh-b-{ts}@example.com"
    uid_a, uid_b = create_user(a_email), create_user(b_email)
    tok_a, tok_b = token_for(a_email), token_for(b_email)
    ha, hb = {"Authorization": f"Bearer {tok_a}"}, {"Authorization": f"Bearer {tok_b}"}
    print(f"created 2 users; token alg = {_jwt_alg(tok_a)}")

    from fastapi.testclient import TestClient

    from ..main import app

    try:
        with TestClient(app) as c:
            assert c.get("/orgs").status_code == 401, "no-token should be 401"
            assert c.get("/orgs", headers=ha).status_code == 200, "real token should auth"
            orgs = c.post("/orgs/ensure-seed", headers=ha).json()
            assert orgs, "ensure-seed should return at least one org"
            org = orgs[0]
            print(f"ensure-seed → {[o['name'] for o in orgs]}")

            sid = c.post("/sessions", headers=ha,
                         json={"org_id": org["id"], "question": "Should this win?", "rounds": 1}
                         ).json()["session_id"]
            for _ in range(180):
                if c.get(f"/sessions/{sid}", headers=ha).json()["session"]["status"] in ("done", "error"):
                    break
                time.sleep(0.5)
            d = c.get(f"/sessions/{sid}", headers=ha).json()
            assert d["session"]["status"] == "done", f"debate status {d['session']['status']}"
            assert d["verdict"], "verdict should be persisted"
            print(f"debate → done · {len(d['events'])} events · verdict {d['verdict']['decision']}")

            assert c.get(f"/sessions/{sid}", headers=hb).status_code == 404, "IDOR: B must not read A"
            assert len(c.get("/orgs", headers=hb).json()) == 0, "tenant isolation: B sees no orgs"
            print("IDOR + tenant isolation enforced ✓")
        print("✓ ALL CHECKS PASSED")
    finally:
        repo = get_repo()
        for uid in (uid_a, uid_b):
            if isinstance(repo, SupabaseRepository):
                try:
                    repo.c.table("orgs").delete().eq("owner_id", uid).execute()
                except Exception:
                    pass
            httpx.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_h, timeout=30)
        print("cleaned up test users + orgs")


if __name__ == "__main__":
    main()
