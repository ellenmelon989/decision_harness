"""Seed the demo 'Judge Panel' org from the repo-root personas/ files.

Each persona file (personas/*.md|*.txt) becomes one agent. We parse the AGENT /
ROLE / SUGGESTED WEIGHT header lines; the full file text is the system prompt.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schemas import AgentCreate, Provider

PERSONAS_DIR = Path(__file__).resolve().parents[2] / "personas"


def _parse(text: str, fallback_name: str) -> tuple[str, str, float]:
    name = role = None
    weight = 1.0
    for line in text.splitlines():
        s = line.strip()
        if not name and s.upper().startswith("AGENT:"):
            name = s.split(":", 1)[1].strip()
        elif not role and s.upper().startswith("ROLE:"):
            role = s.split(":", 1)[1].strip()
        elif s.upper().startswith("SUGGESTED WEIGHT:"):
            m = re.search(r"(\d+(?:\.\d+)?)", s)
            if m:
                v = float(m.group(1))
                weight = v / 100.0 if "%" in s else v
    return (name or fallback_name, role or "Panelist", weight)


def load_personas() -> list[AgentCreate]:
    if not PERSONAS_DIR.exists():
        return []
    agents: list[AgentCreate] = []
    for i, path in enumerate(sorted(PERSONAS_DIR.glob("*"))):
        if path.suffix.lower() not in (".md", ".txt"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        name, role, weight = _parse(text, path.stem.title())
        agents.append(AgentCreate(name=name, role=role, system_prompt=text,
                                  weight=weight, position=i, tools=["research"],
                                  provider=Provider.wandb,
                                  model="llama-3.3-70b-versatile"))
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
