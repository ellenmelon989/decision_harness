"use client";
// The chamber header: a seal + wordmark, and an honest backend-status readout
// (the thing that silently failed before — now it's visible with a retry).
import { motion } from "framer-motion";

import { cx } from "./ui";

function Seal() {
  return (
    <svg width="34" height="34" viewBox="0 0 40 40" fill="none" aria-hidden>
      <circle cx="20" cy="20" r="18.5" stroke="var(--ember)" strokeOpacity="0.5" />
      <circle cx="20" cy="20" r="13" stroke="var(--ember)" strokeOpacity="0.28" />
      {Array.from({ length: 12 }).map((_, i) => {
        const a = (i / 12) * Math.PI * 2;
        return (
          <line
            key={i}
            x1={20 + Math.cos(a) * 13} y1={20 + Math.sin(a) * 13}
            x2={20 + Math.cos(a) * 18} y2={20 + Math.sin(a) * 18}
            stroke="var(--ember)" strokeOpacity="0.45" strokeWidth="1"
          />
        );
      })}
      <path d="M20 11 L26 26 L20 22 L14 26 Z" fill="var(--ember)" fillOpacity="0.9" />
    </svg>
  );
}

export function Console({
  health, healthError, onRetry, user, onSignOut, demo,
}: {
  health: string;
  healthError: boolean;
  onRetry: () => void;
  user?: { email?: string } | null;
  onSignOut?: () => void;
  demo?: boolean;
}) {
  return (
    <motion.header
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
      className="row between wrapflex"
      style={{ gap: 16, alignItems: "flex-end", paddingBottom: 20, borderBottom: "1px solid var(--line)" }}
    >
      <div className="row" style={{ gap: 13, alignItems: "center" }}>
        <Seal />
        <div>
          <div className="eyebrow" style={{ marginBottom: 2 }}>The Deliberation Room</div>
          <h1 style={{ fontSize: 28, lineHeight: 1 }}>Decision&nbsp;Harness</h1>
        </div>
      </div>

      <div className="row" style={{ gap: 14, alignItems: "center" }}>
        <button
          className={cx("row", "small")}
          onClick={healthError ? onRetry : undefined}
          title={healthError ? "Retry connection" : health}
          style={{
            gap: 7, background: "transparent", border: "1px solid var(--line-2)",
            borderRadius: 999, padding: "5px 11px", cursor: healthError ? "pointer" : "default",
            color: healthError ? "var(--no)" : "var(--text-dim)",
          }}
        >
          <span className={cx("dot", healthError ? "err" : "done")} />
          <span className="mono small">{healthError ? "backend offline · retry" : health}</span>
        </button>

        {demo ? (
          <span className="eyebrow" style={{ color: "var(--ember)" }}>Demo mode</span>
        ) : user ? (
          <div className="row small muted" style={{ gap: 8 }}>
            <span>{user.email}</span>
            <a href="#" onClick={(e) => { e.preventDefault(); onSignOut?.(); }}>sign out</a>
          </div>
        ) : null}
      </div>
    </motion.header>
  );
}
