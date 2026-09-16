import { useState } from "react";
import LandscapeGraph from "@/components/LandscapeGraph";
import type { AnalysisResult, NoveltyVerdict, SourceType } from "@/types/analysis";

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

const VERDICT_LABELS: Record<NoveltyVerdict, string> = {
  blocking: "Blocking",
  partially_overlapping: "Partially overlapping",
  not_relevant: "Not relevant",
};

const VERDICT_STYLES: Record<NoveltyVerdict, string> = {
  blocking: "bg-red-100 text-red-800",
  partially_overlapping: "bg-yellow-100 text-yellow-800",
  not_relevant: "bg-neutral-100 text-neutral-600",
};

function ResultCard({
  result,
  verdict,
}: {
  result: AnalysisResult["ranked_results"][number];
  verdict: NoveltyVerdict | null;
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

export default function ResultsView({ result }: { result: AnalysisResult }) {
  const verdictByResultId = new Map(
    result.candidate_assessments.map((a) => [a.result_id, a.verdict])
  );

  const confidencePct = Math.round(result.overall_novelty_confidence * 100);

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-neutral-900">Novelty confidence</h2>
        <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-neutral-200">
          <div
            className="h-full rounded-full bg-neutral-900 transition-all"
            style={{ width: `${confidencePct}%` }}
          />
        </div>
        <p className="mt-2 text-sm text-neutral-500">
          {confidencePct}% — {confidencePct >= 70
            ? "This idea looks largely novel against what we found."
            : confidencePct >= 40
              ? "This idea has meaningful overlap with existing prior art."
              : "This idea closely overlaps with existing prior art."}
        </p>
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

      <div className="rounded-lg border border-orange-200 bg-orange-50 p-5">
        <h2 className="font-semibold text-orange-900">India patentability signal</h2>
        <div className="mt-3 grid grid-cols-2 gap-4">
          <div>
            <div className="text-2xl font-bold text-orange-900">
              {result.india_status.blocking_in_india}
            </div>
            <div className="text-sm text-orange-800">Active & blocking in India</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-orange-900">
              {result.india_status.active_elsewhere_only}
            </div>
            <div className="text-sm text-orange-800">Active elsewhere, not in India</div>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-green-200 bg-green-50 p-5">
        <h2 className="font-semibold text-green-900">How to differentiate your idea</h2>
        <ul className="mt-3 space-y-2">
          {result.differentiation_suggestions.map((suggestion, i) => (
            <li key={i} className="flex gap-2 text-sm text-green-900">
              <span className="text-green-600">→</span>
              <span>{suggestion}</span>
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

      <div>
        <h2 className="text-xl font-bold text-neutral-900">Prior art & related results</h2>
        <div className="mt-4 space-y-3">
          {result.ranked_results.map((r) => (
            <ResultCard key={r.id} result={r} verdict={verdictByResultId.get(r.id) ?? null} />
          ))}
        </div>
      </div>
    </div>
  );
}
