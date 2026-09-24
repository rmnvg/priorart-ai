import { describe, expect, it } from "vitest";
import { buildDecision } from "@/lib/decision";
import type { CandidateNoveltyAssessment } from "@/types/analysis";
import { analysis, patent } from "./fixtures";

function assessment(result_id: string, verdict: CandidateNoveltyAssessment["verdict"]): CandidateNoveltyAssessment {
  return {
    result_id,
    title: `Title ${result_id}`,
    link: "https://x",
    overlapping_elements: ["o1"],
    differences: ["d1", "d2", "d3"],
    verdict,
  };
}

describe("buildDecision", () => {
  it("picks the most severe match, breaking ties by relevance", () => {
    const d = buildDecision(
      analysis({
        ranked_results: [
          patent({ id: "a", relevance_score: 0.9 }),
          patent({ id: "b", relevance_score: 0.4 }),
          patent({ id: "c", relevance_score: 0.7 }),
        ],
        candidate_assessments: [
          assessment("a", "partially_overlapping"),
          assessment("b", "blocking"),
          assessment("c", "blocking"),
        ],
        differentiation_suggestions: ["add a hinge"],
      })
    );
    expect(d.closest?.result_id).toBe("c");
    expect(d.differences).toEqual(["d1", "d2"]);
    expect(d.nextSuggestionIndex).toBe(0);
  });

  it("never presents an irrelevant document as the closest match", () => {
    const d = buildDecision(analysis({ candidate_assessments: [assessment("a", "not_relevant")] }));
    expect(d.closest).toBeNull();
    expect(d.differences).toEqual([]);
    expect(d.nextSuggestionIndex).toBeNull();
  });
});
