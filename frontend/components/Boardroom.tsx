"use client";
// The council in session. One seat per agent: live stance + score, the latest
// public argument streaming in, private reasoning on tap, and a "speaking" glow
// on whoever just took the floor.
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import type { AgentState, Board } from "../lib/derive";
import type { Agent } from "../lib/types";
import { Eyebrow, Monogram, ScoreMeter, StanceBadge, cx, hueFor } from "./ui";

const PROVIDER = (p: string) => (p === "wandb" ? "W&B Inference" : "Claude");
const shortModel = (m: string) => m.split("/").pop()?.replace(/-\d{8}$/, "") ?? m;

function Delta({ d }: { d?: number }) {
  if (!d) return null;
  const up = d > 0;
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }}
      className="mono small" style={{ color: up ? "var(--yes)" : "var(--no)", fontWeight: 700 }}
    >
      {up ? "▲" : "▼"}{Math.abs(d).toFixed(1)}
    </motion.span>
  );
}

function Seat({ agent, hue, state }: { agent: Agent; hue: string; state: AgentState }) {
  const [showThought, setShowThought] = useState(false);
  const speaking = !!state.speaking;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26 }}
      className="panel panel-pad"
      style={{
        display: "flex", flexDirection: "column", gap: 12,
        borderColor: speaking ? "color-mix(in srgb, var(--ember) 50%, var(--line))" : "var(--line)",
        boxShadow: speaking
          ? "var(--shadow), 0 0 0 1px color-mix(in srgb, var(--ember) 35%, transparent), 0 0 34px -10px var(--ember)"
          : "var(--shadow)",
        transition: "box-shadow .4s ease, border-color .4s ease",
      }}
    >
      <div className="row between" style={{ alignItems: "flex-start", gap: 10 }}>
        <div className="row" style={{ gap: 11, alignItems: "center", minWidth: 0 }}>
          <Monogram name={agent.name} hue={hue} />
          <div style={{ minWidth: 0 }}>
            <div className="serif" style={{ fontSize: 17, lineHeight: 1.1, display: "flex", gap: 7, alignItems: "center" }}>
              {agent.name}
              {speaking && <span className="dot live" style={{ width: 6, height: 6 }} />}
            </div>
            <div className="eyebrow" style={{ fontSize: 9.5, marginTop: 3 }}>{agent.role}</div>
          </div>
        </div>
        <div className="row" style={{ gap: 7, alignItems: "center" }}>
          <Delta d={state.delta} />
          <StanceBadge stance={state.stance} score={state.score} />
        </div>
      </div>

      <ScoreMeter score={state.score} stance={state.stance} />

      <div style={{ minHeight: 46 }}>
        <AnimatePresence mode="wait">
          <motion.p
            key={state.message ?? "awaiting"}
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.32 }}
            style={{ margin: 0, fontSize: 13.5, color: state.message ? "var(--text)" : "var(--text-faint)" }}
          >
            {state.message
              ? <>“{state.message}”</>
              : (state.rationale ?? "Awaiting the agent’s opening position…")}
          </motion.p>
        </AnimatePresence>
      </div>

      {state.thought && (
        <div>
          <button
            className="eyebrow" onClick={() => setShowThought((s) => !s)}
            style={{ background: "none", border: 0, padding: 0, cursor: "pointer", color: "var(--text-faint)" }}
          >
            {showThought ? "▾ hide reasoning" : "▸ private reasoning"}
          </button>
          <AnimatePresence>
            {showThought && (
              <motion.div
                initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                style={{ overflow: "hidden" }}
              >
                <p className="small muted" style={{ margin: "8px 0 0", fontStyle: "italic", borderLeft: "2px solid var(--line-2)", paddingLeft: 10 }}>
                  {state.thought}
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      <div className="row between" style={{ borderTop: "1px solid var(--line)", paddingTop: 10, marginTop: "auto" }}>
        <span className="mono small faint" title={agent.model}>
          {PROVIDER(agent.provider)} · {shortModel(agent.model)}
        </span>
        <div className="row" style={{ gap: 12 }}>
          {state.toolCount > 0 && <span className="mono small faint">⚒ {state.toolCount}</span>}
          {typeof state.confidence === "number" && (
            <span className="mono small faint">conf {Math.round(state.confidence * 100)}%</span>
          )}
          <span className="mono small" style={{ color: hue }}>×{agent.weight.toFixed(1)}</span>
        </div>
      </div>
    </motion.div>
  );
}

export function Boardroom({ agents, board }: { agents: Agent[]; board: Board }) {
  return (
    <section>
      <div className="row between" style={{ marginBottom: 12 }}>
        <Eyebrow>The Boardroom · {agents.length} seats</Eyebrow>
        {board.round > 0 && <span className="mono small faint">round {board.round}</span>}
      </div>
      <motion.div
        layout
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))", gap: 14 }}
      >
        {agents.map((a, i) => (
          <Seat key={a.id} agent={a} hue={hueFor(i)} state={board.byAgent[a.id] ?? { toolCount: 0 }} />
        ))}
      </motion.div>
    </section>
  );
}
