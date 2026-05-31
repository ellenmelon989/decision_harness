// A self-contained sample debate. Powers the no-login "?demo" / replay mode
// (great for showing judges the full UI without spinning up a live LLM run) and
// is the fixture used to verify every panel renders. Shapes match §5 / §7.
import type { Agent, DHEvent, Org, Verdict } from "./types";

export const MOCK_ORG: Org = {
  id: "org-demo",
  name: "Judge Panel",
  description: "A four-seat council weighing technical merit, feasibility, risk, and upside.",
  preset: "judges",
};

export const MOCK_AGENTS: Agent[] = [
  { id: "a1", org_id: "org-demo", name: "The Architect", role: "Systems & Technical Merit", system_prompt: "", model: "claude-opus-4-8", provider: "anthropic", weight: 1.4, tools: ["research"], position: 0, structural: false, veto: false },
  { id: "a2", org_id: "org-demo", name: "The Pragmatist", role: "Product & Feasibility", system_prompt: "", model: "claude-sonnet-4-6", provider: "anthropic", weight: 1.0, tools: ["company_data"], position: 1, structural: false, veto: false },
  { id: "a3", org_id: "org-demo", name: "The Skeptic", role: "Risk & Red Team", system_prompt: "", model: "meta-llama/Llama-3.1-8B-Instruct", provider: "wandb", weight: 1.2, tools: ["research"], position: 2, structural: true, veto: true },
  { id: "a4", org_id: "org-demo", name: "The Visionary", role: "Strategy & Upside", system_prompt: "", model: "claude-sonnet-4-6", provider: "anthropic", weight: 0.9, tools: [], position: 3, structural: false, veto: false },
];

export const MOCK_QUESTION = "Should this project win Most Sophisticated Harness?";

let seq = 0;
const ev = (e: Partial<DHEvent> & { type: DHEvent["type"]; content: any }): DHEvent => ({
  id: `e${++seq}`,
  session_id: "s-demo",
  seq,
  round: 0,
  agent_id: null,
  parent_event: null,
  influenced_by: [],
  ...e,
});

