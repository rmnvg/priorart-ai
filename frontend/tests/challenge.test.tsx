import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi, afterEach } from "vitest";
import { ChallengeOutcome } from "@/components/ChallengeFinding";
import { fetchChallenge } from "@/lib/analyzeStream";
import type { ChallengeResult } from "@/types/analysis";

const result: ChallengeResult = {
  feature_id: "F1", feature: "Humidity controlled vent", outcome: "found",
  queries: [{ query: "humidity vent", rationale: "Mechanism" }],
  documents: [{ id: "p1", title: "Vent patent", link: "https://patents.google.com/",
    previously_reviewed: false,
    sections: [{ label: "Abstract", source: "abstract", text: "A sensor controls the vent opening." }] }],
  evidence: [{ document_id: "p1", section: "Abstract", quote: "A sensor controls the vent opening." }],
  warnings: [], serpapi_calls: { google_patents: 2, google_patents_details: 1 },
  completed_at: "2026-10-02T10:00:00+00:00",
};

afterEach(() => vi.unstubAllGlobals());

describe("challenge evidence", () => {
  it("shows before/after, exact evidence, attribution and research scope", () => {
    const html = renderToStaticMarkup(<ChallengeOutcome result={result} />);
    expect(html).toContain("Challenge changed this finding: overlap found");
    expect(html).toContain("Before: not found in the original report");
    expect(html).toContain("A sensor controls the vent opening.");
    expect(html).toContain("Abstract");
    expect(html).toContain("original snapshot");
    expect(html).toContain("additional document");
  });

  it("distinguishes incomplete attempts from bounded negative findings", () => {
    const incomplete = renderToStaticMarkup(<ChallengeOutcome result={{ ...result, outcome: "inconclusive", evidence: [] }} />);
    expect(incomplete).toContain("Challenge incomplete");
    expect(incomplete).not.toContain("Challenge complete:");
    const negative = renderToStaticMarkup(<ChallengeOutcome result={{ ...result, outcome: "not_found", evidence: [] }} />);
    expect(negative).toContain("This does not establish novelty");
  });

  it("only runs a search on an explicit POST; loading saved results uses GET", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => result });
    vi.stubGlobal("fetch", fetch);
    await fetchChallenge("abc", "F1");
    expect(fetch.mock.calls[0][1].method).toBe("GET");
    await fetchChallenge("abc", "F1", true);
    expect(fetch.mock.calls[1][1].method).toBe("POST");
  });

  it("surfaces service errors without replacing them with a negative finding", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: "Search unavailable" }) }));
    await expect(fetchChallenge("abc", "F1", true)).rejects.toThrow("Search unavailable");
  });
});
