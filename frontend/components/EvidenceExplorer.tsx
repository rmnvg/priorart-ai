import { highlightSpans } from "@/lib/highlightText";
import type { EvidenceSection, ExaminedDocument, FeatureEvidence } from "@/types/analysis";

function SectionText({ section, quote }: { section: EvidenceSection; quote?: string }) {
  // Match the verifier's whitespace normalization for display/highlighting.
  const text = section.text.replace(/\s+/g, " ");
  const cleaned = quote?.replace(/\s+/g, " ").trim().replace(/[ .…]+$/, "").replace(/^"|"$/g, "") ?? "";
  return <div className="mt-2">
    <p className="text-xs text-neutral-500">
      {section.label} · {section.text.length.toLocaleString()} of {section.original_chars.toLocaleString()} characters reviewed
      {section.truncated ? " · Excerpt; remaining text was not reviewed" : " · Complete retrieved section"}
    </p>
    <p className="mt-2 max-h-64 overflow-y-auto rounded-lg bg-neutral-50 p-3 text-sm leading-relaxed text-neutral-700">
      {highlightSpans(text, [{ text: cleaned, color: "#fde68a", key: "evidence" }])}
    </p>
  </div>;
}

export function QuotedSection({ evidence }: { evidence: FeatureEvidence }) {
  if (!evidence.section) return <p className="mt-2 pl-3 text-xs text-neutral-500">This saved finding has no section-level source record. Open the source to inspect its context.</p>;
  return <details className="mt-2 rounded-lg border border-neutral-200 p-3">
    <summary className="cursor-pointer text-sm font-medium">Inspect passage in {evidence.section.label}</summary>
    <SectionText section={evidence.section} quote={evidence.quote} />
    <p className="mt-2 text-xs text-neutral-500">The passage was matched to this source text. Whether it supports the feature is an AI assessment you can check here.</p>
  </details>;
}

export default function EvidenceExplorer({ documents }: { documents: ExaminedDocument[] }) {
  if (!documents.length) return null;
  return <details className="mt-5 border-t border-neutral-200 pt-4">
    <summary className="cursor-pointer text-sm font-medium">Review scope & source text · {documents.length} documents</summary>
    <p className="mt-2 text-xs text-neutral-500">Only the sections listed here were supplied for the initial evidence assessment. Unreviewed text may contain additional information.</p>
    <div className="mt-3 space-y-3">
      {documents.map((doc) => <details key={doc.id} className="rounded-lg border border-neutral-200 p-3">
        <summary className="cursor-pointer text-sm font-medium">{doc.title}</summary>
        {doc.sections?.length ? <>
          {doc.source_type === "patent" && <p className="mt-2 text-xs text-neutral-500">
            {doc.sections.filter((s) => s.source === "claims").length} of {doc.total_claims ?? 0} retrieved claims reviewed; full specification not reviewed.
          </p>}
          {doc.sections.map((section) => <SectionText key={section.label} section={section} />)}
        </> : <p className="mt-2 text-xs text-neutral-500">Legacy report: section coverage was not recorded.</p>}
        <a href={doc.link} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-xs underline">Open original source</a>
      </details>)}
    </div>
  </details>;
}