export const MOCK_EVENTS: DHEvent[] = [
  // Round 0 — opening positions
  ev({ type: "position", agent_id: "a1", round: 0, content: { stance: "YES", score: 9, confidence: 0.86, rationale: "Claude Agent SDK subagents over N rounds with peer requests and a weighted orchestrator — this is real orchestration, not a prompt chain." } }),
  ev({ type: "position", agent_id: "a2", round: 0, content: { stance: "CONDITIONAL", score: 6, confidence: 0.7, rationale: "Strong, but does it actually run end-to-end under demo conditions? Streaming + persistence must hold." } }),
  ev({ type: "position", agent_id: "a3", round: 0, content: { stance: "NO", score: 3, confidence: 0.65, rationale: "Sophistication ≠ utility. I want evidence the influence graph and verdict aren't theater." } }),
  ev({ type: "position", agent_id: "a4", round: 0, content: { stance: "YES", score: 8, confidence: 0.78, rationale: "A configurable AI org that argues out loud, with a live influence graph, is a genuinely new interface." } }),

  // Round 1 — debate
  ev({ type: "orchestrator", round: 1, content: { action: "continue", conflict_level: 0.6, note: "Wide spread (3–9). Skeptic anchors low; pressure-test the utility claim." } }),
  ev({ type: "thought", agent_id: "a1", round: 1, content: { text: "The Skeptic's bar is groundedness. I should cite the traced ops and MCP tool calls." } }),
  ev({ type: "message", agent_id: "a1", round: 1, content: { text: "Every reasoning step is one events row, every op is @weave.op traced, and agents call real MCP tools. The audit trail IS the utility.", to: "all" } }),
  ev({ type: "peer_request", agent_id: "a3", round: 1, content: { to_agent_id: "a1", question: "Name one decision where the influence graph changed the outcome — not just decorated it." } }),
  ev({ type: "tool_call", agent_id: "a1", round: 1, content: { tool: "research", args: { query: "weighted orchestrator conflict detection convergence" } } }),
  ev({ type: "tool_result", agent_id: "a1", round: 1, parent_event: "e9", content: { tool: "research", result: "Found: re-run with Skeptic weight +0.4 flipped a CONDITIONAL verdict to NO — influence ranking surfaced the CFO as pivotal." } }),
  ev({ type: "peer_response", agent_id: "a1", round: 1, parent_event: "e8", content: { to_agent_id: "a3", answer: "Re-run with your weight raised flips the verdict, and the graph names who moved the room. That's causal, not cosmetic." } }),
  ev({ type: "message", agent_id: "a2", round: 1, content: { text: "I watched a full run stream without dropping events and persist to Postgres. Feasibility concern retired.", to: "all" } }),

  // Round 1 — positions move
  ev({ type: "position_update", agent_id: "a3", round: 1, influenced_by: ["a1", "a2"], content: { stance: "CONDITIONAL", score: 6, confidence: 0.74, rationale: "The re-run-flips-verdict demo answers groundedness. Moving up, conditional on it holding live." } }),
  ev({ type: "position_update", agent_id: "a2", round: 1, influenced_by: ["a1"], content: { stance: "YES", score: 8, confidence: 0.82, rationale: "Traced + persisted + streamed end to end. Upgrading to YES." } }),

  // Round 2 — convergence
  ev({ type: "orchestrator", round: 2, content: { action: "continue", conflict_level: 0.3, note: "Converging. Skeptic is the swing seat; one more round to settle." } }),
  ev({ type: "message", agent_id: "a4", round: 2, content: { text: "The voice boardroom + influence graph is the memorable bit. Sophistication you can watch.", to: "all" } }),
  ev({ type: "thought", agent_id: "a3", round: 2, content: { text: "They produced the causal artifact I asked for. My remaining doubt is demo fragility, not design." } }),
  ev({ type: "position_update", agent_id: "a3", round: 2, influenced_by: ["a1", "a4"], content: { stance: "YES", score: 8, confidence: 0.8, rationale: "Convinced on merit. The harness earns 'sophisticated' — the audit trail makes it defensible." } }),
  ev({ type: "position_update", agent_id: "a1", round: 2, influenced_by: [], content: { stance: "YES", score: 9, confidence: 0.9, rationale: "Position holds; the room converged on the evidence." } }),
  ev({ type: "orchestrator", round: 2, content: { action: "converge", conflict_level: 0.12, note: "Consensus reached. Rendering verdict." } }),
];

export const MOCK_VERDICT: Verdict = {
  decision: "YES",
  weighted_score: 8.6,
  confidence: 0.85,
  summary:
    "The council converges on YES. The harness demonstrates genuine multi-agent orchestration — N-round debate, peer questioning, MCP tool use, and a weighted orchestrator — and crucially makes it inspectable: every step is a traced event, and the influence graph plus re-run show the verdict is causal, not cosmetic. The Skeptic moved from NO(3) to YES(8) on the evidence.",
  key_agreements: [
    "Every reasoning step is a persisted, Weave-traced event — a real audit trail.",
    "Re-running with adjusted weights flips the verdict, proving the council is causal.",
    "The live influence graph answers 'who swayed the room?' concretely.",
  ],
  key_conflicts: [
    { between: ["a1", "a3"], issue: "Whether sophistication translates into utility or is demo theater." },
  ],
  dissenting_opinions: [
    { agent_id: "a3", stance: "YES", why: "Now persuaded, but flags live-demo fragility as the one residual risk." },
  ],
  // Matches the client-side §8 derivation from MOCK_EVENTS (Σ outgoing / total
  // movement) so the ruling and the influence graph agree to the eye.
  influence_ranking: [
    { agent_id: "a1", influence: 1.0 },
    { agent_id: "a2", influence: 0.43 },
    { agent_id: "a4", influence: 0.29 },
  ],
};
