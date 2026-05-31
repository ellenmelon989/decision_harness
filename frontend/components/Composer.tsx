"use client";
// "Motion on the floor" — choose the council, state the question, convene.
// Surfaces an honest live-session status and a loud (not silent) error state.
import { motion } from "framer-motion";

import type { Org } from "../lib/types";
import type { StreamStatus } from "../lib/useEventStream";
import { Eyebrow } from "./ui";

const STATUS_LABEL: Record<StreamStatus, string> = {
  idle: "idle", connecting: "convening…", open: "in session", done: "verdict in", error: "connection lost",
};

export function Composer({
  orgs, orgId, onOrg, question, onQuestion, rounds, onRounds,
  status, seats, round, note, canRun, onRun, onOpenBuilder, healthError, healthMsg, onRetry,
}: {
  orgs: Org[]; orgId: string; onOrg: (id: string) => void;
  question: string; onQuestion: (q: string) => void;
  rounds: number; onRounds: (r: number) => void;
  status: StreamStatus; seats: number; round: number; note?: string;
  canRun: boolean; onRun: () => void; onOpenBuilder: () => void;
  healthError: boolean; healthMsg: string; onRetry: () => void;
}) {
  const live = status === "open" || status === "connecting";
  const dotClass = status === "error" ? "err" : live ? "live" : status === "done" ? "done" : "";

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.05 }}
      className="panel" style={{ marginTop: 22 }}
    >
      {healthError && (
        <div
          className="row between wrapflex"
          style={{
            gap: 10, padding: "11px 18px", borderBottom: "1px solid var(--line)",
            background: "color-mix(in srgb, var(--no) 10%, transparent)",
            borderTopLeftRadius: "var(--r)", borderTopRightRadius: "var(--r)",
          }}
        >
          <span className="small" style={{ color: "var(--no)" }}>
            Backend unreachable — {healthMsg}. The council can’t convene until the API responds.
          </span>
          <button className="btn btn-ghost btn-sm" onClick={onRetry}>Retry</button>
        </div>
      )}

      <div className="panel-pad" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="row between wrapflex" style={{ gap: 12 }}>
          <Eyebrow>Motion on the floor</Eyebrow>
          <button className="btn btn-ghost btn-sm" onClick={onOpenBuilder}>⊕ Assemble a council</button>
        </div>

        <div className="row wrapflex" style={{ gap: 12, alignItems: "stretch" }}>
          <div className="col" style={{ gap: 5, minWidth: 200 }}>
            <label className="eyebrow" style={{ fontSize: 9.5 }}>Council</label>
            <select value={orgId} onChange={(e) => onOrg(e.target.value)} disabled={!orgs.length}>
              {orgs.length === 0 && <option>no council yet</option>}
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </div>

          <div className="col grow" style={{ gap: 5, minWidth: 260 }}>
            <label className="eyebrow" style={{ fontSize: 9.5 }}>The question</label>
            <input
              className="serif" style={{ fontSize: 18, padding: "11px 14px" }}
              value={question} placeholder="Put a decision to the council…"
              onChange={(e) => onQuestion(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && canRun) onRun(); }}
            />
          </div>

          <div className="col" style={{ gap: 5, width: 86 }}>
            <label className="eyebrow" style={{ fontSize: 9.5 }}>Rounds</label>
            <input
              type="number" min={1} max={6} value={rounds} className="mono tnum"
              onChange={(e) => onRounds(Math.max(1, Math.min(6, +e.target.value || 1)))}
            />
          </div>

          <div className="col" style={{ gap: 5, justifyContent: "flex-end" }}>
            <label className="eyebrow" style={{ fontSize: 9.5, opacity: 0 }}>.</label>
            <button className="btn btn-primary" onClick={onRun} disabled={!canRun} style={{ height: 42 }}>
              {live ? "In session…" : "Convene ▸"}
            </button>
          </div>
        </div>

        <div className="row wrapflex" style={{ gap: 14, alignItems: "center" }}>
          <span className="row small muted" style={{ gap: 7 }}>
            <span className={`dot ${dotClass}`} />
            <span className="mono">{seats} seats · {STATUS_LABEL[status]}</span>
          </span>
          {round > 0 && <span className="mono small faint">round {round}</span>}
          {note && (
            <span className="small muted" style={{ borderLeft: "1px solid var(--line-2)", paddingLeft: 12, fontStyle: "italic" }}>
              orchestrator: {note}
            </span>
          )}
        </div>
      </div>
    </motion.section>
  );
}
