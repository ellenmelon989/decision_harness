"use client";
// Assemble a council: synthesize a whole panel from a prompt (§9.4), spin up a
// blank preset, or edit seats in place (name / role / weight / provider).
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { api, type AgentCreateBody } from "../lib/api";
import type { Agent, Org } from "../lib/types";
import { Eyebrow, Monogram, hueFor } from "./ui";

const PRESETS = [
  { key: "judges", label: "Hackathon Judges" },
  { key: "vc", label: "VC Committee" },
  { key: "board", label: "Board of Directors" },
  { key: "custom", label: "Blank / Custom" },
];

// The council runs entirely on W&B Inference open models (no Anthropic).
const WANDB_MODELS = [
  "openai/gpt-oss-120b",
  "Qwen/Qwen3-235B-A22B-Instruct-2507",
  "moonshotai/Kimi-K2.6",
  "deepseek-ai/DeepSeek-V4-Pro",
  "zai-org/GLM-5.1",
  "MiniMaxAI/MiniMax-M2.5",
  "meta-llama/Llama-3.3-70B-Instruct",
  "Qwen/Qwen3-30B-A3B-Instruct-2507",
];
const BLANK_AGENT: AgentCreateBody = { name: "", role: "", system_prompt: "", weight: 1, provider: "wandb", model: WANDB_MODELS[0], tools: [] };

