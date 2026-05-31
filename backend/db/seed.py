"""Seed the demo 'Judge Panel' org from the repo-root personas/ files.

Each persona file (personas/*.md|*.txt) becomes one agent. The YAML frontmatter
(name / role / weight / position / model / provider / voice_id / tools) configures
the agent; the body BELOW the frontmatter — minus the fenced "demo-prep reference"
block and any HTML comments — becomes the system_prompt.

The demo-prep block is the answer key (predicted scores, natural verdict) and must
never reach the model, so it is stripped here at load time. Files without
frontmatter fall back to filename-derived name + full body as the prompt.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schemas import AgentCreate, Provider

PERSONAS_DIR = Path(__file__).resolve().parents[2] / "personas"

# Everything from this marker down is demo-prep reference, not persona text.
_DEMO_MARKER = "demo-prep reference"
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter dict, body). Only flat scalar keys are read; indented
    continuation lines (e.g. the nested cap_rule mapping) are skipped."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text
    fm: dict[str, str] = {}
    for ln in lines[1:end]:
        if not ln.strip() or ln[0] in " \t" or ":" not in ln:
            continue
        key, _, val = ln.partition(":")
        fm[key.strip()] = _strip_inline_comment(val).strip()
    return fm, "\n".join(lines[end + 1:])


def _strip_inline_comment(val: str) -> str:
    """Drop a trailing ` # ...` YAML comment. A '#' only starts a comment when
    preceded by whitespace (or at the start), so in-value '#' chars are safe."""
    out = []
    for i, ch in enumerate(val):
        if ch == "#" and (i == 0 or val[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out)


def _clean_body(body: str) -> str:
    """Drop the demo-prep block and any HTML comments; the rest is the prompt."""
    kept: list[str] = []
    for ln in body.splitlines():
        if _DEMO_MARKER in ln:
            break
        kept.append(ln)
    return _COMMENT_RE.sub("", "\n".join(kept)).strip()


def _opt(val: str | None) -> str | None:
    if val is None:
        return None
    v = val.strip()
    return None if v.lower() in ("", "null", "none", "~") else v


def _float(val: str | None, default: float) -> float:
    try:
        return float(val) if val not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _int(val: str | None, default: int) -> int:
    try:
        return int(val) if val not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _bool(val: str | None) -> bool:
    return (val or "").strip().lower() in ("true", "yes", "1")


def _tools(val: str | None) -> list[str]:
    if not val:
        return []
    v = val.strip().strip("[]")
    return [p.strip().strip("\"'") for p in v.split(",") if p.strip().strip("\"'")]


def load_personas() -> list[AgentCreate]:
    if not PERSONAS_DIR.exists():
        return []
    agents: list[AgentCreate] = []
    for i, path in enumerate(sorted(PERSONAS_DIR.glob("*"))):
        if path.suffix.lower() not in (".md", ".txt"):
            continue
        fm, body = _split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        kwargs: dict = dict(
            name=fm.get("name") or path.stem.replace("_", " ").title(),
            role=fm.get("role") or "Panelist",
            system_prompt=_clean_body(body),
            weight=_float(fm.get("weight"), 1.0),
            position=_int(fm.get("position"), i),
            tools=_tools(fm.get("tools")),
            structural=_bool(fm.get("structural")),
            # A persona vetoes if it declares `veto: true` or carries a `cap_rule` block.
            veto=_bool(fm.get("veto")) or "cap_rule" in fm,
        )
        if fm.get("model"):
            kwargs["model"] = fm["model"]
        if fm.get("provider"):
            kwargs["provider"] = fm["provider"]
        if _opt(fm.get("voice_id")):
            kwargs["voice_id"] = fm["voice_id"].strip()
        agents.append(AgentCreate(**kwargs))
    return agents


def seed_judge_panel(repo, owner_id: str):
    """Create the 'Hackathon Judge Panel' org + agents. Returns the Org (or None)."""
    personas = load_personas()
    if not personas:
        return None
    org = repo.create_org(owner_id, name="Hackathon Judge Panel",
                          description="The Most Sophisticated Harness judges, modeled as agents.",
                          preset="judges")
    for a in personas:
        repo.create_agent(org.id, a)
    return org
