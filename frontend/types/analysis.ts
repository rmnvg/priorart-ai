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
  replayed?: boolean; // a saved run being replayed, not a live analysis
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
  evidence_source?: EvidenceSource | null; // what the verdict was judged from
  found_via?: FoundVia; // "citation" for documents the citation follow-up fetched
}

// Feature-level evidence: backend/app/pipeline/evidence.py
export type EvidenceSource = "claims" | "abstract" | "snippet";
export type FoundVia = "search" | "citation";

export interface FeatureEvidence {
  result_id: string;
  title: string;
  link: string;
  quote: string; // verified to occur in the document text
  evidence_source: EvidenceSource;
  found_via: FoundVia;
}

export interface FeatureFinding {
  id: string; // "F1"
  feature: string;
  evidence: FeatureEvidence[]; // empty = not found in the evidence reviewed
}

export interface ChallengeResult {
  feature_id: string;
  feature: string;
  outcome: "found" | "not_found" | "inconclusive";
  queries: { query: string; rationale: string }[];
  documents: {
    id: string;
    title: string;
    link: string;
    previously_reviewed: boolean;
    sections: { label: string; source: EvidenceSource; text: string }[];
  }[];
  evidence: { document_id: string; section: string; quote: string }[];
  warnings: string[];
  serpapi_calls: Record<string, number>;
  completed_at: string;
}

// Citation follow-up: backend/app/pipeline/citation_followup.py
export interface CitationFollowUp {
  id: string;
  title: string;
  link: string;
  referenced_by: string[];
  reason: string;
  evidence_source: EvidenceSource;
  verdict: NoveltyVerdict;
  features_found: string[]; // feature ids
  newly_found: string[]; // feature ids no searched document showed
  explanation: string;
  changed_conclusion: boolean;
}

export interface ExaminedDocument {
  id: string;
  source_type: string;
  title: string;
  link: string;
  text: string;
  evidence_source?: EvidenceSource | null;
  found_via?: FoundVia;
}

export interface IndiaStatus {
  // A legal-status count, not an overlap finding: related patents among the
  // closest matches that Google Patents reports as active in India.
  related_active_in_india: number;
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
  recheck?: RecheckComparison | null; // only on "Apply & re-check" runs
  examined_documents?: ExaminedDocument[];
  feature_findings?: FeatureFinding[]; // the headline; absent on older reports
  citation_followups?: CitationFollowUp[];
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

// Evidence-backed re-check: backend/app/pipeline/recheck.py
export interface RecheckComparison {
  parent_report_id: string;
  applied_change: string;
  confidence_before: number;
  original_matches: {
    id: string;
    title: string;
    link: string;
    verdict_before: NoveltyVerdict;
    change_found_in_document: boolean;
    change_quote?: string | null; // verified evidence when the change is already there
    still_shared: { feature: string; quote: string }[];
    explanation: string;
  }[];
  new_matches: { id: string; title: string; link: string; verdict: NoveltyVerdict; source_type: string }[];
  evidence_basis: "full_text" | "snippets";
}

// Examination preview: backend/app/pipeline/examination.py
export type ExaminationOutcome =
  | "novelty_objection" // one document discloses every element — s. 2(1)(j)
  | "inventive_step_objection" // two documents together do — s. 2(1)(ja)
  | "combination_risk" // only three or more documents together do
  | "no_objection_found"; // some element is disclosed nowhere

export interface ExaminationPreview {
  outcome: ExaminationOutcome;
  elements: { id: string; text: string }[];
  documents: { key: string; id: string; title: string; link: string; source_type: string }[];
  coverage: { element: string; document: string; status: "disclosed" | "partial"; quote: string }[];
  novelty_objections: string[]; // document keys
  inventive_step_objections: { documents: string[]; same_field: boolean }[];
  uncovered_elements: string[]; // element ids — the novelty core
  section3_flags: {
    clause: string;
    title: string;
    law_summary: string;
    risk: "high" | "possible";
    reason: string;
    how_to_address: string;
  }[];
  evidence_basis: "full_text" | "snippets";
  unverified_quotes_dropped: number;
}

// Sketch input: backend/app/pipeline/sketch.py
export interface SketchComponent {
  id: string; // "C1"
  name: string;
  description: string;
}

export interface SketchRelationship {
  source: string; // component id
  target: string; // component id
  relation: string; // "sits inside"
}

export interface SketchReading {
  purpose: string;
  components: SketchComponent[];
  relationships: SketchRelationship[];
  uncertain: string[]; // questions the model couldn't answer from the image
}

// Constrained redesign: backend/app/pipeline/redesign.py
export interface Feature {
  id: string; // "E1"
  text: string;
}

export interface RedesignBrief {
  locked_features: string[]; // feature ids the design must keep
  constraints: string[];
  cost_target_inr?: number | null;
}

export interface DesignAlternative {
  title: string;
  how_it_works: string;
  what_changes: string;
  keeps: string[];
  drops_locked: string[]; // locked feature ids it doesn't say it keeps
  constraint_notes: { constraint: string; approach: string }[];
  avoids: { document_id: string; title: string; link: string; mechanism: string; quote: string }[];
  revised_idea: string; // English, for the re-check run
  change_summary: string; // English, the re-check's applied change
}

export interface RedesignResult {
  features: Feature[];
  locked_features: string[];
  constraints: string[];
  alternatives: DesignAlternative[];
  matches_considered: { id: string; title: string; link: string }[];
  evidence_basis: "full_text" | "snippets";
  unverified_quotes_dropped: number;
  language_name: string;
}

export interface ExampleReport {
  report_id: string;
  idea_text: string;
  language_name: string;
  novelty_confidence: number;
  features_found?: number; // 0/0 on reports saved before feature evidence
  features_total?: number;
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
  applied_change?: string; // the suggestion applied, in English
}
