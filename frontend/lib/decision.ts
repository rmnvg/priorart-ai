import type { AnalysisResult, CandidateNoveltyAssessment, NoveltyVerdict } from "@/types/analysis";

const SEVERITY: Record<NoveltyVerdict, number> = {
  blocking: 0,
  partially_overlapping: 1,
  not_relevant: 2,
};

export interface Decision {
  closest: CandidateNoveltyAssessment | null;
  differences: string[]; // how the idea differs from the closest match
  nextSuggestionIndex: number | null; // index into differentiation_suggestions
}

/** The three answers the report leads with, derived from what the analysis
 * already found — no extra calls. "Closest" is the most severe assessed
 * match (blocking over partial overlap), ties going to the more relevant. */
export function buildDecision(result: AnalysisResult): Decision {
  const relevance = new Map(result.ranked_results.map((r) => [r.id, r.relevance_score]));
  const closest =
    [...result.candidate_assessments]
      .filter((a) => a.verdict !== "not_relevant")
      .sort(
        (a, b) =>
          SEVERITY[a.verdict] - SEVERITY[b.verdict] ||
          (relevance.get(b.result_id) ?? 0) - (relevance.get(a.result_id) ?? 0)
      )[0] ?? null;

  return {
    closest,
    differences: closest ? closest.differences.slice(0, 2) : [],
    nextSuggestionIndex: result.differentiation_suggestions.length > 0 ? 0 : null,
  };
}
