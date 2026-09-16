import type { PipelineStage } from "@/types/analysis";

const STAGES: { key: PipelineStage; label: string }[] = [
  { key: "generating_queries", label: "Generating search queries" },
  { key: "searching_patents", label: "Searching patents" },
  { key: "searching_scholar", label: "Reviewing academic literature" },
  { key: "checking_market_availability", label: "Checking market availability" },
  { key: "ranking_results", label: "Ranking & deduplicating results" },
  { key: "scoring_novelty", label: "Scoring novelty & building citations" },
];

interface ProgressChecklistProps {
  currentStage: PipelineStage | null;
  isComplete: boolean;
}

export default function ProgressChecklist({ currentStage, isComplete }: ProgressChecklistProps) {
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
    </div>
  );
}
