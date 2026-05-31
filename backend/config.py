"""Central settings, read from backend/.env and the process environment.

Everything degrades gracefully: the app boots even when keys are missing so
the team can run `GET /health` on day one before all accounts are provisioned.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

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
    inference_model: str = "meta-llama/Llama-3.1-8B-Instruct"

    # --- Supabase (Postgres + Auth) ---
    supabase_url: str = ""
    supabase_service_key: str = ""                 # server-side only
    supabase_jwt_secret: str = ""                  # to verify frontend JWTs

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"

    # --- Auth posture ---
    # Local dev only: allow requests with no Authorization header (treated as the
    # demo user). IGNORED once auth_enabled (a JWT secret is set) — then a valid
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
    def auth_enabled(self) -> bool:
        return bool(self.supabase_jwt_secret)

    @property
    def cors_origins(self) -> list[str]:
        return list({self.frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"})


@lru_cache
def get_settings() -> Settings:
    return Settings()
