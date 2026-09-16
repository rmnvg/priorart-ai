// Shared contract between the FastAPI backend and the Next.js frontend
// for the POST /analyze SSE stream. Keep in sync with backend/app/pipeline.

export type PipelineStage =
  | "generating_queries"
  | "searching_patents"
  | "searching_scholar"
  | "checking_market_availability"
  | "ranking_results"
  | "scoring_novelty"
  | "done";

export interface ProgressEvent {
  type: "progress";
  stage: PipelineStage;
  message: string;
}

export type SourceType = "patent" | "scholar" | "product";

export interface RankedResult {
  id: string; // patent_id / scholar_id / product url
  source_type: SourceType;
  title: string;
  snippet: string;
  link: string;
  relevance_score: number; // 0-1
  cpc_code?: string | null;
  cpc_description?: string | null;
  country_status?: Record<string, string>; // e.g. { US: "ACTIVE", IN: "UNKNOWN" }
  query_types?: string[]; // which generated queries surfaced this result
}

export type NoveltyVerdict = "blocking" | "partially_overlapping" | "not_relevant";

export interface CandidateNoveltyAssessment {
  result_id: string;
  title: string;
  link: string;
  overlapping_elements: string[];
  differences: string[];
  verdict: NoveltyVerdict;
}

export interface IndiaStatus {
  blocking_in_india: number;
  active_elsewhere_only: number;
}

export interface Citation {
  claim: string;
  result_id: string;
  title: string;
  link: string;
}

export interface ClaimChartPair {
  concept: string;
  idea_span: string;
  candidate_span: string;
}

export interface ClaimChart {
  candidate_result_id: string;
  candidate_title: string;
  candidate_link: string;
  candidate_text: string;
  pairs: ClaimChartPair[];
}

export interface AnalysisResult {
  idea_text: string;
  ranked_results: RankedResult[];
  candidate_assessments: CandidateNoveltyAssessment[];
  overall_novelty_confidence: number; // 0-1
  differentiation_suggestions: string[];
  citations: Citation[];
  india_status: IndiaStatus;
  claim_chart: ClaimChart | null;
}

export interface ResultEvent {
  type: "result";
  data: AnalysisResult;
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type AnalyzeStreamEvent = ProgressEvent | ResultEvent | ErrorEvent;

export interface AnalyzeRequest {
  idea_text: string;
}
