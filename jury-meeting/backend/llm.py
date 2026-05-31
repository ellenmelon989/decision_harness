"""W&B Inference client (OpenAI-compatible), auto-traced by Weave.

Weave patches the `openai` client at import/init time, so every chat call made
through here shows up as a child span under whatever @weave.op is on the stack.
"""
from __future__ import annotations

import os
from functools import lru_cache

import openai
from dotenv import load_dotenv

load_dotenv()

WANDB_BASE_URL = "https://api.inference.wandb.ai/v1"

# Team-shared config (matches the other team's .env so traces land in one project).
WANDB_ENTITY = os.getenv("WANDB_ENTITY", "yamanbicer-mindra")
WANDB_PROJECT = os.getenv("WANDB_PROJECT", "company-brain-harness")
PROJECT_PATH = f"{WANDB_ENTITY}/{WANDB_PROJECT}"
DEFAULT_MODEL = os.getenv("WANDB_INFERENCE_MODEL", "meta-llama/Llama-3.1-8B-Instruct")


@lru_cache(maxsize=1)
def _client() -> openai.OpenAI:
    api_key = os.getenv("WANDB_API_KEY")
    if not api_key:
        raise RuntimeError(
            "WANDB_API_KEY is not set. Copy backend/.env.example to backend/.env "
            "and add your key from https://wandb.ai/authorize"
        )
    # `project` routes the inference usage to the right W&B project.
    return openai.OpenAI(base_url=WANDB_BASE_URL, api_key=api_key, project=PROJECT_PATH)


def chat(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.6,
    max_tokens: int = 600,
) -> str:
    """Single-shot system+user completion, returns the assistant text."""
    resp = _client().chat.completions.create(
        model=model or DEFAULT_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()
