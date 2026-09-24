import { useState } from "react";
import type { NoveltyVerdict, RecheckComparison as Comparison } from "@/types/analysis";

const VERDICT_LABELS: Record<NoveltyVerdict, string> = {
  blocking: "blocking",
  partially_overlapping: "partial overlap",
  not_relevant: "not relevant",
};

const SOURCE_LABELS: Record<string, string> = {
  patent: "Patent",
  scholar: "Paper",
  product: "Product",
};

const NEW_MATCHES_SHOWN = 5;

// What changed after "Apply & re-check", shown as evidence rather than as a
// score: the ORIGINAL closest matches stay in view (a re-run search could
// otherwise just rank them lower and hide an unresolved overlap), each with
// quoted proof, plus any close matches the revised idea newly ran into.
export default function RecheckComparison({
  comparison,
  confidenceAfter,
  shownChange,
}: {
  comparison: Comparison;
  confidenceAfter: number;
  shownChange: string; // the change as the reader saw it (possibly translated)
}) {
  const [showAllNew, setShowAllNew] = useState(false);
  const originals = comparison.original_matches;
  const distinguished = originals.filter((m) => !m.change_found_in_document).length;
  const before = Math.round(comparison.confidence_before * 100);
  const after = Math.round(confidenceAfter * 100);
  const newShown = showAllNew ? comparison.new_matches : comparison.new_matches.slice(0, NEW_MATCHES_SHOWN);

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 shadow-sm sm:p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-blue-600">
        Re-checked after your change
      </p>
      <p className="mt-2 text-sm italic text-blue-950">&ldquo;{shownChange}&rdquo;</p>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-white p-3">
          <div className="text-2xl font-semibold text-neutral-900">
            {distinguished} of {originals.length}
          </div>
          <div className="text-xs text-neutral-600">
            original closest matches don&apos;t show your change
          </div>
        </div>
        <div className="rounded-lg bg-white p-3">
          <div className="text-2xl font-semibold text-neutral-900">{comparison.new_matches.length}</div>
          <div className="text-xs text-neutral-600">new close matches the revised idea ran into</div>
        </div>
        <div className="rounded-lg bg-white p-3">
          <div className="text-2xl font-semibold text-neutral-900">
            {before}% → {after}%
          </div>
          <div className="text-xs text-neutral-600">
            novelty confidence (a model estimate: the evidence here matters more)
          </div>
        </div>
      </div>

      {originals.length > 0 && (
        <section className="mt-5">
          <h3 className="text-sm font-semibold text-neutral-900">The original closest matches</h3>
          <ul className="mt-2 space-y-2">
            {originals.map((m) => (
              <li key={m.id} className="rounded-lg border border-neutral-200 bg-white p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <a
                    href={m.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-neutral-900 underline decoration-neutral-300 underline-offset-2 hover:decoration-neutral-900"
                  >
                    {m.title}
                  </a>
                  <span className="text-xs text-neutral-400">was: {VERDICT_LABELS[m.verdict_before]}</span>
                </div>
                {m.change_found_in_document ? (
                  <p className="mt-1.5 text-red-800">
                    <span className="font-semibold">✕ Already has your change.</span>{" "}
                    <span className="italic">&ldquo;{m.change_quote}&rdquo;</span>
                  </p>
                ) : (
                  <p className="mt-1.5 text-emerald-800">
                    <span className="font-semibold">✓ Your change isn&apos;t in this document</span>{" "}
                    <span className="text-neutral-500">(no passage in its text shows it)</span>
                  </p>
                )}
                <p className="mt-1 text-neutral-600">{m.explanation}</p>
                {m.still_shared.length > 0 && (
                  <div className="mt-2 border-t border-neutral-100 pt-2">
                    <p className="text-xs font-medium text-neutral-500">Still shared with it:</p>
                    <ul className="mt-1 space-y-1">
                      {m.still_shared.map((s) => (
                        <li key={s.feature} className="text-xs text-neutral-700">
                          <span className="font-medium">{s.feature}</span>{" "}
                          <span className="italic text-neutral-500">&ldquo;{s.quote}&rdquo;</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-5">
        <h3 className="text-sm font-semibold text-neutral-900">New close matches</h3>
        {comparison.new_matches.length === 0 ? (
          <p className="mt-1 text-sm text-neutral-600">
            The revised idea&apos;s search didn&apos;t turn up any close match the original search
            hadn&apos;t already found.
          </p>
        ) : (
          <>
            <p className="mt-1 text-sm text-neutral-600">
              Your change moved the idea toward work the original search never returned. Review
              these before settling on the change.
            </p>
            <ul className="mt-2 space-y-1.5">
              {newShown.map((m) => (
                <li key={m.id} className="text-sm leading-relaxed">
                  <span className="mr-1.5 inline-block rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-600">
                    {SOURCE_LABELS[m.source_type] ?? m.source_type}
                  </span>
                  <a
                    href={m.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-neutral-900 underline decoration-neutral-300 underline-offset-2 hover:decoration-neutral-900"
                  >
                    {m.title}
                  </a>
                  <span className="ml-1.5 whitespace-nowrap text-xs text-neutral-400">
                    {VERDICT_LABELS[m.verdict]}
                  </span>
                </li>
              ))}
            </ul>
            {comparison.new_matches.length > NEW_MATCHES_SHOWN && (
              <button
                onClick={() => setShowAllNew((v) => !v)}
                className="mt-2 text-xs text-blue-700 underline"
              >
                {showAllNew ? "Show fewer" : `Show all ${comparison.new_matches.length}`}
              </button>
            )}
          </>
        )}
      </section>

      <p className="mt-4 text-xs text-neutral-500">
        Checked against the original matches&apos;{" "}
        {comparison.evidence_basis === "full_text" ? "abstracts and leading claims" : "search snippets only"}
        . A passage is only reported when its quote is found word for word in the document.
      </p>
    </div>
  );
}
