import { buildDecision } from "@/lib/decision";
import type { Translate } from "@/lib/i18n";
import type { AnalysisResult, NoveltyVerdict } from "@/types/analysis";

const VERDICT_WORDS: Record<NoveltyVerdict, string> = {
  blocking: "could block this idea as described",
  partially_overlapping: "overlaps in part",
  not_relevant: "not a real match",
};

// The report's answer in three lines, before any of the detail: what's
// closest, what's different, what to do. Phrased as "in the searched
// evidence" — the search can show overlap, never prove its absence.
export default function DecisionSummary({
  result,
  t,
  suggestions,
}: {
  result: AnalysisResult;
  t: Translate;
  suggestions: string[]; // in the reader's language, parallel to the English list
}) {
  const decision = buildDecision(result);
  const next = decision.nextSuggestionIndex !== null ? suggestions[decision.nextSuggestionIndex] : null;
  const closestType = decision.closest
    ? result.ranked_results.find((r) => r.id === decision.closest!.result_id)?.source_type
    : undefined;

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
      <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
          {t("decision_closest")}
        </p>
        {decision.closest ? (
          <>
            {closestType && closestType !== "patent" && (
              <span className="mt-1.5 inline-block rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-600">
                {closestType === "product" ? "Existing product" : "Academic paper"}
              </span>
            )}
            <a
              href={decision.closest.link}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1.5 block font-medium text-neutral-900 underline decoration-neutral-300 underline-offset-2 hover:decoration-neutral-900"
            >
              {decision.closest.title}
            </a>
            <p className="mt-1 text-sm text-neutral-600">
              {VERDICT_WORDS[decision.closest.verdict]}
              {decision.closest.overlapping_elements.length > 0 &&
                ` — shares ${decision.closest.overlapping_elements.slice(0, 2).join("; ")}`}
            </p>
          </>
        ) : (
          <p className="mt-1.5 text-sm text-neutral-600">
            No searched document was assessed as a real match.
          </p>
        )}
      </div>

      <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
          {t("decision_difference")}
        </p>
        {decision.differences.length > 0 ? (
          <>
            <ul className="mt-1.5 space-y-1 text-sm text-neutral-800">
              {decision.differences.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
            <p className="mt-1.5 text-xs text-neutral-400">{t("decision_difference_note")}</p>
          </>
        ) : (
          <p className="mt-1.5 text-sm text-neutral-600">
            {decision.closest
              ? "No clear difference from the closest match was found."
              : "See the full results below."}
          </p>
        )}
      </div>

      <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
          {t("decision_next")}
        </p>
        <p className="mt-1.5 text-sm text-neutral-800">
          {next ?? "Talk to a registered patent agent about the closest match above."}
        </p>
        {next && (
          <p className="mt-1.5 text-xs text-neutral-400">
            Try it with &ldquo;Apply &amp; re-check&rdquo; below, or preview how an examiner
            would respond.
          </p>
        )}
      </div>
    </div>
  );
}
