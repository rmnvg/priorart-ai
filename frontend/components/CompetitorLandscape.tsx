import type { AssigneeStat } from "@/types/analysis";

// One series (share of results by assignee) -> every bar takes the same
// slot-1 hue. Coloring bars by their own value would spend the identity
// channel re-encoding what bar length already shows. No legend box needed
// for a single series — the heading already names what's plotted.
const BAR_COLOR = "#2a78d6";

export default function CompetitorLandscape({ assignees }: { assignees: AssigneeStat[] }) {
  if (assignees.length === 0) return null;

  const maxPct = Math.max(...assignees.map((a) => a.percentage));

  return (
    <div>
      <h2 className="text-xl font-bold text-neutral-900">Who owns this space</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Share of the closest-matching search results by patent assignee, from the most
        precisely-targeted search query.
      </p>
      <div className="mt-4 space-y-3">
        {assignees.map((a) => (
          <div key={a.name}>
            <div className="mb-1 flex items-baseline justify-between text-sm">
              <span className="truncate pr-2 text-neutral-700">{a.name}</span>
              <span className="shrink-0 font-medium text-neutral-900">
                {a.percentage.toFixed(1)}%
              </span>
            </div>
            <div className="h-5 w-full overflow-hidden rounded-sm bg-neutral-100">
              <div
                className="h-full rounded-sm"
                style={{
                  width: `${(a.percentage / maxPct) * 100}%`,
                  backgroundColor: BAR_COLOR,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
