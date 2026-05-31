"use client";
// The chair's controls (§14 step 5): drag a seat's voting weight, inject a new
// constraint, and re-run — spawning a child session whose verdict can flip.
import { motion } from "framer-motion";

import type { Agent } from "../lib/types";
import { Eyebrow, Monogram, cx, hueFor } from "./ui";

const MAX = 3;

export function HITL({
  agents, weights, onWeight, context, onContext, onRerun, rerunning, enabled,
}: {
  agents: Agent[];
  weights: Record<string, number>;
  onWeight: (id: string, w: number) => void;
  context: string;
  onContext: (c: string) => void;
  onRerun: () => void;
  rerunning: boolean;
  enabled: boolean;
}) {
  const changed = agents.some((a) => Math.abs((weights[a.id] ?? a.weight) - a.weight) > 0.001) || context.trim().length > 0;

  return (
    <section className="panel" style={{ display: "flex", flexDirection: "column" }}>
      <div className="panel-head">
        <Eyebrow>Chair’s controls · re-run the room</Eyebrow>
        {changed && <span className="mono small" style={{ color: "var(--ember)" }}>● unsaved</span>}
      </div>

      <div className="panel-pad" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="col" style={{ gap: 13 }}>
          {agents.map((a, i) => {
            const w = weights[a.id] ?? a.weight;
            const hue = hueFor(i);
            return (
              <div key={a.id} className="row" style={{ gap: 12, alignItems: "center" }}>
                <Monogram name={a.name} hue={hue} size={28} />
                <div className="grow" style={{ minWidth: 0 }}>
                  <div className="row between" style={{ marginBottom: 3 }}>
                    <span className="small" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.name}</span>
                    <span className="mono small tnum" style={{ color: hue }}>×{w.toFixed(1)}</span>
                  </div>
                  <input
                    type="range" min={0} max={MAX} step={0.1} value={w}
                    style={{ ["--range-fill" as any]: `${(w / MAX) * 100}%` }}
                    onChange={(e) => onWeight(a.id, +e.target.value)}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <div className="col" style={{ gap: 5 }}>
          <label className="eyebrow" style={{ fontSize: 9.5 }}>Inject a constraint</label>
          <textarea
            rows={2} value={context} placeholder="e.g. “Assume a recession and a 6-month runway.”"
            onChange={(e) => onContext(e.target.value)} style={{ resize: "vertical" }}
          />
        </div>

        <div className="row between wrapflex" style={{ gap: 10 }}>
          <span className="small faint">
            {enabled ? "Re-running spawns a child session with these weights." : "Run a debate first to enable re-runs."}
          </span>
          <motion.button
            whileTap={{ scale: 0.97 }}
            className={cx("btn", "btn-primary")} onClick={onRerun} disabled={!enabled || rerunning}
          >
            {rerunning ? "Re-running…" : "↻ Re-run the council"}
          </motion.button>
        </div>
      </div>
    </section>
  );
}
