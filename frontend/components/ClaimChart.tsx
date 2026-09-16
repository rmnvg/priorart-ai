import { highlightSpans, isSpanFindable } from "@/lib/highlightText";
import type { ClaimChart as ClaimChartType } from "@/types/analysis";

// Light "highlighter" tones, not the categorical data-identity palette —
// these mark matched spans in prose, always paired with the concept label in
// the legend below, so identity never rests on color alone.
const HIGHLIGHT_COLORS = ["#fef08a", "#bbf7d0", "#bfdbfe", "#fbcfe8", "#e9d5ff", "#fed7aa"];

export default function ClaimChart({
  claimChart,
  ideaText,
}: {
  claimChart: ClaimChartType;
  ideaText: string;
}) {
  // The LLM is asked to copy spans verbatim but doesn't always manage it
  // (especially from the longer candidate text). Highlighting only the idea
  // side for a pair whose candidate side didn't match would look broken —
  // half-highlighted, half-plain. Only keep pairs findable on BOTH sides, so
  // every rendered pair reads as an intentional, real match.
  const findablePairs = claimChart.pairs.filter(
    (p) =>
      isSpanFindable(ideaText, p.idea_span) && isSpanFindable(claimChart.candidate_text, p.candidate_span)
  );

  if (findablePairs.length === 0) return null;

  const coloredPairs = findablePairs.map((pair, i) => ({
    ...pair,
    color: HIGHLIGHT_COLORS[i % HIGHLIGHT_COLORS.length],
  }));

  const ideaSpans = coloredPairs.map((p, i) => ({
    text: p.idea_span,
    color: p.color,
    key: `idea-${i}`,
  }));
  const candidateSpans = coloredPairs.map((p, i) => ({
    text: p.candidate_span,
    color: p.color,
    key: `candidate-${i}`,
  }));

  return (
    <div>
      <h2 className="text-xl font-bold text-neutral-900">Claim chart</h2>
      <p className="mt-1 text-sm text-neutral-500">
        A side-by-side comparison of your idea against its closest match — the technique
        patent professionals use to compare an invention to prior art claim by claim.
        Matching colors mark the same technical concept in both texts.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-neutral-200 p-4">
          <h3 className="text-sm font-semibold text-neutral-700">Your idea</h3>
          <p className="mt-2 whitespace-pre-wrap text-sm text-neutral-800">
            {highlightSpans(ideaText, ideaSpans)}
          </p>
        </div>
        <div className="rounded-lg border border-neutral-200 p-4">
          <h3 className="text-sm font-semibold text-neutral-700">
            Closest match: {claimChart.candidate_title}
          </h3>
          <p className="mt-2 whitespace-pre-wrap text-sm text-neutral-800">
            {highlightSpans(claimChart.candidate_text, candidateSpans)}
          </p>
          <a
            href={claimChart.candidate_link}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-xs text-blue-600 underline"
          >
            View source
          </a>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        {coloredPairs.map((p, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs text-neutral-600">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: p.color }}
            />
            {p.concept}
          </div>
        ))}
      </div>
    </div>
  );
}
