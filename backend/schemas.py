"""THE FROZEN CONTRACT (ROADMAP §5-7).

Every workstream codes against these models. Do not change a field name without
announcing it to the team — this is the seam between backend, frontend, engine,
and voice. Mirrored in TypeScript at frontend/lib/types.ts.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ───────────────────────── enums ─────────────────────────
class EventType(str, Enum):
    position = "position"                 # round 0 independent stance
    thought = "thought"                   # private reasoning summary
    message = "message"                   # public argument (this is what gets spoken)
    peer_request = "peer_request"         # direct question to a peer
    peer_response = "peer_response"       # answer (parent_event = the request)
    tool_call = "tool_call"
    tool_result = "tool_result"           # parent_event = the call
    position_update = "position_update"   # carries influenced_by
    orchestrator = "orchestrator"         # control: start/continue/converge
    verdict = "verdict"                   # final verdict object


class Stance(str, Enum):
    YES = "YES"
    NO = "NO"
    CONDITIONAL = "CONDITIONAL"


class Provider(str, Enum):
    anthropic = "anthropic"
    wandb = "wandb"                       # W&B Inference (open models)


class SessionStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    error = "error"


# ───────────────────── core domain models ─────────────────────
class Position(BaseModel):
    stance: Stance
    score: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""


class Conflict(BaseModel):
    between: list[str]                    # agent_ids
    issue: str


class Dissent(BaseModel):
    agent_id: str
    stance: Stance
    why: str


class InfluenceScore(BaseModel):
    agent_id: str
    influence: float = Field(ge=0, le=1)


class Verdict(BaseModel):
    decision: Stance
    weighted_score: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    summary: str = ""
    key_agreements: list[str] = []
    key_conflicts: list[Conflict] = []
    dissenting_opinions: list[Dissent] = []
    influence_ranking: list[InfluenceScore] = []


class Agent(BaseModel):
    id: str
    org_id: str
    name: str
    role: str
    system_prompt: str
    model: str = "openai/gpt-oss-120b"
    provider: Provider = Provider.wandb
    weight: float = 1.0
    voice_id: Optional[str] = None
    tools: list[str] = []
    position: int = 0                     # seat order in the boardroom
    structural: bool = False              # cannot be removed/re-weighted away (e.g. the Skeptic)
    veto: bool = False                    # blocks a clean YES unless it too is convinced
    created_at: Optional[datetime] = None


class Org(BaseModel):
    id: str
    owner_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    preset: Optional[str] = None          # 'vc' | 'board' | 'judges'
    created_at: Optional[datetime] = None


class Event(BaseModel):
    id: str
    session_id: str
    seq: int                              # global order within session
    round: int
    agent_id: Optional[str] = None        # null for orchestrator events
    type: EventType
    content: dict[str, Any]               # type-specific payload (see ROADMAP §5)
    parent_event: Optional[str] = None
    influenced_by: list[str] = []
    created_at: Optional[datetime] = None


class Session(BaseModel):
    id: str
    org_id: str
    created_by: Optional[str] = None
    question: str
    context: Optional[str] = None
    weights_override: Optional[dict[str, float]] = None
    status: SessionStatus = SessionStatus.pending
    rounds: int = 3
    final_verdict: Optional[Verdict] = None
    weave_trace_url: Optional[str] = None
    parent_session: Optional[str] = None
    created_at: Optional[datetime] = None


# ───────────────────── API request / response ─────────────────────
class CreateOrgRequest(BaseModel):
    name: str
    description: Optional[str] = None
    preset: Optional[str] = None


class GenerateOrgRequest(BaseModel):
    prompt: str                           # "a biotech seed investment committee"


class AgentCreate(BaseModel):
    name: str
    role: str
    system_prompt: str
    # Default to W&B Inference; the council runs entirely on open models (no Anthropic).
    model: str = "openai/gpt-oss-120b"
    provider: Provider = Provider.wandb
    weight: float = 1.0
    voice_id: Optional[str] = None
    tools: list[str] = []
    position: int = 0
    structural: bool = False
    veto: bool = False


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[Provider] = None
    weight: Optional[float] = None
    voice_id: Optional[str] = None
    tools: Optional[list[str]] = None
    position: Optional[int] = None
    structural: Optional[bool] = None
    veto: Optional[bool] = None


class CreateSessionRequest(BaseModel):
    org_id: str
    question: str
    context: Optional[str] = None
    rounds: int = 3


class CreateSessionResponse(BaseModel):
    session_id: str


class RerunRequest(BaseModel):
    weights_override: Optional[dict[str, float]] = None
    context: Optional[str] = None


class SessionDetail(BaseModel):
    session: Session
    events: list[Event] = []
    positions: list[dict[str, Any]] = []  # rows from `positions` table
    verdict: Optional[Verdict] = None


class InfluenceNode(BaseModel):
    agent_id: str
    name: str
    weight: float
    influence: float


class InfluenceEdge(BaseModel):
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    weight: float

    model_config = {"populate_by_name": True}


class InfluenceGraph(BaseModel):
    nodes: list[InfluenceNode] = []
    edges: list[InfluenceEdge] = []
