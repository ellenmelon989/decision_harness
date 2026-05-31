"use client";
// The ruling. A formal decree: the decision, the weighted score, then the
// reasoning the council actually produced — agreements, conflicts, dissents,
// and who moved the room. Deep-links to the Weave trace (sponsor story §9).
import { motion } from "framer-motion";

import type { Agent, Stance, Verdict as V } from "../lib/types";
import { Eyebrow, cx } from "./ui";

const STANCE_VAR: Record<Stance, string> = { YES: "var(--yes)", NO: "var(--no)", CONDITIONAL: "var(--cond)" };
const reveal = (i: number) => ({
  initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, delay: 0.08 * i, ease: [0.2, 0.8, 0.2, 1] as const },
});

export function VerdictPanel({ verdict, agents, weaveUrl }: { verdict: V; agents: Agent[]; weaveUrl?: string | null }) {
  const nameOf = (id: string) => agents.find((a) => a.id === id)?.name ?? id;
  const color = STANCE_VAR[verdict.decision];
  const maxInfluence = Math.max(0.0001, ...verdict.influence_ranking.map((r) => r.influence));

  return (
    <motion.section {...reveal(0)} className="panel" style={{ overflow: "hidden" }}>
      {/* decree band */}
      <div
        className="row between wrapflex"
        style={{
          gap: 18, padding: "22px 24px", borderBottom: "1px solid var(--line)",
          background: `linear-gradient(100deg, color-mix(in srgb, ${color} 12%, transparent), transparent 70%)`,
        }}
      >
        <div>
          <Eyebrow>The council rules</Eyebrow>
          <div className="serif" style={{ fontSize: 52, lineHeight: 1, color, marginTop: 6, letterSpacing: "-0.02em" }}>
            {verdict.decision}
          </div>
        </div>
        <div className="row" style={{ gap: 28 }}>
          <div style={{ textAlign: "right" }}>
            <div className="eyebrow">Weighted score</div>
            <div className="serif tnum" style={{ fontSize: 40, lineHeight: 1.1 }}>
              {verdict.weighted_score.toFixed(1)}<span className="faint" style={{ fontSize: 20 }}>/10</span>
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="eyebrow">Confidence</div>
            <div className="serif tnum" style={{ fontSize: 40, lineHeight: 1.1 }}>
              {Math.round(verdict.confidence * 100)}<span className="faint" style={{ fontSize: 20 }}>%</span>
            </div>
          </div>
        </div>
      </div>

      <div className="panel-pad" style={{ display: "flex", flexDirection: "column", gap: 22 }}>
        <motion.p {...reveal(1)} className="serif" style={{ fontSize: 17, lineHeight: 1.6, margin: 0, color: "var(--text)" }}>
          {verdict.summary}
        </motion.p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 22 }}>
          <motion.div {...reveal(2)} className="col" style={{ gap: 9 }}>
            <Eyebrow>Where they agreed</Eyebrow>
            {verdict.key_agreements.map((a, i) => (
              <div key={i} className="row" style={{ gap: 9, alignItems: "baseline" }}>
                <span style={{ color: "var(--yes)" }}>✓</span>
                <span className="small">{a}</span>
              </div>
            ))}
          </motion.div>

          <motion.div {...reveal(3)} className="col" style={{ gap: 12 }}>
            <Eyebrow>Where they clashed</Eyebrow>
            {verdict.key_conflicts.map((c, i) => (
              <div key={i} className="small">
                <span className="mono faint">{c.between.map(nameOf).join(" ⇄ ")}</span>
                <div className="muted">{c.issue}</div>
              </div>
            ))}
            {verdict.dissenting_opinions.length > 0 && (
              <>
                <Eyebrow style={{ marginTop: 4 }}>Dissent</Eyebrow>
                {verdict.dissenting_opinions.map((d, i) => (
                  <div key={i} className="small">
                    <span className={cx("stance", d.stance)} style={{ marginRight: 7 }}>{d.stance}</span>
                    <span className="muted">{nameOf(d.agent_id)} — {d.why}</span>
                  </div>
                ))}
              </>
            )}
          </motion.div>

          <motion.div {...reveal(4)} className="col" style={{ gap: 9 }}>
            <Eyebrow>Who moved the room</Eyebrow>
            {verdict.influence_ranking.map((r) => (
              <div key={r.agent_id} className="col" style={{ gap: 3 }}>
                <div className="row between small">
                  <span>{nameOf(r.agent_id)}</span>
                  <span className="mono tnum faint">{Math.round(r.influence * 100)}%</span>
                </div>
                <div style={{ height: 5, borderRadius: 999, background: "rgba(0,0,0,0.35)", border: "1px solid var(--line)" }}>
                  <motion.div
                    initial={{ width: 0 }} animate={{ width: `${(r.influence / maxInfluence) * 100}%` }}
                    transition={{ duration: 0.8, delay: 0.5 }}
                    style={{ height: "100%", borderRadius: 999, background: "linear-gradient(90deg, var(--ember-deep), var(--ember))" }}
                  />
                </div>
              </div>
            ))}
          </motion.div>
        </div>

        {weaveUrl && (
          <motion.a {...reveal(5)} href={weaveUrl} target="_blank" rel="noreferrer" className="row" style={{ gap: 8, alignSelf: "flex-start" }}>
            <span className="mono small">↗ Open the full reasoning trace in W&B Weave</span>
          </motion.a>
        )}
      </div>
    </motion.section>
  );
}
