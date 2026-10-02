import { useEffect, useRef, useState } from "react";
import { fetchChallenge } from "@/lib/analyzeStream";
import type { ChallengeResult } from "@/types/analysis";

export default function ChallengeFinding({ reportId, featureId }: {
  reportId: string; featureId: string;
}) {
  const [result, setResult] = useState<ChallengeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    fetchChallenge(reportId, featureId, false, controller.signal)
      .then(setResult)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Couldn't load a saved challenge.");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { request.current?.abort(); };
  }, [reportId, featureId]);

  async function challenge() {
    if (busy) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError(null);
    try {
      setResult(await fetchChallenge(reportId, featureId, true, controller.signal));
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Couldn't complete the challenge.");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <div className="mt-4 border-t border-neutral-100 pt-3">
      {result && <ChallengeOutcome result={result} />}
      {(!result || result.outcome === "inconclusive") && (
        <div className="print:hidden">
          <button type="button" disabled={busy || loading} onClick={challenge}
            className="rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-900 hover:bg-blue-100 disabled:opacity-50">
            {loading ? "Loading saved challenge…" : busy ? "Searching and verifying passages…" : result ? "Retry challenge" : "Challenge this finding"}
          </button>
          <p className="mt-2 text-xs text-neutral-500">
            Search specifically for this feature using alternative terminology, then check up to three patents.
          </p>
        </div>
      )}
      {busy && <p role="status" className="mt-2 text-sm text-blue-800">Checking additional evidence. Your original finding stays visible above.</p>}
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
    </div>
  );
}

export function ChallengeOutcome({ result }: { result: ChallengeResult }) {
  const found = result.outcome === "found";
  const title = found ? "Challenge changed this finding: overlap found"
    : result.outcome === "inconclusive" ? "Challenge incomplete — no conclusion"
    : "Challenge complete: no supporting passage found";
  return (
    <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50/50 p-3" role="status">
      <h3 className="font-semibold text-blue-950">{title}</h3>
      <p className="mt-1 text-sm text-neutral-700">
        Before: not found in the original report. After: {found
          ? "the targeted review found the supporting evidence below."
          : result.outcome === "inconclusive" ? "the targeted review could not reach a reliable finding."
          : `no verified supporting passage in ${result.documents.length} patent(s) reviewed by this challenge. This does not establish novelty.`}
      </p>
      <p className="mt-1 text-xs text-neutral-500">
        This follow-up supplements the original report; its score, exports and other assessments remain the original snapshot.
      </p>
      {result.evidence.map((e, i) => {
        const doc = result.documents.find((d) => d.id === e.document_id);
        if (!doc) return null;
        const section = doc.sections.find((s) => s.label === e.section);
        return <div key={`${e.document_id}-${i}`} className="mt-3">
          <blockquote className="border-l-2 border-blue-400 pl-3 text-sm italic">“{e.quote}”</blockquote>
          <a href={doc.link} target="_blank" rel="noopener noreferrer" className="mt-1 block text-sm underline">{doc.title} · {e.section}</a>
          {section && <details className="mt-1 text-xs text-neutral-600">
            <summary className="cursor-pointer">Read the reviewed source section</summary>
            <p className="mt-2 whitespace-pre-wrap">{section.text}</p>
          </details>}
        </div>;
      })}
      {result.warnings.map((warning, i) => <p key={i} className="mt-2 text-sm text-amber-800">{warning}</p>)}
      <details className="mt-3 text-xs text-neutral-600">
        <summary className="cursor-pointer font-medium">Inspect challenge searches and documents</summary>
        <ul className="mt-2 space-y-2">
          {result.queries.map((q) => <li key={q.query}>
            <a href={`https://patents.google.com/?q=${encodeURIComponent(q.query)}`} target="_blank" rel="noopener noreferrer" className="underline">{q.query}</a>
            <p>{q.rationale}</p>
          </li>)}
        </ul>
        <ul className="mt-3 space-y-1">
          {result.documents.map((doc) => <li key={doc.id}>
            <a href={doc.link} target="_blank" rel="noopener noreferrer" className="underline">{doc.title}</a>
            {doc.previously_reviewed ? " — previously reviewed; checked again for this feature" : " — additional document"}
          </li>)}
        </ul>
        <p className="mt-2">Scope: available abstract and excerpts of up to the first 12 claims per patent. Papers and full specifications are not checked.</p>
        <p className="mt-1">SerpApi calls for this saved run: {Object.entries(result.serpapi_calls).map(([engine, count]) => `${engine}: ${count}`).join(" · ")}</p>
        <p className="mt-1">Completed: {result.completed_at}</p>
      </details>
    </div>
  );
}
