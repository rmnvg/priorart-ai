// Shared contract between the FastAPI backend and the Next.js frontend
// for the POST /analyze SSE stream. Keep in sync with backend/app/pipeline.

export type PipelineStage =
  | "generating_queries"
  | "searching_patents"
  | "searching_scholar"
  | "checking_market_availability"
  | "ranking_results"
  | "refining_search"
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
  assignee?: string | null;
  priority_date?: string | null;
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
  india_filings_found?: number; // Indian Patent Office filings anywhere in the results
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

export interface AssigneeStat {
  name: string;
  percentage: number;
}

export type LapseReason = "term_expired" | "lapsed_early";

export interface PublicDomainEntry {
  id: string;
  title: string;
  link: string;
  priority_date?: string | null;
  assignee?: string | null;
  relevance_score: number;
  lapsed_in: string[];
  reason: LapseReason;
  years_since_filing?: number | null;
}

export interface PublicDomainSummary {
  count: number;
  patents_considered: number;
  entries: PublicDomainEntry[];
}

export interface SearchQueryInfo {
  type: string;
  query: string;
  rationale: string;
  country?: string | null;
  result_count: number;
  failed: boolean;
}

export interface SearchStrategy {
  core_concepts: string[];
  suggested_cpc?: string | null;
  queries: SearchQueryInfo[];
  market_query: string;
  trends_keyword?: string | null;
  serpapi_calls: Record<string, number>; // engine -> number of calls
  refinement_observation?: string | null; // what the refinement agent noticed
  refinement_terms?: string[];
}

export interface CitationDiscovery {
  id: string;
  title: string;
  link: string;
  assignee?: string | null;
  priority_date?: string | null;
  referenced_by: string[]; // ids of the top candidates that reference it
  direction: "backward" | "forward" | "both";
  examiner_cited: boolean;
  reason: "shared_reference" | "examiner_cited";
  likely_expired: boolean;
}

export interface CitationEdge {
  source: string; // citing patent
  target: string; // cited patent
}

export interface CitationNetwork {
  discoveries: CitationDiscovery[];
  edges: CitationEdge[];
  references_scanned: number;
}

export interface TrendPoint {
  date: string;
  value: number; // 0-100, Google Trends relative interest
}

export interface MarketTrend {
  keyword: string;
  points: TrendPoint[];
  direction: "rising" | "steady" | "declining";
  change_pct: number;
}

// The inventor-facing parts of a report, translated. Parallel to the
// English fields on AnalysisResult (same order, same lengths).
export interface LocalizedContent {
  language_code: string;
  language_name: string;
  plain_summary: string;
  differentiation_suggestions: string[];
  citation_claims: string[];
  ui_labels: Record<string, string>;
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
  top_assignees: AssigneeStat[];
  public_domain: PublicDomainSummary | null;
  // Absent on analyses cached before these features existed.
  search_strategy?: SearchStrategy | null;
  citation_network?: CitationNetwork | null;
  market_trend?: MarketTrend | null;
  report_id?: string | null;
  plain_summary?: string;
  original_idea_text?: string | null; // the inventor's own words, when not English
  language_code?: string;
  language_name?: string;
  localized?: LocalizedContent | null;
}

export interface AskTurn {
  question: string;
  answer: string;
}

export interface AnswerSource {
  key: string; // "D3", as it appears in the answer text
  id: string;
  title: string;
  link: string;
}

export interface ReportAnswer {
  answer: string; // cites sources inline as [D3]
  sources: AnswerSource[];
}

export interface ExampleReport {
  report_id: string;
  idea_text: string;
  language_name: string;
  novelty_confidence: number;
  results_count: number;
  public_domain_count: number;
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
  language?: string; // ISO 639-1; forces the report language
  parent_report_id?: string; // set for "Apply & re-check" runs
}
