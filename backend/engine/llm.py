"""LLM backends for agents + orchestrator (ROADMAP §7.3).

Provider-routed with graceful degradation:
  • provider "wandb"     -> W&B Inference (OpenAI-compatible, async)
  • provider "anthropic" -> Anthropic Messages API, forced tool-use for structured JSON
  • neither configured   -> resolve_backend() returns None and the caller uses its mock

If an agent's declared provider has no credentials, we fall back to whatever IS
configured (so the panel still runs on, e.g., W&B Inference before Anthropic
credits arrive). Weave auto-traces both SDKs once weave.init has run.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from ..config import get_settings
from ..schemas import Provider

# Anthropic backend can't run a W&B model id, and vice-versa. Safe defaults:
_DEFAULT_ANTHROPIC = "claude-sonnet-4-6"


def available_backends() -> dict[str, bool]:
    s = get_settings()
    return {"wandb": bool(s.wandb_api_key), "anthropic": bool(s.anthropic_api_key)}


def resolve_backend(provider) -> Optional[str]:
    """Pick the backend to actually use for an agent. None → use mock."""
    avail = available_backends()
    p = provider.value if isinstance(provider, Provider) else str(provider)
    if avail.get(p):
        return p
    for cand in ("anthropic", "wandb"):  # prefer Claude, fall back to W&B Inference
        if avail[cand]:
            return cand
    return None


# --- lazy, cached async clients ---
_openai_client = None
_anthropic_client = None


def _wandb_client():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI

        s = get_settings()
        _openai_client = AsyncOpenAI(base_url=s.inference_base_url,
                                     api_key=s.wandb_api_key, project=s.project_path)
    return _openai_client


def _anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic

        _anthropic_client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _anthropic_client


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


async def complete_json(backend: str, model: str, system: str, prompt: str,
                        schema: dict) -> dict:
    """Return a dict matching `schema`. Raises on hard failure (caller falls back)."""
    if backend == "wandb":
        s = get_settings()
        wb_model = model if "/" in model else s.inference_model  # Claude name → use inference model
        sys = (system + "\n\nRespond with ONLY a single JSON object matching this schema "
               "(no prose, no markdown fences):\n" + json.dumps(schema))
        msgs = [{"role": "system", "content": sys}, {"role": "user", "content": prompt}]
        try:  # JSON mode greatly improves validity on models that support it
            resp = await _wandb_client().chat.completions.create(
                model=wb_model, messages=msgs, temperature=0.6,
                response_format={"type": "json_object"})
        except Exception:
            resp = await _wandb_client().chat.completions.create(
                model=wb_model, messages=msgs, temperature=0.6)
        return _extract_json(resp.choices[0].message.content or "")

    if backend == "anthropic":
        an_model = model if model.startswith("claude") else _DEFAULT_ANTHROPIC
        resp = await _anthropic().messages.create(
            model=an_model, max_tokens=1024, system=system,
            tools=[{"name": "submit", "description": "Submit your structured response",
                    "input_schema": schema}],
            tool_choice={"type": "tool", "name": "submit"},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in resp.content:
            if block.type == "tool_use":
                return block.input
        raise RuntimeError("anthropic returned no tool_use block")

    raise ValueError(f"unknown backend: {backend}")
