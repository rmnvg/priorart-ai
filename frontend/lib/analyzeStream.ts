import type {
  AnalysisResult,
  AnalyzeRequest,
  AnalyzeStreamEvent,
  AskTurn,
  ExaminationPreview,
  ExampleReport,
  ReportAnswer,
} from "@/types/analysis";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// The backend streams SSE over a POST response, so the native EventSource
// (GET-only) doesn't apply — we parse the "event: X\r\ndata: Y\r\n\r\n" framing
// manually from the fetch response body stream. sse_starlette emits CRLF line
// endings (per the SSE spec), not bare "\n" — normalize before splitting.
export async function streamAnalysis(
  request: AnalyzeRequest,
  onEvent: (event: AnalyzeStreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
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

/** Saved analyses for the examples gallery. Empty on any failure — the
 * gallery is an extra, and the idea form must render regardless. */
export async function fetchExamples(): Promise<ExampleReport[]> {
  try {
    const response = await fetch(`${API_URL}/examples`);
    return response.ok ? ((await response.json()) as ExampleReport[]) : [];
  } catch {
    return [];
  }
}

/** Whether the backend can run new analyses (it has API keys), or is
 * serving saved reports only. null when the backend can't be reached. */
export async function fetchLiveMode(): Promise<boolean | null> {
  try {
    const response = await fetch(`${API_URL}/health`);
    if (!response.ok) return null;
    return Boolean(((await response.json()) as { live?: boolean }).live);
  } catch {
    return null;
  }
}

/** A follow-up question about a saved report, answered from that report
 * alone. Throws with the server's explanation (no LLM key, unknown report,
 * model failure) so the UI can show it as-is. */
export async function askReport(
  reportId: string,
  question: string,
  history: AskTurn[]
): Promise<ReportAnswer> {
  const response = await fetch(`${API_URL}/report/${encodeURIComponent(reportId)}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  if (!response.ok) throw new Error(await errorDetail(response, "Couldn't get an answer — is the backend running?"));
  return (await response.json()) as ReportAnswer;
}

/** How an Indian patent examiner might read a saved report. Computed once
 * server-side, then cached — later calls return instantly. */
export async function fetchExamination(reportId: string): Promise<ExaminationPreview> {
  const response = await fetch(`${API_URL}/report/${encodeURIComponent(reportId)}/examination`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response, "Couldn't prepare the preview — is the backend running?"));
  }
  return (await response.json()) as ExaminationPreview;
}

// FastAPI errors carry a human-readable `detail`; show it as-is.
async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}
