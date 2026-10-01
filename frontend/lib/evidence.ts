import type {
  AnalysisResult,
  CitationFollowUp,
  EvidenceSource,
  FeatureFinding,
} from "@/types/analysis";

export const EVIDENCE_SOURCE_LABELS: Record<EvidenceSource, string> = {
  claims: "from the claims",
  abstract: "from the abstract",
  snippet: "from a search snippet only",
};

export interface EvidenceSummary {
  found: FeatureFinding[];
  missing: FeatureFinding[];
  documentsReviewed: number;
  // Citation follow-ups that moved a feature from "not found" to "found".
  changedBy: CitationFollowUp[];
}

/** The report's conclusion as verified evidence, or null for reports saved
 * before feature findings existed (the UI then falls back to the model's
 * overall verdict). */
export function summarizeEvidence(result: AnalysisResult): EvidenceSummary | null {
  const findings = result.feature_findings ?? [];
  if (findings.length === 0) return null;
  return {
    found: findings.filter((f) => f.evidence.length > 0),
    missing: findings.filter((f) => f.evidence.length === 0),
    documentsReviewed: result.examined_documents?.length ?? result.candidate_assessments.length,
    changedBy: (result.citation_followups ?? []).filter((f) => f.changed_conclusion),
  };
}

/** One sentence, phrased so "not found" is never read as "doesn't exist". */
export function evidenceHeadline(summary: EvidenceSummary): string {
  const total = summary.found.length + summary.missing.length;
  const docs = `${summary.documentsReviewed} document${summary.documentsReviewed === 1 ? "" : "s"} reviewed`;
  if (summary.found.length === 0) {
    return `None of the ${total} features of your idea was found in the ${docs}.`;
  }
  const overlap = `We found overlap in ${summary.found.length} of ${total} features of your idea.`;
  if (summary.missing.length === 0) return `${overlap} Every feature appears in the ${docs}.`;
  const missing = summary.missing.length === 1 ? "One feature wasn't" : `${summary.missing.length} features weren't`;
  return `${overlap} ${missing} found in the ${docs}.`;
}

// Embedding (cosine) similarity between a result's text and the idea. It
// orders results well but is not a probability of overlap, so it is shown
// as a band, never as a percentage.
export type SimilarityBand = "High" | "Medium" | "Low";

export function similarityBand(score: number): SimilarityBand {
  if (score >= 0.55) return "High";
  if (score >= 0.4) return "Medium";
  return "Low";
}

export const SIMILARITY_HINT =
  "How closely this document's wording matches your description (text similarity). " +
  "It orders the results; it is not a probability that the document overlaps your idea.";
