"use client";

import { useState } from "react";
import { useElementWidth } from "@/lib/useElementWidth";
import type { MarketTrend } from "@/types/analysis";

// One series -> one hue, no legend box. Line at 2px with a ~10% area wash.
const LINE_COLOR = "#2a78d6";
const GRID_COLOR = "#e5e5e5";
const HEIGHT = 190;
const MARGIN = { top: 16, right: 12, bottom: 24, left: 28 };

const DIRECTION_COPY: Record<MarketTrend["direction"], { arrow: string; label: string }> = {
  rising: { arrow: "↗", label: "Rising" },
  steady: { arrow: "→", label: "Steady" },
  declining: { arrow: "↘", label: "Declining" },
};

export default function MarketTrendChart({ trend }: { trend: MarketTrend }) {
  const [containerRef, width] = useElementWidth<HTMLDivElement>();
  const [hovered, setHovered] = useState<number | null>(null);

  const points = trend.points;
  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right);
  const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;
  const x = (i: number) => MARGIN.left + (points.length > 1 ? (i / (points.length - 1)) * innerW : 0);
  const y = (v: number) => MARGIN.top + innerH - (v / 100) * innerH;

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.value)}`).join(" ");
  const area = `${line} L${x(points.length - 1)},${y(0)} L${x(0)},${y(0)} Z`;
  const direction = DIRECTION_COPY[trend.direction];

  // Year labels at the first data point of each calendar year.
  const yearTicks: { i: number; year: string }[] = [];
  points.forEach((p, i) => {
    const year = p.date.match(/\d{4}/g)?.at(-1);
    if (year && !yearTicks.some((t) => t.year === year)) yearTicks.push({ i, year });
  });

  function handleMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left - MARGIN.left;
    const i = Math.round((px / Math.max(innerW, 1)) * (points.length - 1));
    setHovered(Math.max(0, Math.min(points.length - 1, i)));
  }

  const hoveredPoint = hovered !== null ? points[hovered] : null;

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold text-neutral-900">Market interest</h3>
        <span className="rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-medium text-neutral-700">
          {direction.arrow} {direction.label}
          {trend.change_pct !== 0 && ` ${trend.change_pct > 0 ? "+" : ""}${trend.change_pct}% vs. prior year`}
        </span>
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        Google search interest in &ldquo;{trend.keyword}&rdquo; over 5 years (100 = peak) — a
        rough read on whether people want this at all.
      </p>

      <div ref={containerRef} className="relative mt-3">
        {width > 0 && points.length > 1 && (
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            aria-label={`Search interest in ${trend.keyword} over time`}
            onMouseMove={handleMove}
            onMouseLeave={() => setHovered(null)}
          >
            {[0, 50, 100].map((t) => (
              <g key={t}>
                <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(t)} y2={y(t)} stroke={GRID_COLOR} />
                <text
                  x={MARGIN.left - 6}
                  y={y(t)}
                  textAnchor="end"
                  dominantBaseline="middle"
                  className="fill-neutral-400 text-[10px] tabular-nums"
                >
                  {t}
                </text>
              </g>
            ))}
            {yearTicks.map((t) => (
              <text
                key={t.year}
                x={x(t.i)}
                y={HEIGHT - 6}
                textAnchor="middle"
                className="fill-neutral-400 text-[10px] tabular-nums"
              >
                {t.year}
              </text>
            ))}

            <path d={area} fill={LINE_COLOR} opacity={0.1} />
            <path d={line} fill="none" stroke={LINE_COLOR} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

            {hovered !== null && hoveredPoint && (
              <g>
                <line x1={x(hovered)} x2={x(hovered)} y1={MARGIN.top} y2={y(0)} stroke="#a3a3a3" />
                <circle cx={x(hovered)} cy={y(hoveredPoint.value)} r={6} fill="#ffffff" />
                <circle cx={x(hovered)} cy={y(hoveredPoint.value)} r={4} fill={LINE_COLOR} />
              </g>
            )}
          </svg>
        )}

        {hovered !== null && hoveredPoint && (
          <div
            className="pointer-events-none absolute rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs shadow-sm"
            style={{ left: Math.min(x(hovered) + 8, width - 170), top: 0 }}
          >
            <span className="text-neutral-500">{hoveredPoint.date}</span>
            <span className="font-medium text-neutral-900"> · {hoveredPoint.value}</span>
          </div>
        )}
      </div>
    </div>
  );
}
