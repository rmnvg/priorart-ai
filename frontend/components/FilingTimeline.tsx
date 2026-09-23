"use client";

import { useState } from "react";
import { useElementWidth } from "@/lib/useElementWidth";
import type { RankedResult } from "@/types/analysis";

// One series (patent filings per year) -> one hue, no legend box; the heading
// names what's plotted. Same slot-1 blue as the assignee bars.
const BAR_COLOR = "#2a78d6";
const GRID_COLOR = "#e5e5e5";
const HEIGHT = 190;
const MARGIN = { top: 24, right: 8, bottom: 24, left: 28 };
const MAX_BAR_WIDTH = 24;
const PATENT_TERM_YEARS = 20;
const RECENT_WINDOW_YEARS = 5;
export const MIN_FILINGS_TO_PLOT = 3;

function roundedTopBar(x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`;
}

export function filingsByYear(results: RankedResult[]) {
  const counts = new Map<number, number>();
  for (const r of results) {
    if (r.source_type !== "patent" || !r.priority_date) continue;
    const year = Number(r.priority_date.slice(0, 4));
    if (Number.isFinite(year) && year > 1900) counts.set(year, (counts.get(year) ?? 0) + 1);
  }
  if (counts.size === 0) return [];
  const years = [...counts.keys()];
  const series: { year: number; count: number }[] = [];
  // Fill empty years with zero — a gap in filings is information, and
  // skipping it would make the axis lie about time.
  for (let y = Math.min(...years); y <= Math.max(...years); y++) {
    series.push({ year: y, count: counts.get(y) ?? 0 });
  }
  return series;
}

export default function FilingTimeline({ results }: { results: RankedResult[] }) {
  const [containerRef, width] = useElementWidth<HTMLDivElement>();
  const [hovered, setHovered] = useState<number | null>(null);

  const series = filingsByYear(results);
  const total = series.reduce((sum, d) => sum + d.count, 0);
  if (total < MIN_FILINGS_TO_PLOT) return null;

  const currentYear = new Date().getFullYear();
  const recent = series
    .filter((d) => d.year > currentYear - RECENT_WINDOW_YEARS)
    .reduce((sum, d) => sum + d.count, 0);
  const expiryYear = currentYear - PATENT_TERM_YEARS;

  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right);
  const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;
  const band = series.length > 0 ? innerW / series.length : 0;
  const barW = Math.max(2, Math.min(MAX_BAR_WIDTH, band - 2));
  const maxCount = Math.max(...series.map((d) => d.count));
  const yTicks = maxCount <= 4 ? [...Array(maxCount + 1).keys()] : [0, Math.ceil(maxCount / 2), maxCount];
  const y = (v: number) => MARGIN.top + innerH - (v / maxCount) * innerH;
  // Label every Nth year so ~36px of room stays between labels.
  const labelEvery = Math.max(1, Math.ceil(36 / Math.max(band, 1)));
  const expiryIndex = series.findIndex((d) => d.year === expiryYear);
  const hoveredDatum = hovered !== null ? series[hovered] : null;

  return (
    <div>
      <h3 className="font-semibold text-neutral-900">Filing activity</h3>
      <p className="mt-1 text-sm text-neutral-500">
        Related patents by priority year.{" "}
        <span className="font-medium text-neutral-800">
          {recent} of {total}
        </span>{" "}
        were filed in the last {RECENT_WINDOW_YEARS} years
        {recent / total >= 0.4 ? " — an active, crowded space." : "."}
      </p>

      <div ref={containerRef} className="relative mt-3" onMouseLeave={() => setHovered(null)}>
        {width > 0 && (
          <svg width={width} height={HEIGHT} role="img" aria-label="Related patent filings per year">
            {yTicks.map((t) => (
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

            {expiryIndex >= 0 && (
              <g>
                <line
                  x1={MARGIN.left + band * expiryIndex}
                  x2={MARGIN.left + band * expiryIndex}
                  y1={MARGIN.top - 12}
                  y2={MARGIN.top + innerH}
                  stroke="#a3a3a3"
                />
                {/* Full label to the left when there's room for it; a
                    short one on the right when the line sits near the edge. */}
                {band * expiryIndex > 170 ? (
                  <text
                    x={MARGIN.left + band * expiryIndex - 4}
                    y={MARGIN.top - 8}
                    textAnchor="end"
                    className="fill-neutral-500 text-[10px]"
                  >
                    ← 20+ years old: term likely over
                  </text>
                ) : (
                  <text
                    x={MARGIN.left + band * expiryIndex + 4}
                    y={MARGIN.top - 8}
                    className="fill-neutral-500 text-[10px]"
                  >
                    20-year patent term line
                  </text>
                )}
              </g>
            )}

            {series.map((d, i) => {
              const x = MARGIN.left + band * i + (band - barW) / 2;
              const h = MARGIN.top + innerH - y(d.count);
              return (
                <g key={d.year}>
                  {d.count > 0 && (
                    <path
                      d={roundedTopBar(x, y(d.count), barW, h, 4)}
                      fill={BAR_COLOR}
                      opacity={hovered === null || hovered === i ? 1 : 0.55}
                    />
                  )}
                  {i % labelEvery === 0 && (
                    <text
                      x={MARGIN.left + band * i + band / 2}
                      y={HEIGHT - 6}
                      textAnchor="middle"
                      className="fill-neutral-400 text-[10px] tabular-nums"
                    >
                      {d.year}
                    </text>
                  )}
                  {/* Hit target spans the whole band, not just the bar. */}
                  <rect
                    x={MARGIN.left + band * i}
                    y={MARGIN.top}
                    width={band}
                    height={innerH}
                    fill="transparent"
                    onMouseEnter={() => setHovered(i)}
                  />
                </g>
              );
            })}
          </svg>
        )}

        {hoveredDatum && (
          <div
            className="pointer-events-none absolute rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs shadow-sm"
            style={{
              left: Math.min(MARGIN.left + band * (hovered ?? 0) + band / 2, width - 90),
              top: Math.max(0, y(hoveredDatum.count) - 34),
            }}
          >
            <span className="font-medium text-neutral-900">{hoveredDatum.year}</span>
            <span className="text-neutral-500">
              {" "}
              · {hoveredDatum.count} patent{hoveredDatum.count === 1 ? "" : "s"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
