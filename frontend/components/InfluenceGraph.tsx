"use client";
// "Who swayed whom" (§8) as a force-directed constellation. Node size = voting
// weight, ring = final stance, edge thickness + flowing particles = influence.
// react-force-graph is canvas/DOM-bound, so it's loaded client-only.
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";

import type { Graph } from "../lib/derive";
import type { Stance } from "../lib/types";
import { Eyebrow, hueFor } from "./ui";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const STANCE_HEX: Record<Stance, string> = { YES: "#7ec078", NO: "#db6151", CONDITIONAL: "#d7a23a" };

export function InfluenceGraph({ graph }: { graph: Graph }) {
  const box = useRef<HTMLDivElement>(null);
  const fg = useRef<any>(null);
  const [w, setW] = useState(0);
  const height = 360;

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  // Clone into fresh objects (force-graph mutates source/target in place) and
  // only recompute when the graph's shape/values actually change.
  const sig = graph.nodes.map((n) => `${n.id}:${n.influence}:${n.stance ?? ""}`).join("|") +
    "#" + graph.links.map((l) => `${l.source}>${l.target}:${l.weight}`).join("|");
  const data = useMemo(() => {
    const hue: Record<string, string> = {};
    graph.nodes.forEach((n, i) => (hue[n.id] = hueFor(i)));
    return {
      hue,
      nodes: graph.nodes.map((n) => ({ ...n })),
      links: graph.links.map((l) => ({ ...l })),
      maxW: Math.max(0.001, ...graph.links.map((l) => l.weight)),
    };
  }, [sig]); // eslint-disable-line react-hooks/exhaustive-deps

  const hasEdges = graph.links.length > 0;

  // Spread the council out (stronger repulsion + longer links) so labels don't
  // collide, and frame them to the panel once the simulation settles.
  useEffect(() => {
    const g = fg.current;
    if (!g || !w) return;
    g.d3Force("charge")?.strength(-320);
    g.d3Force("link")?.distance(95);
    g.d3ReheatSimulation?.();
  }, [sig, w]);

  return (
    <section className="panel" style={{ display: "flex", flexDirection: "column" }}>
      <div className="panel-head"><Eyebrow>Influence · who swayed whom</Eyebrow></div>
      <div ref={box} style={{ height, position: "relative" }}>
        {!hasEdges && (
          <div className="muted small" style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center", padding: 20, zIndex: 1, pointerEvents: "none" }}>
            Influence emerges as agents move each other’s positions.
          </div>
        )}
        {w > 0 && (
          <ForceGraph2D
            ref={fg}
            width={w}
            height={height}
            graphData={data as any}
            backgroundColor="rgba(0,0,0,0)"
            nodeRelSize={5}
            nodeVal={(n: any) => 2 + n.weight * 3}
            cooldownTicks={120}
            onEngineStop={() => fg.current?.zoomToFit(500, 56)}
            d3VelocityDecay={0.3}
            linkColor={() => "rgba(232,168,56,0.32)"}
            linkWidth={(l: any) => 0.6 + (l.weight / data.maxW) * 4}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={0.9}
            linkDirectionalParticles={(l: any) => Math.min(5, Math.ceil((l.weight / data.maxW) * 4))}
            linkDirectionalParticleWidth={2}
            linkDirectionalParticleColor={() => "rgba(244,198,108,0.9)"}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, scale: number) => {
              const r = (2 + node.weight * 3);
              const fill = data.hue[node.id] ?? "#e0a040";
              ctx.beginPath();
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
              ctx.fillStyle = fill;
              ctx.globalAlpha = 0.92;
              ctx.fill();
              ctx.globalAlpha = 1;
              // stance ring
              if (node.stance) {
                ctx.lineWidth = 1.6 / scale;
                ctx.strokeStyle = STANCE_HEX[node.stance as Stance];
                ctx.beginPath();
                ctx.arc(node.x, node.y, r + 2.2, 0, 2 * Math.PI);
                ctx.stroke();
              }
              // label
              const fs = 11 / scale;
              ctx.font = `600 ${fs}px ui-sans-serif, system-ui`;
              ctx.fillStyle = "rgba(236,227,210,0.92)";
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillText(node.name, node.x, node.y + r + 3.5);
              if (node.influence > 0) {
                ctx.fillStyle = "rgba(126,115,97,0.95)";
                ctx.font = `${9 / scale}px ui-monospace, monospace`;
                ctx.fillText(`${Math.round(node.influence * 100)}%`, node.x, node.y + r + 3.5 + fs + 1);
              }
            }}
          />
        )}
      </div>
    </section>
  );
}
