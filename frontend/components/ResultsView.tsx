import { useState } from "react";
import ClaimChartView from "@/components/ClaimChart";
import CompetitorLandscape from "@/components/CompetitorLandscape";
import LandscapeGraph from "@/components/LandscapeGraph";
import NoveltyVerdict from "@/components/NoveltyVerdict";
import type { AnalysisResult, NoveltyVerdict as Verdict, SourceType } from "@/types/analysis";

// How many prior-art cards to show before collapsing. A full run returns
// 30-40 results; rendering them all buries the analysis under an endless
// scroll, so the rest sit behind an expander.
const VISIBLE_RESULTS = 6;

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="text-2xl font-semibold text-neutral-900">{value}</div>
      <div className="mt-0.5 text-xs text-neutral-500">{label}</div>
    </div>
  );
}

const SOURCE_LABELS: Record<SourceType, string> = {
  patent: "Patent",
  scholar: "Academic paper",
  product: "Existing product",
};

const SOURCE_STYLES: Record<SourceType, string> = {
  patent: "bg-blue-100 text-blue-800",
  scholar: "bg-purple-100 text-purple-800",
  product: "bg-amber-100 text-amber-800",
};

const VERDICT_LABELS: Record<Verdict, string> = {
  blocking: "Blocking",
  partially_overlapping: "Partially overlapping",
  not_relevant: "Not relevant",
};

const VERDICT_STYLES: Record<Verdict, string> = {
  blocking: "bg-red-100 text-red-800",
  partially_overlapping: "bg-yellow-100 text-yellow-800",
  not_relevant: "bg-neutral-100 text-neutral-600",
};

