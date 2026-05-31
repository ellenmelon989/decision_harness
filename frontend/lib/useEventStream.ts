"use client";
// Live session events via SSE (ROADMAP §6). Accumulates events as they arrive
// and surfaces a connection status so the UI can show an honest "in session"
// vs "complete" vs "lost connection" state instead of a silent dead stream.
import { useEffect, useRef, useState } from "react";

import { api } from "./api";
import type { DHEvent, EventType } from "./types";

export type StreamStatus = "idle" | "connecting" | "open" | "done" | "error";

const EVENT_NAMES: EventType[] = [
  "position", "thought", "message", "peer_request", "peer_response",
  "tool_call", "tool_result", "position_update", "orchestrator", "verdict",
  "error", "done",
];

export function useEventStream(sessionId: string | null) {
  const [events, setEvents] = useState<DHEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!sessionId) { setStatus("idle"); return; }
    setEvents([]);
    setStatus("connecting");
    seen.current = new Set();

    const es = new EventSource(api.streamUrl(sessionId));
    es.onopen = () => setStatus((s) => (s === "done" ? s : "open"));

    const finish = () => { setStatus("done"); es.close(); };
    const onEvent = (e: MessageEvent) => {
      if ((e as any).type === "done") return finish();
      try {
        const ev = JSON.parse(e.data) as DHEvent;
        if (ev.id && seen.current.has(ev.id)) return; // dedupe history+live overlap
        if (ev.id) seen.current.add(ev.id);
        setEvents((prev) => [...prev, ev]);
        if (ev.type === "verdict") finish();
      } catch { /* ignore non-JSON keepalives */ }
    };
    EVENT_NAMES.forEach((name) => es.addEventListener(name, onEvent as EventListener));
    es.onerror = () => {
      // EventSource auto-reconnects; only surface an error if we never finished.
      setStatus((s) => (s === "done" ? s : "error"));
    };
    return () => es.close();
  }, [sessionId]);

  const done = status === "done";
  return { events, status, done };
}
