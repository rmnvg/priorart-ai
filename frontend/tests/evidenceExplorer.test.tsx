import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import EvidenceExplorer, { QuotedSection } from "@/components/EvidenceExplorer";
import type { FeatureEvidence } from "@/types/analysis";

const evidence: FeatureEvidence = {
  result_id: "p1", title: "Dryer", link: "https://example.com", found_via: "search",
  evidence_source: "abstract", quote: "A humidity sensor controls the vent…",
  section: { label: "Abstract", source: "abstract", text: "A humidity\n sensor controls the vent opening.", original_chars: 100, truncated: true },
};

describe("source inspection", () => {
  it("highlights the passage with normalized whitespace and marks truncated scope", () => {
    const html = renderToStaticMarkup(<QuotedSection evidence={evidence} />);
    expect(html).toContain("Inspect passage in Abstract");
    expect(html).toContain("<mark");
    expect(html).toContain("remaining text was not reviewed");
    expect(html).toContain("AI assessment");
  });

  it("does not invent source coverage for older reports", () => {
    const html = renderToStaticMarkup(<QuotedSection evidence={{ ...evidence, section: undefined }} />);
    expect(html).toContain("no section-level source record");
    expect(html).not.toContain("Inspect passage in");
  });

  it("shows unreviewed claim counts and exposes all reviewed sections", () => {
    const html = renderToStaticMarkup(<EvidenceExplorer documents={[{
      id: "p1", title: "Dryer", link: "https://example.com", text: "", source_type: "patent",
      total_claims: 12, sections: [evidence.section!, { label: "Claim 1", source: "claims", text: "A drying chamber.", original_chars: 17, truncated: false }],
    }]} />);
    expect(html).toContain("1 of 12 retrieved claims reviewed");
    expect(html).toContain("full specification not reviewed");
    expect(html).toContain("Claim 1");
  });
});