function ResultCard({
  result,
  verdict,
}: {
  result: AnalysisResult["ranked_results"][number];
  verdict: Verdict | null;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-neutral-200 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded px-2 py-0.5 text-xs font-medium ${SOURCE_STYLES[result.source_type]}`}>
          {SOURCE_LABELS[result.source_type]}
        </span>
        {verdict && (
          <span className={`rounded px-2 py-0.5 text-xs font-medium ${VERDICT_STYLES[verdict]}`}>
            {VERDICT_LABELS[verdict]}
          </span>
        )}
        <span className="ml-auto text-xs text-neutral-400">
          {Math.round(result.relevance_score * 100)}% match
        </span>
      </div>
      <h3 className="mt-2 font-medium text-neutral-900">{result.title}</h3>
      <p className="mt-1 text-sm text-neutral-500 line-clamp-2">{result.snippet}</p>
      {(result.assignee || result.priority_date) && (
        <p className="mt-1 text-xs text-neutral-400">
          {result.assignee}
          {result.assignee && result.priority_date && " · "}
          {result.priority_date && `filed ${result.priority_date}`}
        </p>
      )}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="mt-2 text-sm text-neutral-500 underline hover:text-neutral-900"
      >
        {expanded ? "Hide source" : "View source"}
      </button>
      {expanded && (
        <a
          href={result.link}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 block truncate text-sm text-blue-600 underline"
        >
          {result.link}
        </a>
      )}
    </div>
  );
}

interface ResultsViewProps {
  result: AnalysisResult;
  onApplySuggestion?: (suggestion: string) => void;
  previousConfidence?: number | null;
  appliedSuggestion?: string | null;
}

export default function ResultsView({
  result,
  onApplySuggestion,
  previousConfidence,
  appliedSuggestion,
}: ResultsViewProps) {
  const [showAllResults, setShowAllResults] = useState(false);

  const verdictByResultId = new Map(
    result.candidate_assessments.map((a) => [a.result_id, a.verdict])
  );

  const confidencePct = Math.round(result.overall_novelty_confidence * 100);
  const previousPct = previousConfidence != null ? Math.round(previousConfidence * 100) : null;

  const visibleResults = showAllResults
    ? result.ranked_results
    : result.ranked_results.slice(0, VISIBLE_RESULTS);
  // Based on the total, not the currently-hidden count — otherwise expanding
  // drops the count to zero and the collapse control disappears with it.
  const isCollapsible = result.ranked_results.length > VISIBLE_RESULTS;

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8">
      {previousPct !== null && (
        <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-blue-500">
            Re-checked after your change
          </p>
          <p className="mt-2 text-sm italic text-blue-900">&ldquo;{appliedSuggestion}&rdquo;</p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <span className="text-3xl font-semibold text-neutral-400 line-through decoration-neutral-300">
              {previousPct}%
            </span>
            <span className="text-2xl text-blue-400">→</span>
            <span
              className={`text-3xl font-semibold ${confidencePct > previousPct ? "text-green-600" : "text-neutral-900"}`}
            >
              {confidencePct}%
            </span>
            <span
              className={`rounded-full px-2.5 py-1 text-sm font-medium ${
                confidencePct > previousPct
                  ? "bg-green-100 text-green-700"
                  : confidencePct < previousPct
                    ? "bg-neutral-200 text-neutral-600"
                    : "bg-neutral-100 text-neutral-500"
              }`}
            >
              {confidencePct > previousPct
                ? `+${confidencePct - previousPct} points more novel`
                : confidencePct < previousPct
                  ? `${confidencePct - previousPct} points — this change overlaps more prior art`
                  : "No change"}
            </span>
          </div>
        </div>
      )}

      <NoveltyVerdict confidence={result.overall_novelty_confidence} />

      <div className="grid grid-cols-3 gap-3">
        <StatTile label="Results analyzed" value={result.ranked_results.length} />
        <StatTile
          label="Assessed in depth"
          value={result.candidate_assessments.length}
        />
        <StatTile
          label="Blocking in India"
          value={result.india_status.blocking_in_india}
        />
      </div>

      <div>
        <h2 className="text-xl font-bold text-neutral-900">Patent landscape</h2>
        <p className="mt-1 text-sm text-neutral-500">
          Each dot is a result from the search, sized and pulled closer by how well it
          matches your idea, and colored by patent classification. Hover a dot for
          details, click to open the source.
        </p>
        <div className="mt-4">
          <LandscapeGraph result={result} />
        </div>
      </div>

      <CompetitorLandscape assignees={result.top_assignees} />

      <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
        <div className="border-l-4 border-orange-400 p-5">
          <h2 className="font-semibold text-neutral-900">India patentability signal</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Whether the closest matches are actually in force in India, or only protected
            elsewhere — where the same idea may still be open.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-orange-50 p-3">
              <div className="text-2xl font-semibold text-orange-900">
                {result.india_status.blocking_in_india}
              </div>
              <div className="text-sm text-orange-800">Active &amp; blocking in India</div>
            </div>
            <div className="rounded-lg bg-neutral-50 p-3">
              <div className="text-2xl font-semibold text-neutral-900">
                {result.india_status.active_elsewhere_only}
              </div>
              <div className="text-sm text-neutral-600">Active elsewhere, not in India</div>
            </div>
          </div>
          <p className="mt-3 text-xs text-neutral-400">
            Google Patents reports Indian legal status as unknown more often than not, so
            treat this as a conservative floor rather than a complete picture.
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-green-200 bg-green-50/60 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-green-900">How to differentiate your idea</h2>
        <p className="mt-1 text-sm text-green-800/80">
          Specific changes that would move this idea away from its closest matches. Apply one
          to re-run the analysis and watch the verdict move.
        </p>
        <ul className="mt-4 space-y-2">
          {result.differentiation_suggestions.map((suggestion, i) => (
            <li
              key={i}
              className="flex items-start justify-between gap-3 rounded-lg bg-white/70 p-3 text-sm text-green-900"
            >
              <span className="flex gap-2.5">
                <span className="font-semibold text-green-600">{i + 1}</span>
                <span>{suggestion}</span>
              </span>
              {onApplySuggestion && (
                <button
                  onClick={() => onApplySuggestion(suggestion)}
                  className="shrink-0 whitespace-nowrap rounded-md bg-green-700 px-2.5 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-green-800"
                >
                  Apply & re-check →
                </button>
              )}
            </li>
          ))}
        </ul>
        {result.citations.length > 0 && (
          <div className="mt-4 border-t border-green-200 pt-3">
            <p className="text-xs font-medium text-green-800">Based on:</p>
            <ul className="mt-1 space-y-1">
              {result.citations.map((c, i) => (
                <li key={i} className="text-xs text-green-700">
                  <a href={c.link} target="_blank" rel="noopener noreferrer" className="underline">
                    {c.title}
                  </a>
                  <span className="text-green-600"> — {c.claim}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {result.claim_chart && (
        <ClaimChartView claimChart={result.claim_chart} ideaText={result.idea_text} />
      )}

      <div>
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-bold text-neutral-900">Prior art & related results</h2>
          <span className="text-sm text-neutral-400">{result.ranked_results.length} found</span>
        </div>
        <div className="mt-4 space-y-3">
          {visibleResults.map((r) => (
            <ResultCard key={r.id} result={r} verdict={verdictByResultId.get(r.id) ?? null} />
          ))}
        </div>
        {isCollapsible && (
          <button
            onClick={() => setShowAllResults((v) => !v)}
            className="mt-4 w-full rounded-lg border border-neutral-300 bg-white py-2.5 text-sm font-medium text-neutral-700 shadow-sm transition hover:bg-neutral-50"
          >
            {showAllResults ? "Show fewer results" : `Show all ${result.ranked_results.length} results`}
          </button>
        )}
      </div>
    </div>
  );
}
