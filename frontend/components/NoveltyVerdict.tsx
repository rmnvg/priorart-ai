// The single number the whole report leads with, so it gets hero treatment:
// one large figure per view, proportional (not tabular) figures at display
// size, and a meter whose fill carries severity against a lighter step of the
// same hue. Status color never stands alone — the verdict word sits beside it.
const LEVELS = [
  {
    min: 0.65,
    color: "#0ca30c",
    label: "Looks novel",
    blurb: "No strong blocking prior art surfaced for this idea.",
  },
  {
    min: 0.35,
    color: "#fab219",
    label: "Partial overlap",
    blurb: "Real prior art shares elements with this idea, but it isn't fully anticipated.",
  },
  {
    min: 0,
    color: "#d03b3b",
    label: "Heavy overlap",
    blurb: "Close matches already exist — differentiation will be essential.",
  },
];

export default function NoveltyVerdict({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const level = LEVELS.find((l) => confidence >= l.min) ?? LEVELS[LEVELS.length - 1];

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
        Novelty verdict
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <span
          className="text-6xl font-semibold leading-none tracking-tight"
          style={{ color: level.color }}
        >
          {pct}%
        </span>
        <span
          className="rounded-full px-3 py-1 text-sm font-semibold"
          style={{ backgroundColor: `${level.color}1a`, color: level.color }}
        >
          {level.label}
        </span>
      </div>

      <div
        className="mt-5 h-2.5 w-full overflow-hidden rounded-full"
        style={{ backgroundColor: `${level.color}1f` }}
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Novelty confidence"
      >
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${pct}%`, backgroundColor: level.color }}
        />
      </div>

      <p className="mt-3 text-sm text-neutral-600">{level.blurb}</p>
    </div>
  );
}
