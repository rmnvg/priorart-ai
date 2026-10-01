import { EVIDENCE_SOURCE_LABELS } from "@/lib/evidence";
import type { CitationFollowUp, CitationNetwork, FeatureFinding, RankedResult } from "@/types/analysis";

const FOLLOWUP_VERDICTS = {
  blocking: "Discloses the idea as a whole",
  partially_overlapping: "Shares some features",
  not_relevant: "No feature of your idea found",
} as const;

const DIRECTION_COPY = {
  backward: "cited by",
  forward: "cites",
  both: "cited by / cites",
} as const;

function shortTitle(title: string, max = 60) {
  return title.length > max ? `${title.slice(0, max).trimEnd()}…` : title;
}

// Keyword search only finds documents that share vocabulary with the query.
// These were found the way professional searchers close that gap — by
// following the citations of the closest matches — so they're shown as their
// own section rather than mixed into the keyword results.
export default function CitationDiscoveries({
  network,
  rankedResults,
  followups = [],
  findings = [],
}: {
  network: CitationNetwork;
  rankedResults: RankedResult[];
  followups?: CitationFollowUp[]; // discoveries that were fetched and assessed
  findings?: FeatureFinding[];
}) {
  if (network.discoveries.length === 0) return null;

  const titleById = new Map(rankedResults.map((r) => [r.id, r.title]));
  const isFallback = network.discoveries.every((d) => d.reason === "examiner_cited");
  const followupById = new Map(followups.map((f) => [f.id, f]));
  const featureText = new Map(findings.map((f) => [f.id, f.feature]));

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h2 className="text-lg font-semibold text-neutral-900">Found by citation chasing</h2>
        <span className="text-sm text-neutral-500">
          {network.discoveries.length} found in {network.references_scanned} citations scanned
        </span>
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        {isFallback
          ? "Documents the patent examiner cited against your closest match. Examiners pick these as the most relevant prior art, whatever words they use, so keyword search often misses them."
          : "Documents that several of your closest matches cite, or are cited by, but that keyword search never returned. When several closest matches point to the same document, it is almost always relevant, whatever words it uses."}
      </p>

      <ul className="mt-4 space-y-2">
        {network.discoveries.map((d) => (
          <li key={d.id} className="rounded-lg border border-neutral-100 bg-neutral-50 p-3">
            <div className="flex flex-wrap items-center gap-2">
              {d.reason === "shared_reference" && (
                <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
                  Linked to {d.referenced_by.length} closest matches
                </span>
              )}
              {d.examiner_cited && (
                <span className="rounded bg-neutral-200 px-2 py-0.5 text-xs font-medium text-neutral-700">
                  Examiner-cited
                </span>
              )}
              {d.likely_expired && (
                <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
                  20+ years old
                </span>
              )}
              {d.priority_date && (
                <span className="ml-auto text-xs text-neutral-400">priority {d.priority_date}</span>
              )}
            </div>
            <a
              href={d.link}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1.5 block font-medium text-neutral-900 underline decoration-neutral-300 underline-offset-2 hover:decoration-neutral-900"
            >
              {d.title}
            </a>
            {d.assignee && <p className="text-xs text-neutral-500">{d.assignee}</p>}
            <p className="mt-1 text-xs text-neutral-500">
              {DIRECTION_COPY[d.direction]}:{" "}
              {d.referenced_by.map((id) => shortTitle(titleById.get(id) ?? id)).join(" · ")}
            </p>
            {followupById.has(d.id) && (
              <FollowUpResult followup={followupById.get(d.id)!} featureText={featureText} />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function FollowUpResult({
  followup,
  featureText,
}: {
  followup: CitationFollowUp;
  featureText: Map<string, string>;
}) {
  const names = (ids: string[]) => ids.map((id) => featureText.get(id) ?? id).join("; ");
  return (
    <div className="mt-2 rounded-md border border-neutral-200 bg-white p-2.5 text-xs text-neutral-700">
      <p>
        <span className="font-semibold text-neutral-900">Followed up:</span> fetched and read{" "}
        {EVIDENCE_SOURCE_LABELS[followup.evidence_source].replace("from ", "")}.{" "}
        {FOLLOWUP_VERDICTS[followup.verdict]}
        {followup.features_found.length > 0 && ` — ${names(followup.features_found)}`}.
      </p>
      {followup.changed_conclusion && (
        <p className="mt-1 font-medium text-blue-800">
          Changed the conclusion: {names(followup.newly_found)} was not shown by any searched
          document.
        </p>
      )}
      {followup.explanation && <p className="mt-1 text-neutral-500">{followup.explanation}</p>}
    </div>
  );
}
