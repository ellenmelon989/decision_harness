// Small presentational primitives shared across the chamber. Pure + tiny so
// every panel speaks the same visual language.
import type { Stance } from "../lib/types";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

// Muted, warm-leaning per-seat accents so agents are distinguishable without
// breaking the chamber palette. Used for monograms and influence-graph nodes.
export const SEAT_HUES = ["#e0a040", "#7ec078", "#d97b5a", "#c9b04a", "#cf7f8a", "#86b8a0", "#d6a23a", "#9db36a"];
export const hueFor = (i: number) => SEAT_HUES[((i % SEAT_HUES.length) + SEAT_HUES.length) % SEAT_HUES.length];

export const initials = (name: string) =>
  name.replace(/^the\s+/i, "").split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("") || "·";

export function Eyebrow({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <div className="eyebrow" style={style}>{children}</div>;
}

export function Monogram({ name, hue, size = 34 }: { name: string; hue: string; size?: number }) {
  return (
    <span
      className="monogram"
      style={{
        width: size, height: size, fontSize: size * 0.42,
        color: hue,
        borderColor: `color-mix(in srgb, ${hue} 45%, transparent)`,
        boxShadow: `inset 0 0 18px -8px ${hue}`,
      }}
    >
      {initials(name)}
    </span>
  );
}

export function StanceBadge({ stance, score }: { stance?: Stance; score?: number }) {
  if (!stance) return <span className="stance faint" style={{ borderColor: "var(--line-2)" }}>AWAITING</span>;
  return (
    <span className={cx("stance", stance)}>
      {stance}{typeof score === "number" ? ` · ${score}` : ""}
    </span>
  );
}

const STANCE_VAR: Record<Stance, string> = { YES: "var(--yes)", NO: "var(--no)", CONDITIONAL: "var(--cond)" };

export function ScoreMeter({ score, stance }: { score?: number; stance?: Stance }) {
  const pct = Math.max(0, Math.min(100, ((score ?? 0) / 10) * 100));
  const color = stance ? STANCE_VAR[stance] : "var(--text-faint)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 5, borderRadius: 999, background: "rgba(0,0,0,0.35)", overflow: "hidden", border: "1px solid var(--line)" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 999, transition: "width 0.7s cubic-bezier(.2,.8,.2,1)" }} />
      </div>
      <span className="mono tnum small" style={{ color, minWidth: 34, textAlign: "right" }}>
        {typeof score === "number" ? score.toFixed(1) : "—"}
      </span>
    </div>
  );
}
