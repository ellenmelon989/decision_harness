"""Central settings, read from backend/.env and the process environment.

Everything degrades gracefully: the app boots even when keys are missing so
the team can run `GET /health` on day one before all accounts are provisioned.
"""
import re
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always read backend/.env, even when uvicorn is launched from the repo root
# (per START_HERE: `uvicorn backend.main:app`). A bare ".env" would resolve
# against the launch CWD and miss this file. Process env still overrides it.
_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # --- W&B / Weave (already provisioned, see main repo .env) ---
    wandb_api_key: str = ""
    wandb_entity: str = ""
    wandb_project: str = "company-brain-harness"  # existing Weave project

    # --- Models ---
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
             # Claude Agent SDK
    inference_base_url: str = "https://api.inference.wandb.ai/v1"
    # Fallback W&B Inference model for any agent whose own model isn't a W&B id.
    inference_model: str = "openai/gpt-oss-120b"

    # --- Supabase (Postgres + Auth) ---
    supabase_url: str = ""
    supabase_service_key: str = ""                 # server-side only

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"
    # Vercel project + team slugs used to pin the CORS origin regex (see
    # cors_origin_regex). The team slug is reserved to us by Vercel, so pinning
    # it stops a look-alike third-party project from matching.
    frontend_vercel_slug: str = "decisive"
    frontend_vercel_team: str = "yamanns"

    # --- Auth posture ---
    # Local dev only: allow requests with no Authorization header (treated as the
    # demo user). IGNORED once auth_enabled (Supabase is configured) — then a valid
    # token is always required. Set False in any shared/hosted environment.
    dev_unauthenticated: bool = True

    @property
    def project_path(self) -> str:
        return f"{self.wandb_entity}/{self.wandb_project}" if self.wandb_entity else self.wandb_project

    @property
    def weave_enabled(self) -> bool:
        return bool(self.wandb_api_key)

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    @property
    def jwks_url(self) -> str:
        # Supabase publishes its asymmetric (ES256) public signing keys here.
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"

    @property
    def auth_enabled(self) -> bool:
        # Verification is keyed off the project URL: tokens are checked against
        # the project's published JWKS (no shared secret needed).
        return bool(self.supabase_url)

    @property
    def cors_origins(self) -> list[str]:
        return list({self.frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"})

    @property
    def cors_origin_regex(self) -> str:
        # Vercel preview / per-deploy URLs look like
        #   <project>-<hash>-<team>.vercel.app   (e.g. decisive-3hpw9j94q-yamanns.vercel.app)
        # Pin BOTH the project slug and the team slug. The team slug is reserved
        # to us by Vercel, so an attacker who registers a `decisive-*` project
        # under their own team can't produce a matching origin (credentials are
        # allowed, so a loose `*.vercel.app` regex would be a real CORS hole).
        # The clean production alias (e.g. decisiveai.vercel.app, which carries
        # no team segment) is allow-listed exactly via frontend_origin instead.
        slug = re.escape(self.frontend_vercel_slug)
        team = re.escape(self.frontend_vercel_team)
        return rf"https://{slug}[a-z0-9-]*-{team}\.vercel\.app"


@lru_cache
def get_settings() -> Settings:
    return Settings()
