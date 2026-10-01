import type { AnalysisResult, RankedResult } from "@/types/analysis";

export function patent(overrides: Partial<RankedResult> = {}): RankedResult {
  return {
    id: "patent/US1/en",
    source_type: "patent",
    title: "A patent",
    snippet: "snippet",
    link: "https://patents.google.com/patent/US1/en",
    relevance_score: 0.5,
    cpc_code: "A61B5/02",
    priority_date: "2010-01-01",
    ...overrides,
  };
}

export function analysis(overrides: Partial<AnalysisResult> = {}): AnalysisResult {
  return {
    idea_text: "A folding paddle",
    ranked_results: [],
    candidate_assessments: [],
    overall_novelty_confidence: 0.5,
    differentiation_suggestions: [],
    citations: [],
    india_status: { related_active_in_india: 0, active_elsewhere_only: 0 },
    claim_chart: null,
    top_assignees: [],
    public_domain: null,
    ...overrides,
  };
}
