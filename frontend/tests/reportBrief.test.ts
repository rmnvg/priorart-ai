import { describe, expect, it } from "vitest";
import { buildReportBrief } from "@/lib/reportBrief";
import { analysis } from "./fixtures";

describe("buildReportBrief", () => {
  it("leads with the invention and verdict, and links the interactive report", () => {
    const brief = buildReportBrief(
      analysis({ overall_novelty_confidence: 0.42 }),
      "http://localhost:3000/?report=abc"
    );
    expect(brief).toContain("## Invention\n\nA folding paddle");
    expect(brief).toContain("**Novelty confidence:** 42%");
    expect(brief).toContain("Interactive report: http://localhost:3000/?report=abc");
  });

  it("escapes pipes so a patent title can't break the Markdown table", () => {
    const brief = buildReportBrief(
      analysis({
        candidate_assessments: [
          {
            result_id: "a",
            title: "Paddle | oar",
            link: "https://x",
            overlapping_elements: ["shaft"],
            differences: [],
            verdict: "blocking",
          },
        ],
      })
    );
    expect(brief).toContain("[Paddle \\| oar](https://x) | Blocking | shaft | — |");
  });

  it("keeps the inventor's own words alongside the English translation", () => {
    const brief = buildReportBrief(
      analysis({ original_idea_text: "मोड़ने वाला चप्पू", language_name: "Hindi" })
    );
    expect(brief).toContain("Translated from the inventor's original (Hindi)");
    expect(brief).toContain("> मोड़ने वाला चप्पू");
  });

  it("lists the searches already run, labeling refined and India-only queries", () => {
    const brief = buildReportBrief(
      analysis({
        search_strategy: {
          core_concepts: ["paddle"],
          queries: [
            { type: "india_specific", query: "(paddle)", rationale: "", country: "IN", result_count: 4, failed: false },
            { type: "refined", query: '("sectional shaft")', rationale: "", result_count: 0, failed: true },
          ],
          market_query: "paddle",
          serpapi_calls: { google_patents: 2 },
        },
      })
    );
    expect(brief).toContain("| India (IN filings only) | `(paddle)` | 4 |");
    expect(brief).toContain("| Refined (agent, patent terminology) | `(\"sectional shaft\")` | search failed |");
  });
});
