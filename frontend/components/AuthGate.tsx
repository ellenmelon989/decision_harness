"use client";
// Gates the app behind Supabase email/password auth. In dev/in-memory mode
// (Supabase not configured) it renders the app directly — no login required.
// A `?demo` query param also bypasses auth into the no-login replay mode, so
// anyone (judges included) can see the full UI without an account.
import { useEffect, useState } from "react";

import { useAuth } from "../lib/auth";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { session, loading, configured } = useAuth();
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    setDemo(new URLSearchParams(window.location.search).has("demo"));
  }, []);

  if (demo) return <>{children}</>;

  if (loading) {
    return (
      <div className="wrap">
        <div className="muted">Loading…</div>
      </div>
    );
  }
  // No Supabase configured → keyless dev path. Authenticated → app.
  if (!configured || session) return <>{children}</>;
  return <LoginForm />;
}

function LoginForm() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    const { error } = await (mode === "in" ? signIn : signUp)(email, password);
    setBusy(false);
    if (error) {
      setError(error);
      return;
    }
    if (mode === "up") {
      setNotice("Account created — signing you in…");
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <div style={{ width: "min(380px, 100%)" }}>
      <div className="eyebrow" style={{ marginBottom: 6 }}>The Deliberation Room</div>
      <h1 style={{ fontSize: 34 }}>Decision Harness</h1>
      <div className="muted small" style={{ marginTop: 4 }}>Convene an AI council. Put a decision to the floor. Watch them argue — with a full audit trail.</div>

      <form className="panel" style={{ margin: "16px 0", maxWidth: 380 }} onSubmit={submit}>
        <b>{mode === "in" ? "Sign in" : "Create account"}</b>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            autoComplete="email"
            required
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password (min 6 chars)"
            value={password}
            autoComplete={mode === "in" ? "current-password" : "new-password"}
            required
            minLength={6}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" style={{ justifyContent: "center" }} disabled={busy || !email || !password}>
            {busy ? "…" : mode === "in" ? "Sign in" : "Sign up"}
          </button>
        </div>

        {error && (
          <div className="small" style={{ color: "#e5484d", marginTop: 10 }}>{error}</div>
        )}
        {notice && (
          <div className="small muted" style={{ marginTop: 10 }}>{notice}</div>
        )}

        <div className="muted small" style={{ marginTop: 12 }}>
          {mode === "in" ? "No account?" : "Already have one?"}{" "}
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              setMode(mode === "in" ? "up" : "in");
              setError(null);
              setNotice(null);
            }}
          >
            {mode === "in" ? "Create one" : "Sign in"}
          </a>
        </div>
      </form>

      <a className="mono small faint" href="?demo">▸ or watch the sample debate — no account needed</a>
      </div>
    </div>
  );
}
