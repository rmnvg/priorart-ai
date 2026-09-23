import type { PipelineStage } from "@/types/analysis";

const STAGES: { key: PipelineStage; label: string }[] = [
  { key: "generating_queries", label: "Generating search queries" },
  { key: "searching_patents", label: "Searching patents" },
  { key: "searching_scholar", label: "Reviewing academic literature" },
  { key: "checking_market_availability", label: "Checking market availability" },
  { key: "ranking_results", label: "Ranking & deduplicating results" },
  { key: "refining_search", label: "Refining the search in patent terminology" },
  { key: "scoring_novelty", label: "Scoring novelty & building citations" },
];

interface ProgressChecklistProps {
  currentStage: PipelineStage | null;
  isComplete: boolean;
  // The pipeline's latest message — where a stage makes a decision (the
  // language it detected, the terms the refinement agent found), this is
  // where the user sees it.
  message?: string | null;
}

export default function ProgressChecklist({
  currentStage,
  isComplete,
  message,
}: ProgressChecklistProps) {
  const currentIndex = currentStage ? STAGES.findIndex((s) => s.key === currentStage) : -1;

  return (
    <div className="mx-auto w-full max-w-md">
      <ul className="space-y-4">
        {STAGES.map((stage, i) => {
          const isPast = isComplete || i < currentIndex;
          const isActive = !isComplete && i === currentIndex;
          return (
            <li key={stage.key} className="flex items-center gap-3">
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs ${
                  isPast
                    ? "bg-green-600 text-white"
                    : isActive
                      ? "bg-neutral-900 text-white"
                      : "bg-neutral-200 text-neutral-400"
                }`}
              >
                {isPast ? (
                  "✓"
                ) : isActive ? (
                  <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                ) : (
                  ""
                )}
              </span>
              <span
                className={
                  isPast
                    ? "text-neutral-900"
                    : isActive
                      ? "font-medium text-neutral-900"
                      : "text-neutral-400"
                }
              >
                {stage.label}
              </span>
            </li>
          );
        })}
      </ul>
      {message && !isComplete && (
        <p
          key={message}
          className="mt-6 animate-[fadeIn_300ms_ease-out] rounded-lg border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-600 shadow-sm"
        >
          {message}
        </p>
      )}
    </div>
  );
}
