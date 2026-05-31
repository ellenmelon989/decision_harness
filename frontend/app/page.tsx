"use client";
// The Deliberation Room. Orchestrates the end-to-end flow (ROADMAP §6):
// assemble a council → put a question → watch them debate live → see who swayed
// whom → read the ruling → re-weight the room and re-run. A `?demo` param plays
// a self-contained sample debate with no backend or login.
import { useCallback, useEffect, useMemo, useState } from "react";

import { Boardroom } from "../components/Boardroom";
import { Composer } from "../components/Composer";
import { Console } from "../components/Console";
import { HITL } from "../components/HITL";
import { InfluenceGraph } from "../components/InfluenceGraph";
import { Inspector } from "../components/Inspector";
import { OrgBuilder } from "../components/OrgBuilder";
import { VerdictPanel } from "../components/Verdict";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { deriveBoard, deriveInfluence } from "../lib/derive";
import { MOCK_AGENTS, MOCK_EVENTS, MOCK_ORG, MOCK_QUESTION, MOCK_VERDICT } from "../lib/mock";
import type { Agent, DHEvent, Org, Verdict } from "../lib/types";
import { useEventStream, type StreamStatus } from "../lib/useEventStream";

export default function Home() {
  const { user, signOut } = useAuth();

  // ---- demo / replay mode (no backend, no login) ----
  const [demo, setDemo] = useState(false);
  useEffect(() => { setDemo(new URLSearchParams(window.location.search).has("demo")); }, []);

  // ---- backend-backed state ----
  const [health, setHealth] = useState("connecting…");
  const [healthError, setHealthError] = useState(false);
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [orgId, setOrgId] = useState("");
  const [liveAgents, setLiveAgents] = useState<Agent[]>([]);
  const [question, setQuestion] = useState(MOCK_QUESTION);
  const [rounds, setRounds] = useState(3);
  const [context, setContext] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [weaveUrl, setWeaveUrl] = useState<string | null>(null);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [builderOpen, setBuilderOpen] = useState(false);
  const [rerunning, setRerunning] = useState(false);

  const bootstrap = useCallback(() => {
    setHealthError(false); setHealth("connecting…");
    api.health()
      .then((h) => setHealth(`backend · ${h.repo}`))
      .catch((e) => { setHealth(String(e)); setHealthError(true); });
    api.ensureSeed()
      .then((o) => { setOrgs(o); setOrgId((cur) => cur || o[0]?.id || ""); })
      .catch((e) => { setHealth(String(e)); setHealthError(true); });
  }, []);

  useEffect(() => { if (!demo) bootstrap(); }, [demo, bootstrap]);
  useEffect(() => {
    if (demo || !orgId) return;
    api.listAgents(orgId).then(setLiveAgents).catch(() => setLiveAgents([]));
  }, [orgId, demo]);

  // ---- live event stream ----
  const live = useEventStream(demo ? null : sessionId);

  // ---- demo replay: play the sample debate progressively ----
  const [demoStep, setDemoStep] = useState(0);
  const [demoKey, setDemoKey] = useState(0);
  useEffect(() => {
    if (!demo) return;
    setDemoStep(0);
    let i = 0;
    const t = setInterval(() => {
      i += 1; setDemoStep(i);
      if (i >= MOCK_EVENTS.length) clearInterval(t);
    }, 620);
    return () => clearInterval(t);
  }, [demo, demoKey]);

  // ---- unify demo vs live ----
  const agents = demo ? MOCK_AGENTS : liveAgents;
  const events: DHEvent[] = demo ? MOCK_EVENTS.slice(0, demoStep) : live.events;
  const status: StreamStatus = demo
    ? (demoStep === 0 ? "connecting" : demoStep >= MOCK_EVENTS.length ? "done" : "open")
    : live.status;

  const board = useMemo(() => deriveBoard(events, agents), [events, agents]);
  const graph = useMemo(() => deriveInfluence(events, agents), [events, agents]);
  const verdict: Verdict | null = demo
    ? (status === "done" ? MOCK_VERDICT : null)
    : ((events.find((e) => e.type === "verdict")?.content as Verdict) ?? null);

  // init / reset weights when the roster changes
  useEffect(() => {
    setWeights(Object.fromEntries(agents.map((a) => [a.id, a.weight])));
  }, [agents]);

  // pull the Weave deep-link once a live session completes
  useEffect(() => {
    if (demo || status !== "done" || !sessionId) return;
    api.getSession(sessionId).then((d) => setWeaveUrl(d.session.weave_trace_url ?? null)).catch(() => {});
  }, [status, sessionId, demo]);

  const currentOrg = demo ? MOCK_ORG : orgs.find((o) => o.id === orgId);
  const live_now = status === "open" || status === "connecting";
  const canRun = demo
    ? !live_now
    : !!orgId && question.trim().length > 0 && !healthError && !live_now;

  async function run() {
    if (demo) { setDemoKey((k) => k + 1); return; }
    setWeaveUrl(null);
    setSessionId(null);
    const { session_id } = await api.createSession({ org_id: orgId, question, rounds, context: context || undefined });
    setSessionId(session_id);
  }

  async function rerun() {
    if (demo || !sessionId) { if (demo) setDemoKey((k) => k + 1); return; }
    setRerunning(true);
    try {
      const override = Object.fromEntries(agents.map((a) => [a.id, weights[a.id] ?? a.weight]));
      setWeaveUrl(null);
      const { session_id } = await api.rerun(sessionId, { weights_override: override, context: context || undefined });
      setSessionId(session_id);
    } catch (e) {
      setHealth(String(e)); setHealthError(true);
    } finally {
      setRerunning(false);
    }
  }

  const refreshOrgs = async (selectId?: string) => {
    const o = await api.listOrgs();
    setOrgs(o);
    if (selectId) setOrgId(selectId);
    if (selectId === orgId) setLiveAgents(await api.listAgents(selectId));
  };
  const refreshAgents = async () => { if (orgId) setLiveAgents(await api.listAgents(orgId)); };

  return (
    <div className="wrap">
      <Console
        health={demo ? "sample debate · no backend" : health}
        healthError={!demo && healthError}
        onRetry={bootstrap}
        user={user}
        onSignOut={signOut}
        demo={demo}
      />

      <Composer
        orgs={demo ? [MOCK_ORG] : orgs}
        orgId={demo ? MOCK_ORG.id : orgId}
        onOrg={setOrgId}
        question={question}
        onQuestion={setQuestion}
        rounds={rounds}
        onRounds={setRounds}
        status={status}
        seats={agents.length}
        round={board.round}
        note={board.lastNote}
        canRun={canRun}
        onRun={run}
        onOpenBuilder={() => setBuilderOpen(true)}
        healthError={!demo && healthError}
        healthMsg={health}
        onRetry={bootstrap}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 22, marginTop: 22 }}>
        <Boardroom agents={agents} board={board} />

        {verdict && <VerdictPanel verdict={verdict} agents={agents} weaveUrl={weaveUrl} />}

        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.25fr) minmax(0, 1fr)", gap: 22, alignItems: "start" }} className="split">
          <Inspector events={events} agents={agents} />
          <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
            <InfluenceGraph graph={graph} />
            <HITL
              agents={agents}
              weights={weights}
              onWeight={(id, w) => setWeights((p) => ({ ...p, [id]: w }))}
              context={context}
              onContext={setContext}
              onRerun={rerun}
              rerunning={rerunning}
              enabled={demo || (!!sessionId && status === "done")}
            />
          </div>
        </div>
      </div>

      <OrgBuilder
        open={builderOpen}
        onClose={() => setBuilderOpen(false)}
        currentOrg={currentOrg}
        agents={agents}
        onOrgsChanged={refreshOrgs}
        onAgentsChanged={refreshAgents}
        demo={demo}
      />

      <footer className="row between wrapflex" style={{ marginTop: 40, paddingTop: 18, borderTop: "1px solid var(--line)", gap: 10 }}>
        <span className="eyebrow">Decision Harness · a configurable AI council</span>
        {!demo && <a className="mono small faint" href="?demo">▸ watch the sample debate</a>}
      </footer>
    </div>
  );
}
