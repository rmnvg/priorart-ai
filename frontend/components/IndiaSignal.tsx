import type { IndiaStatus } from "@/types/analysis";

// Pointers only, never figures that go stale (fees change by notification).
// Every step links to the official source so the user verifies there.
const NEXT_STEPS: { title: string; body: string; href: string; linkLabel: string }[] = [
  {
    title: "Search the Indian Patent Office directly",
    body: "InPASS covers Indian filings that Google Patents indexes late or not at all.",
    href: "https://iprsearch.ipindia.gov.in/PublicSearch/",
    linkLabel: "InPASS public search",
  },
  {
    title: "Lock in a filing date cheaply",
    body: "A provisional specification secures your priority date. You then have 12 months to file the complete specification.",
    href: "https://ipindia.gov.in/",
    linkLabel: "IP India",
  },
  {
    title: "Check fee concessions",
    body: "Individual inventors, startups and small entities pay reduced official fees. DPIIT-recognised startups can also get facilitation support and expedited examination.",
    href: "https://www.startupindia.gov.in/",
    linkLabel: "Startup India",
  },
  {
    title: "Don't disclose it publicly yet",
    body: "Publishing, pitching publicly or selling before you file can count as prior art against your own application.",
    href: "https://ipindia.gov.in/",
    linkLabel: "IP India",
  },
];

export default function IndiaSignal({
  status,
  title = "India patentability signal",
}: {
  status: IndiaStatus;
  title?: string;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
      <div className="border-l-4 border-orange-400 p-5">
        <h2 className="font-semibold text-neutral-900">{title}</h2>
        <p className="mt-1 text-sm text-neutral-500">
          Whether the closest matches are actually in force in India, or only protected
          elsewhere, where the same idea may still be open.
        </p>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-lg bg-orange-50 p-3">
            <div className="text-2xl font-semibold text-orange-900">{status.blocking_in_india}</div>
            <div className="text-sm text-orange-800">Active &amp; blocking in India</div>
          </div>
          <div className="rounded-lg bg-neutral-50 p-3">
            <div className="text-2xl font-semibold text-neutral-900">
              {status.active_elsewhere_only}
            </div>
            <div className="text-sm text-neutral-600">Active elsewhere, not in India</div>
          </div>
          {status.india_filings_found != null && (
            <div className="rounded-lg bg-neutral-50 p-3">
              <div className="text-2xl font-semibold text-neutral-900">
                {status.india_filings_found}
              </div>
              <div className="text-sm text-neutral-600">Indian filings in the results</div>
            </div>
          )}
        </div>
        <p className="mt-3 text-xs text-neutral-400">
          Google Patents reports Indian legal status as unknown more often than not, so
          treat this as a conservative floor rather than a complete picture.
        </p>

        <div className="mt-5 border-t border-neutral-100 pt-4">
          <h3 className="text-sm font-semibold text-neutral-800">Next steps if you file in India</h3>
          <ol className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {NEXT_STEPS.map((step, i) => (
              <li key={step.title} className="flex gap-2.5 text-sm">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-orange-100 text-xs font-semibold text-orange-800">
                  {i + 1}
                </span>
                <span>
                  <span className="font-medium text-neutral-900">{step.title}.</span>{" "}
                  <span className="text-neutral-600">{step.body}</span>{" "}
                  <a
                    href={step.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="whitespace-nowrap text-blue-600 underline"
                  >
                    {step.linkLabel} ↗
                  </a>
                </span>
              </li>
            ))}
          </ol>
          <p className="mt-3 text-xs text-neutral-400">
            General information, not legal advice. A registered patent agent can confirm
            what applies to you.
          </p>
        </div>
      </div>
    </div>
  );
}
