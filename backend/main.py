"""Decision Harness API (ROADMAP §6).

Boots with or without Supabase/Weave/Anthropic keys so the team can run it on
day one. `GET /health` is the Hour-0 checkpoint. When Supabase isn't configured
the app uses an in-memory store seeded with the Judge Panel org from personas/.
"""
import threading
from contextlib import asynccontextmanager

import weave
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import agents, orgs, sessions
from .api.deps import DEMO_USER_ID
from .config import get_settings
from .db.client import get_supabase
from .db.repository import get_repo
from .db.seed import seed_judge_panel

settings = get_settings()


def _init_weave() -> None:
    try:
        weave.init(settings.project_path)
        print(f"✓ Weave: {settings.project_path}")
    except Exception as exc:
        print(f"! Weave init skipped: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.weave_enabled:
        # Run in a background thread: weave.init() does heavy imports + network
        # auth that would otherwise block uvicorn from serving /health, tripping
        # the platform healthcheck on a cold start. Tracing attaches once it's up.
        threading.Thread(target=_init_weave, daemon=True).start()
    # Auto-seed the demo org into the in-memory store so dev has data immediately.
    if not settings.supabase_enabled:
        org = seed_judge_panel(get_repo(), DEMO_USER_ID)
        if org:
            print(f"✓ Seeded in-memory org '{org.name}' ({org.id})")
    yield


app = FastAPI(title="Decision Harness API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orgs.router)
app.include_router(agents.router)
app.include_router(sessions.router)


@app.get("/health")
def health():
    return {
        "ok": True,
        "weave": settings.weave_enabled,
        "supabase": settings.supabase_enabled,
        "auth": settings.auth_enabled,
        "repo": "supabase" if get_supabase() else "in-memory",
    }
