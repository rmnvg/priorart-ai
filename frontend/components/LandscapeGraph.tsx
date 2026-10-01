"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  buildLandscapeGraph,
  CITATION_LINK_COLOR,
  type GraphLink,
  type GraphNode,
} from "@/lib/landscapeGraph";
import { similarityBand } from "@/lib/evidence";
import type { AnalysisResult } from "@/types/analysis";

// react-force-graph-2d renders to an HTML canvas and reaches for `window` at
// import time, so it can only run client-side.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

// next/dynamic doesn't preserve react-force-graph-2d's generic type
// parameters on the wrapped component, so ForceGraphMethods<...> can't be
// named accurately here. The underlying d3-force objects also have
// different shapes per force name (link vs. charge), which a precise type
// isn't worth modeling for two call sites — left as `any` deliberately.
type ForceGraphRef = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  d3Force: (name: string) => any;
  zoomToFit: (durationMs: number, padding: number) => void;
} | null;

const GRAPH_HEIGHT = 480;
// Phones get a shorter canvas: a 480px-tall graph on a 390px-wide screen is
// mostly empty space above and below the cluster.
const GRAPH_HEIGHT_NARROW = 360;
const NARROW_WIDTH = 640;
const SURFACE_RING_COLOR = "#fafafa"; // matches the page background (bg-neutral-50)

// Per-link distance/strength (closer relevance -> shorter distance to the
// idea node) isn't exposed as a prop, so we reach into the underlying
// d3-force simulation directly. Pure function of the ref, not component
// state, so it can live outside the component and be called from a stable
// ref callback.
function configureForces(fg: ForceGraphRef) {
  if (!fg) return;
  fg.d3Force("link")
    ?.distance((l: object) => (l as GraphLink).distance)
    .strength((l: object) => (l as GraphLink).strength);
  fg.d3Force("charge")?.strength(-140);
  // One early fit for quick visual feedback, one after the simulation's
  // cooldown (see cooldownTime on ForceGraph2D below) so the final framing
  // matches the fully-settled layout rather than a mid-simulation snapshot.
  setTimeout(() => fg.zoomToFit(400, 60), 400);
  setTimeout(() => fg.zoomToFit(400, 60), 2700);
}

export default function LandscapeGraph({ result }: { result: AnalysisResult }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<ForceGraphRef>(null);
  const [width, setWidth] = useState(0);

  const { nodes, links, legend } = useMemo(() => buildLandscapeGraph(result), [result]);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // The ref callback fires exactly when the (async-loaded) ForceGraph2D
  // instance mounts — unlike a useEffect keyed on data, which next/dynamic's
  // async resolution can race, silently leaving nodes on d3-force's default
  // (much tighter) link distance. Stable identity via useCallback so it
  // doesn't re-fire configureForces (and re-run zoomToFit) on every render.
  const setForceGraphRef = useCallback((el: ForceGraphRef) => {
    fgRef.current = el;
    if (el) configureForces(el);
  }, []);

  // Data can also change later (a new analysis re-using the same mounted
  // component), in which case the ref is already populated and this effect
  // is what re-applies the forces/re-fits the view.
  useEffect(() => {
    if (fgRef.current) configureForces(fgRef.current);
  }, [nodes, links]);

  return (
    <div className="relative rounded-lg border border-neutral-200 bg-neutral-50" ref={containerRef}>
      {/* On phones the legend sits above the canvas as a wrapped row — an
          overlaid box would cover a quarter of the graph at that width. */}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 border-b border-neutral-200 p-3 text-xs sm:absolute sm:left-4 sm:top-4 sm:z-10 sm:block sm:rounded-md sm:border sm:bg-white/90 sm:shadow-sm sm:backdrop-blur">
        {legend.map((entry) => (
          <div key={entry.label} className="flex items-center gap-2 py-0.5">
            {entry.shape === "dot" ? (
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
            ) : (
              <span className="inline-block w-2.5 text-center leading-none" style={{ color: entry.color }}>
                →
              </span>
            )}
            <span className="text-neutral-700">{entry.label}</span>
          </div>
        ))}
      </div>

      {width > 0 && (
        <ForceGraph2D
          // react-force-graph-2d types its `ref` prop narrowly (a plain
          // MutableRefObject, not React's usual Ref<T> union) and next/dynamic
          // erases its generics on top of that — a targeted cast is the
          // pragmatic way through, rather than fighting a third-party type.
          ref={setForceGraphRef as never}
          width={width}
          height={width < NARROW_WIDTH ? GRAPH_HEIGHT_NARROW : GRAPH_HEIGHT}
          graphData={{ nodes, links }}
          // Without a cap the simulation can keep making tiny position
          // adjustments for up to ~15s by default, so nodes drift slightly
          // out from under the cursor right after they visually look settled.
          cooldownTime={2500}
          nodeId="id"
          nodeLabel={(node) => {
            const n = node as GraphNode;
            if (n.isIdea) return "Your idea";
            const band = n.relevanceScore ? similarityBand(n.relevanceScore) : null;
            const verdict = n.verdict ? ` · ${n.verdict.replace(/_/g, " ")}` : "";
            return `${n.label}${band !== null ? ` (${band.toLowerCase()} text similarity${verdict})` : ""}`;
          }}
          linkWidth={(link) => ((link as GraphLink).kind === "citation" ? 1.5 : 1)}
          linkColor={(link) =>
            (link as GraphLink).kind === "citation" ? CITATION_LINK_COLOR : "rgba(11,11,11,0.12)"
          }
          linkDirectionalArrowLength={(link) => ((link as GraphLink).kind === "citation" ? 5 : 0)}
          linkDirectionalArrowRelPos={0.85}
          onNodeClick={(node) => {
            const n = node as GraphNode;
            if (!n.isIdea && n.link) window.open(n.link, "_blank", "noopener,noreferrer");
          }}
          onNodeHover={(node) => {
            if (containerRef.current) {
              containerRef.current.style.cursor = node && !(node as GraphNode).isIdea ? "pointer" : "default";
            }
          }}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const n = node as GraphNode & { x: number; y: number };
            const radius = n.val;

            // Surface ring so overlapping nodes stay legible (per dataviz
            // mark spec: a ring in the surface color, not a border stroke).
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius + 2, 0, 2 * Math.PI);
            ctx.fillStyle = SURFACE_RING_COLOR;
            ctx.fill();

            ctx.beginPath();
            ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI);
            ctx.fillStyle = n.clusterColor;
            ctx.fill();

            // The idea node is the one permanently-labeled "extreme" (it's
            // the single most important node) — every other node relies on
            // the hover tooltip instead of a permanent label, to avoid
            // flooding the graph with 20+ overlapping text labels.
            if (n.isIdea) {
              const label = "Your idea";
              const fontSize = 12 / globalScale;
              ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = "#0b0b0b";
              ctx.fillText(label, n.x, n.y + radius + 4);
            }
          }}
          nodePointerAreaPaint={(node, color, ctx) => {
            const n = node as GraphNode & { x: number; y: number };
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.val + 2, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          }}
        />
      )}
    </div>
  );
}