export function OrgBuilder({
  open, onClose, currentOrg, agents, onOrgsChanged, onAgentsChanged, demo,
}: {
  open: boolean;
  onClose: () => void;
  currentOrg?: Org;
  agents: Agent[];
  onOrgsChanged: (selectId?: string) => void | Promise<void>;
  onAgentsChanged: () => void | Promise<void>;
  demo?: boolean;
}) {
  const [prompt, setPrompt] = useState("");
  const [name, setName] = useState("");
  const [preset, setPreset] = useState("vc");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [draft, setDraft] = useState<AgentCreateBody>(BLANK_AGENT);
  const [adding, setAdding] = useState(false);

  const guard = async (key: string, fn: () => Promise<void>) => {
    if (demo) { setErr("Council editing is disabled in demo mode — sign in to build your own."); return; }
    setErr(null); setBusy(key);
    try { await fn(); } catch (e) { setErr(String(e)); } finally { setBusy(null); }
  };

  const generate = () => guard("gen", async () => {
    const org = await api.generateOrg(prompt.trim());
    setPrompt("");
    await onOrgsChanged(org.id);
  });
  const create = () => guard("create", async () => {
    const org = await api.createOrg({ name: name.trim() || "New Council", preset });
    setName("");
    await onOrgsChanged(org.id);
  });
  const addAgent = () => guard("add", async () => {
    if (!currentOrg) return;
    await api.createAgent(currentOrg.id, { ...draft, position: agents.length });
    setDraft(BLANK_AGENT); setAdding(false);
    await onAgentsChanged();
  });
  const patch = (id: string, body: Partial<AgentCreateBody>) =>
    guard("patch", async () => { await api.updateAgent(id, body); await onAgentsChanged(); });

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}
          style={{ position: "fixed", inset: 0, zIndex: 100, background: "rgba(6,5,4,0.66)", backdropFilter: "blur(6px)", display: "grid", placeItems: "center", padding: 20 }}
        >
          <motion.div
            initial={{ opacity: 0, y: 18, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 18, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 280, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
            className="panel" style={{ width: "min(680px, 100%)", maxHeight: "88vh", display: "flex", flexDirection: "column" }}
          >
            <div className="panel-head">
              <div className="serif" style={{ fontSize: 20 }}>Assemble a council</div>
              <button className="btn btn-ghost btn-sm" onClick={onClose}>✕ close</button>
            </div>

            <div className="panel-pad" style={{ overflowY: "auto", display: "flex", flexDirection: "column", gap: 22 }}>
              {err && <div className="small" style={{ color: "var(--no)" }}>{err}</div>}

              {/* generate from prompt */}
              <div className="col" style={{ gap: 8 }}>
                <Eyebrow>Synthesize from a prompt</Eyebrow>
                <textarea
                  rows={2} value={prompt} placeholder="e.g. “a biotech seed investment committee” or “a senior hiring panel for a staff engineer”"
                  onChange={(e) => setPrompt(e.target.value)} style={{ resize: "vertical" }}
                />
                <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} disabled={!prompt.trim() || busy === "gen"} onClick={generate}>
                  {busy === "gen" ? "Convening minds…" : "✦ Generate council"}
                </button>
              </div>

              <hr className="rule" />

              {/* blank / preset */}
              <div className="col" style={{ gap: 8 }}>
                <Eyebrow>Or start from a preset</Eyebrow>
                <div className="row wrapflex" style={{ gap: 10 }}>
                  <input className="grow" style={{ minWidth: 180 }} value={name} placeholder="Council name" onChange={(e) => setName(e.target.value)} />
                  <select value={preset} onChange={(e) => setPreset(e.target.value)}>
                    {PRESETS.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
                  </select>
                  <button className="btn btn-ghost" disabled={busy === "create"} onClick={create}>
                    {busy === "create" ? "Creating…" : "Create"}
                  </button>
                </div>
              </div>

              {/* edit current council's seats */}
              {currentOrg && (
                <>
                  <hr className="rule" />
                  <div className="col" style={{ gap: 12 }}>
                    <Eyebrow>Seats in “{currentOrg.name}”</Eyebrow>
                    {agents.map((a, i) => (
                      <SeatEditor key={a.id} agent={a} hue={hueFor(i)} onPatch={(b) => patch(a.id, b)} />
                    ))}

                    {adding ? (
                      <div className="panel panel-pad col" style={{ gap: 8, background: "var(--surface-2)" }}>
                        <div className="row wrapflex" style={{ gap: 8 }}>
                          <input className="grow" placeholder="Name (e.g. The CFO)" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                          <input className="grow" placeholder="Role (e.g. Finance & risk)" value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })} />
                        </div>
                        <textarea rows={2} placeholder="System prompt — how should this seat reason?" value={draft.system_prompt} onChange={(e) => setDraft({ ...draft, system_prompt: e.target.value })} />
                        <div className="row wrapflex" style={{ gap: 8 }}>
                          <select value={draft.model} onChange={(e) => setDraft({ ...draft, model: e.target.value })} title="W&B Inference model">
                            {WANDB_MODELS.map((m) => <option key={m} value={m}>{m.split("/").pop()}</option>)}
                          </select>
                          <label className="row small muted" style={{ gap: 6 }}>
                            weight
                            <input type="number" min={0} max={3} step={0.1} value={draft.weight} style={{ width: 72 }} className="mono tnum" onChange={(e) => setDraft({ ...draft, weight: +e.target.value })} />
                          </label>
                          <div className="grow" />
                          <button className="btn btn-ghost btn-sm" onClick={() => { setAdding(false); setDraft(BLANK_AGENT); }}>cancel</button>
                          <button className="btn btn-primary btn-sm" disabled={!draft.name.trim() || !draft.role.trim() || busy === "add"} onClick={addAgent}>
                            {busy === "add" ? "Adding…" : "Add seat"}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }} onClick={() => setAdding(true)}>⊕ Add a seat</button>
                    )}
                  </div>
                </>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SeatEditor({ agent, hue, onPatch }: { agent: Agent; hue: string; onPatch: (b: Partial<AgentCreateBody>) => void }) {
  const [name, setName] = useState(agent.name);
  const [role, setRole] = useState(agent.role);
  const [weight, setWeight] = useState(agent.weight);
  const commit = (b: Partial<AgentCreateBody>, changed: boolean) => { if (changed) onPatch(b); };

  return (
    <div className="row" style={{ gap: 10, alignItems: "center" }}>
      <Monogram name={name || agent.name} hue={hue} size={30} />
      <input className="grow" value={name} onChange={(e) => setName(e.target.value)} onBlur={() => commit({ name }, name !== agent.name)} />
      <input className="grow" value={role} onChange={(e) => setRole(e.target.value)} onBlur={() => commit({ role }, role !== agent.role)} />
      <input
        type="number" min={0} max={3} step={0.1} value={weight} className="mono tnum" style={{ width: 70 }}
        onChange={(e) => setWeight(+e.target.value)} onBlur={() => commit({ weight }, weight !== agent.weight)}
      />
    </div>
  );
}
