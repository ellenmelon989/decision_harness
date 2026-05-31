"""Prompt fragments + the structured-output schema for an agent turn (ROADMAP §7.3).

WS-A: these feed the Claude Agent SDK calls. The JSON schema is what each agent
must return so we can persist typed events and build the influence graph.
"""

DEBATE_RUBRIC = """
You are one member of a decision-making panel. You have already stated an initial
position. You can now SEE what every other member said. Do exactly one deliberation turn:

1. Make ONE public argument (`message`) — concise, in your own voice, addressing the
   strongest opposing point.
2. Optionally ask ONE peer a direct question (`peer_request`) by their agent_id.
3. Optionally call a tool you have access to, to ground a claim.
4. Re-state your position (`position`): stance (YES/NO/CONDITIONAL), score 0-10,
   confidence 0-1, and a one-line rationale.
5. If a peer's argument changed your score, list their agent_ids in `influenced_by`.
   Be honest — a static panel is a useless panel.

Stay in character. Do not invent facts; use tools or say you're uncertain.
""".strip()

ORCHESTRATOR_PROMPT = """
You are the orchestrator of a decision panel. You are given the full transcript of a
multi-round debate. Produce a structured verdict:
- summary: 2-3 sentences capturing the panel's collective judgment.
- key_agreements: points (nearly) everyone shared.
- key_conflicts: the real disagreements, naming the agents on each side.
- dissenting_opinions: any agent whose final stance differs from the majority, and why.
Do NOT compute the numeric score yourself — that is calculated from weighted votes.
Be neutral and precise; surface conflict rather than smoothing it over.
""".strip()

ORG_BUILDER_PROMPT = """
You design panels of expert AI agents that evaluate decisions together. Given a
domain or panel description, invent 3-5 DISTINCT panelists who would productively
disagree. For each: a realistic name, a specific role/title, and a rich first-person
system_prompt (3-5 sentences) defining their expertise, biases, what they optimize
for, and their voice. Make at least one a skeptic. Assign each a relative weight
(they need not sum to 1 — they'll be normalized). Return JSON only.
""".strip()

ORG_BUILDER_SCHEMA = {
    "type": "object",
    "properties": {
        "org_name": {"type": "string"},
        "description": {"type": "string"},
        "agents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "system_prompt": {"type": "string"},
                    "weight": {"type": "number"},
                },
                "required": ["name", "role", "system_prompt", "weight"],
            },
        },
    },
    "required": ["org_name", "agents"],
}

# Initial (round 0) position.
POSITION_SCHEMA = {
    "type": "object",
    "properties": {
        "stance": {"enum": ["YES", "NO", "CONDITIONAL"]},
        "score": {"type": "number", "minimum": 0, "maximum": 10},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
    },
    "required": ["stance", "score", "confidence", "rationale"],
}

# Orchestrator's natural-language summary (numbers are computed, not asked for).
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_agreements": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "key_agreements"],
}

# Structured output each agent must return per deliberation turn.
AGENT_TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "peer_request": {
            "type": ["object", "null"],
            "properties": {
                "to_agent_id": {"type": "string"},
                "question": {"type": "string"},
            },
            "required": ["to_agent_id", "question"],
        },
        "tool_call": {
            "type": ["object", "null"],
            "properties": {
                "tool": {"type": "string"},
                "args": {"type": "object"},
            },
            "required": ["tool", "args"],
        },
        "position": {
            "type": "object",
            "properties": {
                "stance": {"enum": ["YES", "NO", "CONDITIONAL"]},
                "score": {"type": "number", "minimum": 0, "maximum": 10},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string"},
            },
            "required": ["stance", "score", "confidence", "rationale"],
        },
        "influenced_by": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["message", "position", "influenced_by"],
}
