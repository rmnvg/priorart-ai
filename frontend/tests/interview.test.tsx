import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import InventorInterview from "@/components/InventorInterview";
import { fetchInterview } from "@/lib/analyzeStream";
import { interviewDescription } from "@/lib/interview";

afterEach(() => vi.unstubAllGlobals());

describe("inventor clarification", () => {
  const plan = { questions: [
    { question: "What moves the air?", reason: "Find the mechanism" },
    { question: "What must stay?", reason: "Understand constraints" },
  ] };

  it("keeps the original idea and only answered questions, without supplying defaults", () => {
    expect(interviewDescription("  बिना बिजली का ड्रायर  ", plan, ["चिमनी", "  "]))
      .toBe("बिना बिजली का ड्रायर\n\nQuestion (context only): What moves the air?\nInventor's answer: चिमनी");
    expect(interviewDescription("A passive crop dryer", plan, []))
      .toBe("A passive crop dryer");
  });

  it("requests clarification without calling the analysis endpoint", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => plan });
    vi.stubGlobal("fetch", fetch);
    const signal = new AbortController().signal;
    expect(await fetchInterview("A passive crop dryer", signal)).toEqual(plan);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toMatch(/\/interview$/);
    expect(fetch.mock.calls[0][1]).toMatchObject({ method: "POST", signal, body: JSON.stringify({ idea_text: "A passive crop dryer" }) });
  });

  it("surfaces interview failures so the inventor can skip or retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: "Interview unavailable" }) }));
    await expect(fetchInterview("A passive crop dryer")).rejects.toThrow("Interview unavailable");
    const html = renderToStaticMarkup(<InventorInterview idea="A passive crop dryer" onSearch={() => {}} onBack={() => {}} />);
    expect(html).toContain("Skip questions &amp; search original idea");
    expect(html).toContain("before searching");
  });
});
