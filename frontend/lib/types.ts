// TypeScript mirror of backend/schemas.py — THE FROZEN CONTRACT (ROADMAP §5-7).
// Keep in sync with the Python models.

export type EventType =
  | "position" | "thought" | "message" | "peer_request" | "peer_response"
  | "tool_call" | "tool_result" | "position_update" | "orchestrator" | "verdict"
  | "error" | "done";

export type Stance = "YES" | "NO" | "CONDITIONAL";
export type Provider = "anthropic" | "wandb";
export type SessionStatus = "pending" | "running" | "done" | "error";

export interface Position {
  stance: Stance; score: number; confidence: number; rationale: string;
}

export interface Agent {
  id: string; org_id: string; name: string; role: string; system_prompt: string;
  model: string; provider: Provider; weight: number; voice_id?: string | null;
  tools: string[]; position: number; structural: boolean; veto: boolean;
  created_at?: string;
}

export interface Org {
  id: string; owner_id?: string | null; name: string;
  description?: string | null; preset?: string | null; created_at?: string;
}

export interface DHEvent {
  id: string; session_id: string; seq: number; round: number;
  agent_id?: string | null; type: EventType; content: Record<string, any>;
  parent_event?: string | null; influenced_by: string[]; created_at?: string;
}

export interface Verdict {
  decision: Stance; weighted_score: number; confidence: number; summary: string;
  key_agreements: string[];
  key_conflicts: { between: string[]; issue: string }[];
  dissenting_opinions: { agent_id: string; stance: Stance; why: string }[];
  influence_ranking: { agent_id: string; influence: number }[];
}

export interface Session {
  id: string; org_id: string; question: string; context?: string | null;
  status: SessionStatus; rounds: number; final_verdict?: Verdict | null;
  weave_trace_url?: string | null; parent_session?: string | null;
  weights_override?: Record<string, number> | null;
}

export interface SessionDetail {
  session: Session; events: DHEvent[];
  positions: Record<string, any>[]; verdict?: Verdict | null;
}

export interface InfluenceGraph {
  nodes: { agent_id: string; name: string; weight: number; influence: number }[];
  edges: { from: string; to: string; weight: number }[];
}
