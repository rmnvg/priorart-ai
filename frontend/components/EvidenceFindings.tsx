import { useState } from "react";
import ChallengeFinding from "@/components/ChallengeFinding";
import EvidenceExplorer, { QuotedSection } from "@/components/EvidenceExplorer";
import { EVIDENCE_SOURCE_LABELS, evidenceHeadline, type EvidenceSummary } from "@/lib/evidence";
import type { ExaminedDocument, FeatureFinding } from "@/types/analysis";

// The report's headline: which features of the idea already appear in the
// reviewed documents (each with the exact passage, verified against the
// document's text) and which weren't found. Replaces a single model-made
// percentage with something the reader can check line by line.
export default function EvidenceFindings({ summary, reportId, documents = [] }: { summary: EvidenceSummary; reportId?: string | null; documents?: ExaminedDocument[] }) {
  const findings = [...summary.found, ...summary.missing].sort(
    (a, b) => Number(a.id.slice(1)) - Number(b.id.slice(1))
  );
  const featureText = new Map(findings.map((f) => [f.id, f.feature]));

  return (
    <section className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm sm:p-6">
      <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
        What we found
      </p>
      <h2 className="mt-2 text-xl font-semibold leading-snug text-neutral-900">
        {evidenceHeadline(summary)}
      </h2>
      <p className="mt-2 text-sm text-neutral-500">
        Every passage below is quoted from the document and checked word for word against
        its text. &ldquo;Not found&rdquo; means not in the {summary.documentsReviewed}{" "}
        documents this search reviewed — not that it doesn&apos;t exist anywhere.
      </p>

      {summary.changedBy.map((f) => (
        <div
          key={f.id}
          className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-950"
        >
          <span className="font-semibold">Citation follow-up changed this conclusion.</span>{" "}
          <a href={f.link} target="_blank" rel="noopener noreferrer" className="underline">
            {f.title}
          </a>{" "}
          is cited by {f.referenced_by.length} of the closest matches but was missed by the
          keyword search. It shows{" "}
          {f.newly_found.map((id) => featureText.get(id) ?? id).join("; ")}, which no searched
          document did.
        </div>
      ))}

      <ul className="mt-5 space-y-3">
        {findings.map((f) => (
          <FindingRow key={f.id} finding={f} reportId={reportId} />
        ))}
      </ul>
      <EvidenceExplorer documents={documents} />
    </section>
  );
}

function FindingRow({ finding, reportId }: { finding: FeatureFinding; reportId?: string | null }) {
  const [showAll, setShowAll] = useState(false);
  const found = finding.evidence.length > 0;
  const shown = showAll ? finding.evidence : finding.evidence.slice(0, 1);

  return (
    <li className="rounded-lg border border-neutral-200 p-3 sm:p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
            found ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900"
          }`}
        >
          {found ? "Overlap found" : "Not found in the evidence reviewed"}
        </span>
        <span className="font-medium text-neutral-900">{finding.feature}</span>
      </div>

      {shown.map((e) => (
        <div key={e.result_id} className="mt-3">
          <blockquote className="border-l-2 border-amber-300 pl-3 text-sm italic text-neutral-700">
            &ldquo;{e.quote}&rdquo;
          </blockquote>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 pl-3 text-xs text-neutral-500">
            <a
              href={e.link}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-neutral-700 underline decoration-neutral-300 underline-offset-2 hover:decoration-neutral-700"
            >
              {e.title}
            </a>
            <span
              className={`rounded px-1.5 py-0.5 ${
                e.evidence_source === "snippet" ? "bg-yellow-50 text-yellow-800" : "bg-neutral-100"
              }`}
            >
              {e.section?.label ?? EVIDENCE_SOURCE_LABELS[e.evidence_source]}
            </span>
            {e.found_via === "citation" && (
              <span className="rounded bg-blue-50 px-1.5 py-0.5 text-blue-800">
                found by citation follow-up
              </span>
            )}
          </p>
          <QuotedSection evidence={e} />
        </div>
      ))}

      {finding.evidence.length > 1 && (
        <button
          onClick={() => setShowAll((v) => !v)}
          className="mt-2 pl-3 text-xs text-neutral-500 underline hover:text-neutral-900 print:hidden"
        >
          {showAll ? "Show one document" : `Also in ${finding.evidence.length - 1} more document(s)`}
        </button>
      )}
      {!found && reportId && <ChallengeFinding key={`${reportId}-${finding.id}`} reportId={reportId} featureId={finding.id} />}
    </li>
  );
}
