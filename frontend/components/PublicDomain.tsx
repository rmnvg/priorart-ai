import type { PublicDomainSummary } from "@/types/analysis";

// Deliberately framed as an opportunity, not a warning. Everywhere else in
// this report prior art is an obstacle; here it's the opposite — protection
// has ended, so the technology is published, public, and free to build on.
export default function PublicDomain({
  summary,
  title = "Free to build on",
}: {
  summary: PublicDomainSummary;
  title?: string;
}) {
  if (summary.count === 0) return null;

  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h2 className="text-lg font-semibold text-emerald-900">{title}</h2>
        <span className="text-sm text-emerald-800/80">
          {summary.count} of {summary.patents_considered} patents found are no longer in force
        </span>
      </div>
      <p className="mt-1 text-sm text-emerald-800/80">
        These aren&apos;t blockers — their protection has ended, so the technology is public
        domain. You can legally use, build on, or manufacture what they describe.
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
                no longer active in {e.lapsed_in.join(", ")}
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
