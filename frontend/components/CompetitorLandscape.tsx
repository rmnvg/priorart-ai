import type { AssigneeStat } from "@/types/analysis";

// One series (share of results by assignee) -> every bar takes the same
// slot-1 hue. Coloring bars by their own value would spend the identity
// channel re-encoding what bar length already shows. No legend box needed
// for a single series — the heading already names what's plotted.
const BAR_COLOR = "#2a78d6";

// Below this, no single holder is meaningfully dominant and the real story is
// fragmentation, not ranking — so we say so rather than letting a full-width
// bar at 3% imply market control.
const FRAGMENTED_THRESHOLD = 10;

/** Google Patents lists the same company under punctuation variants
 * ("Beta Air, Llc" vs "Beta Air Llc"). Merge them so one company doesn't
 * occupy two rows and look like two competitors. */
function mergeDuplicateAssignees(assignees: AssigneeStat[]): AssigneeStat[] {
  const merged = new Map<string, AssigneeStat>();
  for (const a of assignees) {
    const key = a.name.toLowerCase().replace(/[^a-z0-9一-鿿]/g, "");
    const existing = merged.get(key);
    if (existing) {
      existing.percentage += a.percentage;
    } else {
      merged.set(key, { ...a });
    }
  }
  return [...merged.values()].sort((a, b) => b.percentage - a.percentage);
}

export default function CompetitorLandscape({ assignees }: { assignees: AssigneeStat[] }) {
  if (assignees.length === 0) return null;

  const merged = mergeDuplicateAssignees(assignees);
  const maxPct = Math.max(...merged.map((a) => a.percentage));
  const isFragmented = maxPct < FRAGMENTED_THRESHOLD;

  return (
    <div>
      <h2 className="text-xl font-bold text-neutral-900">Who owns this space</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Share of the closest-matching search results by patent assignee, from the most
        precisely-targeted search query.
      </p>

      {isFragmented && (
        <p className="mt-3 rounded-lg bg-neutral-100 px-3 py-2 text-sm text-neutral-600">
          No dominant holder — the largest owns just {maxPct.toFixed(1)}% of matching
          results, so this space is fragmented across many parties rather than controlled
          by one.
        </p>
      )}

      <div className="mt-4 space-y-3">
        {merged.map((a) => (
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
                  // Bars are scaled relative to the top holder so the ranking
                  // stays legible at small absolute shares; the note above and
                  // the value on every row carry the true scale.
                  width: `${(a.percentage / maxPct) * 100}%`,
                  backgroundColor: BAR_COLOR,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-neutral-400">
        Bars are scaled relative to the largest holder ({maxPct.toFixed(1)}%), not to 100%.
      </p>
    </div>
  );
}
