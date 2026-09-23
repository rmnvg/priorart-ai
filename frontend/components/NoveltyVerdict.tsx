import type { LabelKey, Translate } from "@/lib/i18n";

// The single number the whole report leads with, so it gets hero treatment:
// one large figure per view, proportional (not tabular) figures at display
// size, and a meter whose fill carries severity against a lighter step of the
// same hue. Status color never stands alone — the verdict word sits beside it.
const LEVELS: { min: number; color: string; label: LabelKey; blurb: LabelKey }[] = [
  { min: 0.65, color: "#0ca30c", label: "looks_novel", blurb: "looks_novel_blurb" },
  { min: 0.35, color: "#fab219", label: "partial_overlap", blurb: "partial_overlap_blurb" },
  { min: 0, color: "#d03b3b", label: "heavy_overlap", blurb: "heavy_overlap_blurb" },
];

export function verdictLevel(confidence: number) {
  return LEVELS.find((l) => confidence >= l.min) ?? LEVELS[LEVELS.length - 1];
}

export default function NoveltyVerdict({ confidence, t }: { confidence: number; t: Translate }) {
  const pct = Math.round(confidence * 100);
  const level = verdictLevel(confidence);

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
        {t("novelty_verdict")}
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
          {t(level.label)}
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

      <p className="mt-3 text-sm text-neutral-600">{t(level.blurb)}</p>
    </div>
  );
}
