"use client";
// The Record — every reasoning step as one row (§5), threaded by parent_event
// (peer answers under questions, tool results under calls), filterable by kind.
// This is the "inspectable" promise made visible.
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";

import type { Agent, DHEvent, EventType } from "../lib/types";
import { Eyebrow, cx, hueFor } from "./ui";

type Cat = "positions" | "arguments" | "peer" | "tools" | "reasoning" | "flow";
const CAT_OF: Record<EventType, Cat> = {
  position: "positions", position_update: "positions",
  message: "arguments",
  peer_request: "peer", peer_response: "peer",
  tool_call: "tools", tool_result: "tools",
  thought: "reasoning",
  orchestrator: "flow", verdict: "flow", error: "flow", done: "flow",
};
const CAT_COLOR: Record<Cat, string> = {
  positions: "var(--ember)", arguments: "var(--text)", peer: "#86b8a0",
  tools: "#c9b04a", reasoning: "var(--text-faint)", flow: "var(--cond)",
};
const FILTERS: { key: Cat | "all"; label: string }[] = [
  { key: "all", label: "all" }, { key: "positions", label: "positions" },
  { key: "arguments", label: "arguments" }, { key: "peer", label: "peer Q&A" },
  { key: "tools", label: "tools" }, { key: "reasoning", label: "reasoning" }, { key: "flow", label: "flow" },
];

export function Inspector({ events, agents }: { events: DHEvent[]; agents: Agent[] }) {
  const [filter, setFilter] = useState<Cat | "all">("all");
  const scroller = useRef<HTMLDivElement>(null);
  const meta = useMemo(() => {
    const m: Record<string, { name: string; hue: string }> = {};
    agents.forEach((a, i) => (m[a.id] = { name: a.name, hue: hueFor(i) }));
    return m;
  }, [agents]);

  const shown = filter === "all" ? events : events.filter((e) => CAT_OF[e.type] === filter);

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  return (
    <section className="panel" style={{ display: "flex", flexDirection: "column", maxHeight: 720 }}>
      <div className="panel-head" style={{ flexWrap: "wrap", gap: 10 }}>
        <Eyebrow>The Record · {events.length}</Eyebrow>
        <div className="row wrapflex" style={{ gap: 6 }}>
          {FILTERS.map((f) => (
            <button key={f.key} className={cx("chip", filter === f.key && "on")} onClick={() => setFilter(f.key)}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div ref={scroller} style={{ overflowY: "auto", padding: "8px 16px 16px" }}>
        {shown.length === 0 && (
          <div className="muted small" style={{ padding: "28px 4px", textAlign: "center" }}>
            No events yet — convene the council to populate the record.
          </div>
        )}
        <AnimatePresence initial={false}>
          {shown.map((e) => (
            <Row key={e.id} e={e} meta={meta} />
          ))}
        </AnimatePresence>
      </div>
    </section>
  );
}

function Row({ e, meta }: { e: DHEvent; meta: Record<string, { name: string; hue: string }> }) {
  const cat = CAT_OF[e.type];
  const color = CAT_COLOR[cat];
  const who = e.agent_id ? meta[e.agent_id] : undefined;
  const threaded = e.type === "peer_response" || e.type === "tool_result";
  const c = e.content ?? {};

  const body = (() => {
    switch (e.type) {
      case "position":
      case "position_update":
        return (
          <span>
            <span className={cx("stance", c.stance)} style={{ marginRight: 7 }}>{c.stance} · {c.score}</span>
            {c.rationale}
            {(e.influenced_by?.length ?? 0) > 0 && (
              <span className="faint small"> · moved by {e.influenced_by.map((id) => meta[id]?.name ?? id).join(", ")}</span>
            )}
          </span>
        );
      case "message": return <span>“{c.text}”</span>;
      case "thought": return <span className="muted" style={{ fontStyle: "italic" }}>{c.text}</span>;
      case "peer_request": return <span>→ asks <b>{meta[c.to_agent_id]?.name ?? "peer"}</b>: {c.question}</span>;
      case "peer_response": return <span>↳ {c.answer}</span>;
      case "tool_call": return <span>⚒ calls <b className="mono">{c.tool}</b>(<span className="faint mono small">{JSON.stringify(c.args)}</span>)</span>;
      case "tool_result": return <span>↳ <b className="mono">{c.tool}</b> → <span className="muted">{String(c.result).slice(0, 220)}</span></span>;
      case "orchestrator": return <span className="muted">{c.action?.toUpperCase()} · conflict {c.conflict_level} — {c.note}</span>;
      case "verdict": return <span style={{ color: "var(--ember)" }}>⚖ verdict rendered</span>;
      case "error": return <span style={{ color: "var(--no)" }}>{c.message ?? "error"}</span>;
      default: return <span className="faint">{JSON.stringify(c).slice(0, 160)}</span>;
    }
  })();

  return (
    <motion.div
      layout initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      style={{
        display: "grid", gridTemplateColumns: "44px 1fr", gap: 10, padding: "7px 0",
        marginLeft: threaded ? 26 : 0, borderTop: "1px solid var(--line)",
      }}
    >
      <div className="mono small faint tnum" style={{ paddingTop: 1 }}>r{e.round}·{e.seq}</div>
      <div style={{ borderLeft: `2px solid ${color}`, paddingLeft: 11, minWidth: 0 }}>
        <div className="row" style={{ gap: 7, marginBottom: 2 }}>
          {who && <span className="dot" style={{ background: who.hue, width: 6, height: 6 }} />}
          <span className="eyebrow" style={{ fontSize: 9, color }}>
            {e.type}{who ? ` · ${who.name}` : ""}
          </span>
        </div>
        <div className="small" style={{ lineHeight: 1.5 }}>{body}</div>
      </div>
    </motion.div>
  );
}
