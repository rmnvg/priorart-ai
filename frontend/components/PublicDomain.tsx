import type { PublicDomainSummary, RankedResult } from "@/types/analysis";

// Framed as an opportunity, not a warning — everywhere else in this report
// prior art is an obstacle, here it's the opposite. But only as strong as
// the evidence: each entry says exactly where it's reported lapsed, and
// where its status isn't reported at all, rather than promising it's free.
export default function PublicDomain({
  summary,
  rankedResults,
  title = "Likely free to build on",
}: {
  summary: PublicDomainSummary;
  rankedResults: RankedResult[];
  title?: string;
}) {
  if (summary.count === 0) return null;

  const statusById = new Map(rankedResults.map((r) => [r.id, r.country_status ?? {}]));
  const unreportedIn = (id: string) =>
    Object.entries(statusById.get(id) ?? {})
      .filter(([, status]) => status !== "ACTIVE" && status !== "NOT_ACTIVE")
      .map(([country]) => country)
      .sort();

  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h2 className="text-lg font-semibold text-emerald-900">{title}</h2>
        <span className="text-sm text-emerald-800/80">
          {summary.count} of {summary.patents_considered} patents found are reported as no
          longer in force
        </span>
      </div>
      <p className="mt-1 text-sm text-emerald-800/80">
        Google Patents reports these as lapsed or expired in every country where it has their
        legal status, and active nowhere. A patent that has ended is usually free to use in
        that country — check the countries listed for each one, especially any whose status
        isn&apos;t reported.
      </p>

      <ul className="mt-4 space-y-2">
        {summary.entries.map((e) => (
          <li key={e.id} className="rounded-lg bg-white/70 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ${
                  e.reason === "term_expired"
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-amber-100 text-amber-800"
                }`}
              >
                {e.reason === "term_expired" ? "20-year term expired" : "Lapsed early"}
              </span>
              {e.years_since_filing != null && (
                <span className="text-xs text-neutral-500">
                  filed {e.years_since_filing} years ago
                </span>
              )}
              <span className="basis-full text-xs text-neutral-400 sm:ml-auto sm:basis-auto">
                reported lapsed in {e.lapsed_in.join(", ")}
                {unreportedIn(e.id).length > 0 && (
                  <span className="text-amber-700"> · status not reported in {unreportedIn(e.id).join(", ")}</span>
                )}
              </span>
            </div>
            <a
              href={e.link}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1.5 block font-medium text-neutral-900 underline decoration-neutral-300 underline-offset-2 hover:decoration-neutral-900"
            >
              {e.title}
            </a>
            {e.assignee && <p className="text-xs text-neutral-500">{e.assignee}</p>}
          </li>
        ))}
      </ul>

      <p className="mt-3 text-xs text-emerald-800/70">
        Based on the legal status Google Patents reports, which can be incomplete or out of
        date — and &ldquo;lapsed early&rdquo; patents can sometimes be revived. Verify status with a
        patent attorney before relying on this commercially.
      </p>
    </div>
  );
}
