import type { SearchStrategy } from "@/types/analysis";

const QUERY_LABELS: Record<string, string> = {
  major_markets: "Major markets",
  india_specific: "India",
  broad_recall: "Broad recall",
};

const ENGINE_LABELS: Record<string, string> = {
  google_patents: "Google Patents search",
  google_patents_details: "Patent full-text & citations",
  google: "Google web search",
  google_trends: "Google Trends",
};

function googlePatentsUrl(query: string, country?: string | null) {
  const params = new URLSearchParams({ q: query });
  if (country) params.set("country", country);
  return `https://patents.google.com/?${params.toString()}`;
}

// Makes the search auditable: the exact queries behind the verdict, and a
// one-click way to keep digging from where the tool stopped. A verdict you
// can't trace back to its searches is one you can't trust.
export default function SearchStrategyPanel({ strategy }: { strategy: SearchStrategy }) {
  const totalCalls = Object.values(strategy.serpapi_calls).reduce((a, b) => a + b, 0);

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-neutral-900">How this report was built</h2>
      <p className="mt-1 text-sm text-neutral-500">
        The exact searches behind the verdict. Open any of them in Google Patents to keep
        digging from here.
      </p>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {strategy.core_concepts.map((c) => (
          <span key={c} className="rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs text-neutral-700">
            {c}
          </span>
        ))}
        {strategy.suggested_cpc && (
          <span className="rounded-full border border-neutral-300 px-2.5 py-0.5 text-xs text-neutral-600">
            CPC {strategy.suggested_cpc}
          </span>
        )}
      </div>

      <ul className="mt-4 space-y-3">
        {strategy.queries.map((q) => (
          <li key={q.type} className="rounded-lg border border-neutral-100 bg-neutral-50 p-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-semibold text-neutral-800">{QUERY_LABELS[q.type] ?? q.type}</span>
              {q.country && (
                <span className="rounded bg-orange-100 px-1.5 py-0.5 font-medium text-orange-800">
                  {q.country} filings only
                </span>
              )}
              <span className="text-neutral-400">
                {q.failed ? "search failed" : `${q.result_count} results`}
              </span>
              <a
                href={googlePatentsUrl(q.query, q.country)}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-auto text-blue-600 underline print:hidden"
              >
                Open in Google Patents ↗
              </a>
            </div>
            <code className="mt-1.5 block break-words font-mono text-xs text-neutral-800">{q.query}</code>
            {q.rationale && <p className="mt-1 text-xs text-neutral-500">{q.rationale}</p>}
          </li>
        ))}
      </ul>

      <div className="mt-4 border-t border-neutral-100 pt-3">
        <p className="text-xs font-medium text-neutral-600">
          {totalCalls} SerpApi calls behind this report
        </p>
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
          {Object.entries(strategy.serpapi_calls).map(([engine, count]) => (
            <span key={engine} className="text-xs text-neutral-500">
              <code className="font-mono text-neutral-700">{engine}</code> ×{count}
              <span className="text-neutral-400"> · {ENGINE_LABELS[engine] ?? engine}</span>
            </span>
          ))}
        </div>
        <p className="mt-1.5 text-xs text-neutral-400">
          Market check searched: &ldquo;{strategy.market_query}&rdquo;
        </p>
      </div>
    </div>
  );
}
