import { describe, expect, it } from "vitest";
import { buildReportBrief } from "@/lib/reportBrief";
import { evidenceHeadline, similarityBand, summarizeEvidence } from "@/lib/evidence";
import type { FeatureFinding } from "@/types/analysis";
import { analysis } from "./fixtures";

const quoted = (id: string, feature: string, via: "search" | "citation" = "search"): FeatureFinding => ({
  id,
  feature,
  evidence: [
    {
      result_id: `patent/US${id}/en`,
      title: `Doc ${id}`,
      link: "https://patents.google.com/x",
      quote: "a drying chamber heated by a solar collector",
      evidence_source: "claims",
      found_via: via,
    },
  ],
});

const docs = (n: number) =>
  Array.from({ length: n }, (_, i) => ({
    id: `d${i}`,
    source_type: "patent",
    title: "t",
    link: "l",
    text: "x",
  }));

describe("summarizeEvidence", () => {
  it("is null for reports saved before feature findings", () => {
    expect(summarizeEvidence(analysis())).toBeNull();
  });

  it("splits found and missing features and counts the documents reviewed", () => {
    const summary = summarizeEvidence(
      analysis({
        feature_findings: [quoted("F1", "solar chamber"), { id: "F2", feature: "clay body", evidence: [] }],
        examined_documents: docs(8),
      })
    )!;
    expect(summary.found.map((f) => f.id)).toEqual(["F1"]);
    expect(summary.missing.map((f) => f.id)).toEqual(["F2"]);
    expect(evidenceHeadline(summary)).toBe(
      "We found overlap in 1 of 2 features of your idea. One feature wasn't found in the 8 documents reviewed."
    );
  });

  it("names the citation follow-ups that changed the conclusion", () => {
    const followup = {
      id: "patent/US9/en",
      title: "Cited doc",
      link: "l",
      referenced_by: ["a", "b"],
      reason: "shared_reference",
      evidence_source: "claims" as const,
      verdict: "partially_overlapping" as const,
      features_found: ["F2"],
      newly_found: ["F2"],
      explanation: "",
      changed_conclusion: true,
    };
    const summary = summarizeEvidence(
      analysis({
        feature_findings: [quoted("F1", "a"), quoted("F2", "b", "citation")],
        citation_followups: [followup, { ...followup, id: "other", newly_found: [], changed_conclusion: false }],
      })
    )!;
    expect(summary.changedBy.map((f) => f.id)).toEqual(["patent/US9/en"]);
  });

  it("never claims novelty when nothing was found", () => {
    const summary = summarizeEvidence(
      analysis({
        feature_findings: [
          { id: "F1", feature: "a", evidence: [] },
          { id: "F2", feature: "b", evidence: [] },
        ],
        examined_documents: docs(1),
      })
    )!;
    expect(evidenceHeadline(summary)).toBe(
      "None of the 2 features of your idea was found in the 1 document reviewed."
    );
  });
});

describe("similarityBand", () => {
  it("bands similarity instead of showing it as a percentage", () => {
    expect(similarityBand(0.66)).toBe("High");
    expect(similarityBand(0.45)).toBe("Medium");
    expect(similarityBand(0.2)).toBe("Low");
  });
});

describe("report brief", () => {
  it("leads with the feature evidence and drops the model percentage", () => {
    const brief = buildReportBrief(
      analysis({
        overall_novelty_confidence: 0.42,
        feature_findings: [quoted("F1", "solar chamber"), { id: "F2", feature: "clay body", evidence: [] }],
      })
    );
    expect(brief).toContain("## What was found");
    expect(brief).toContain("| clay body | Not found in the documents reviewed | — |");
    expect(brief).not.toContain("42%");
    expect(brief).toContain("Related patents reported active in India");
  });
});
