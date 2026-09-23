import type { AnalysisResult, AnalyzeStreamEvent } from "@/types/analysis";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// The backend streams SSE over a POST response, so the native EventSource
// (GET-only) doesn't apply — we parse the "event: X\r\ndata: Y\r\n\r\n" framing
// manually from the fetch response body stream. sse_starlette emits CRLF line
// endings (per the SSE spec), not bare "\n" — normalize before splitting.
export async function streamAnalysis(
  ideaText: string,
  onEvent: (event: AnalyzeStreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idea_text: ideaText }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const dataLine = chunk.split("\n").find((line) => line.startsWith("data:"));
      if (!dataLine) continue; // skip comment/ping lines like ": ping ..."
      const jsonStr = dataLine.slice("data:".length).trim();
      if (!jsonStr) continue;
      try {
        onEvent(JSON.parse(jsonStr) as AnalyzeStreamEvent);
      } catch {
        // ignore malformed frame, keep streaming
      }
    }
  }
}

/** A previously completed analysis, by the id carried in a shared report
 * link. Returns null when the report doesn't exist (or no longer does). */
export async function fetchReport(reportId: string): Promise<AnalysisResult | null> {
  const response = await fetch(`${API_URL}/report/${encodeURIComponent(reportId)}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
  return (await response.json()) as AnalysisResult;
}
