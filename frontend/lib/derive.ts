// Pure selectors that turn the raw event stream (§5) into the view state the
// Boardroom / Inspector / Influence graph render. Keeping this side-effect-free
// makes the UI a thin projection of the events table — the "inspectable" promise.
import type { Agent, DHEvent, Stance } from "./types";

export interface AgentState {
  stance?: Stance;
  score?: number;
  confidence?: number;
  rationale?: string;
  message?: string; // latest public argument
  thought?: string; // latest private reasoning
  delta?: number; // last score change (signed), for the "moved" animation
  speaking?: boolean; // emitted something in the most recent event
  toolCount: number;
}

export interface Thread {
  request: DHEvent;
  response?: DHEvent;
}

export interface Board {
  byAgent: Record<string, AgentState>;
  round: number; // highest round seen
  threads: Thread[]; // peer Q&A
  lastNote?: string; // latest orchestrator note
  conflict?: number; // latest orchestrator conflict_level
  speakingAgentId?: string; // agent behind the most recent utterance
}

const isPosition = (t: string) => t === "position" || t === "position_update";

export function deriveBoard(events: DHEvent[], agents: Agent[]): Board {
  const byAgent: Record<string, AgentState> = {};
  for (const a of agents) byAgent[a.id] = { toolCount: 0 };
  const ensure = (id?: string | null): AgentState | undefined => {
    if (!id) return undefined;
    return (byAgent[id] ??= { toolCount: 0 });
  };

  let round = 0;
  let lastNote: string | undefined;
  let conflict: number | undefined;
  let speakingAgentId: string | undefined;
  const requests: Record<string, DHEvent> = {}; // event id -> peer_request
  const responses: Record<string, DHEvent> = {}; // parent request id -> response
  const order: string[] = []; // request ids in arrival order

  for (const e of events) {
    if (typeof e.round === "number") round = Math.max(round, e.round);
    const st = ensure(e.agent_id);

    switch (e.type) {
      case "position":
      case "position_update": {
        if (!st) break;
        const prev = st.score;
        st.stance = e.content.stance as Stance;
        st.score = e.content.score;
        st.confidence = e.content.confidence;
        st.rationale = e.content.rationale;
        if (typeof prev === "number" && typeof st.score === "number")
          st.delta = +(st.score - prev).toFixed(2);
        break;
      }
      case "message":
        if (st) st.message = e.content.text;
        speakingAgentId = e.agent_id ?? speakingAgentId;
        break;
      case "thought":
        if (st) st.thought = e.content.text;
        break;
      case "tool_call":
        if (st) st.toolCount += 1;
        break;
      case "peer_request":
        requests[e.id] = e;
        order.push(e.id);
        break;
      case "peer_response":
        if (e.parent_event) responses[e.parent_event] = e;
        break;
      case "orchestrator":
        lastNote = e.content.note;
        conflict = e.content.conflict_level;
        break;
    }
  }

  // mark the most recent speaker
  if (speakingAgentId && byAgent[speakingAgentId]) byAgent[speakingAgentId].speaking = true;

  const threads: Thread[] = order.map((id) => ({ request: requests[id], response: responses[id] }));
  return { byAgent, round, threads, lastNote, conflict, speakingAgentId };
}

export interface GraphNode { id: string; name: string; weight: number; influence: number; stance?: Stance }
export interface GraphLink { source: string; target: string; weight: number }
export interface Graph { nodes: GraphNode[]; links: GraphLink[] }

/**
 * Live, client-side influence graph derived from the stream (§8), so the graph
 * animates during the debate instead of only after the /influence endpoint.
 * Edge A→B when B's position_update lists A in `influenced_by`; edge weight is
 * |Δ score of B that round|, summed. influence(A) = Σ outgoing / total movement.
 */
export function deriveInfluence(events: DHEvent[], agents: Agent[]): Graph {
  const agentIds = new Set(agents.map((a) => a.id));
  const eventAgent: Record<string, string> = {}; // event id -> emitting agent id
  for (const e of events) if (e.agent_id) eventAgent[e.id] = e.agent_id;

  const lastScore: Record<string, number> = {};
  const edge: Record<string, number> = {}; // "A->B" -> summed weight
  let totalMovement = 0;

  for (const e of events) {
    if (!isPosition(e.type) || !e.agent_id) continue;
    const b = e.agent_id;
    const score = e.content.score;
    const prev = lastScore[b];
    const delta = typeof prev === "number" && typeof score === "number" ? Math.abs(score - prev) : 0;
    if (typeof score === "number") lastScore[b] = score;
    if (delta <= 0) continue;
    totalMovement += delta;
    for (const raw of e.influenced_by ?? []) {
      // influenced_by may carry agent ids or event ids — resolve both to an agent.
      const a = agentIds.has(raw) ? raw : eventAgent[raw];
      if (!a || a === b) continue;
      edge[`${a}->${b}`] = (edge[`${a}->${b}`] ?? 0) + delta;
    }
  }

  const outgoing: Record<string, number> = {};
  for (const key in edge) {
    const [a] = key.split("->");
    outgoing[a] = (outgoing[a] ?? 0) + edge[key];
  }

  const stanceByAgent = deriveBoard(events, agents).byAgent;
  const nodes: GraphNode[] = agents.map((a) => ({
    id: a.id,
    name: a.name,
    weight: a.weight,
    influence: totalMovement > 0 ? +((outgoing[a.id] ?? 0) / totalMovement).toFixed(3) : 0,
    stance: stanceByAgent[a.id]?.stance,
  }));
  const links: GraphLink[] = Object.entries(edge).map(([key, weight]) => {
    const [source, target] = key.split("->");
    return { source, target, weight };
  });
  return { nodes, links };
}
