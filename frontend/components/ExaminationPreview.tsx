"use client";

import { useState } from "react";
import { fetchExamination } from "@/lib/analyzeStream";
import type { ExaminationOutcome, ExaminationPreview as Preview } from "@/types/analysis";

// Status colors carry the outcome's severity, always beside a word and an
// icon — never color alone.
const OUTCOMES: Record<
  ExaminationOutcome,
  { icon: string; title: string; body: string; box: string; text: string }
> = {
  novelty_objection: {
    icon: "✕",
    title: "Likely objection: lack of novelty — Section 2(1)(j)",
    body: "A single document found in the search discloses every element of your idea.",
    box: "border-red-200 bg-red-50",
    text: "text-red-900",
  },
  inventive_step_objection: {
    icon: "!",
    title: "Likely objection: lack of inventive step — Section 2(1)(ja)",
    body: "No single document has everything, but two of them together do. An examiner could argue the combination is obvious.",
    box: "border-amber-200 bg-amber-50",
    text: "text-amber-900",
  },
  combination_risk: {
    icon: "!",
    title: "Inventive-step risk",
    body: "Every element appears somewhere, but only spread across three or more documents — a weaker argument for an examiner, but a real one.",
    box: "border-amber-200 bg-amber-50/60",
    text: "text-amber-900",
  },
  no_objection_found: {
    icon: "✓",
    title: "No novelty or inventive-step objection from these documents",
    body: "At least one element of your idea appears in none of the documents found — that's what an application would be built around.",
    box: "border-emerald-200 bg-emerald-50",
    text: "text-emerald-900",
  },
};

function CoverageMark({ status }: { status: "disclosed" | "partial" | null }) {
  if (status === "disclosed") {
    return <span aria-label="disclosed" className="inline-block h-3 w-3 rounded-full bg-blue-700" />;
  }
  if (status === "partial") {
    return (
      <span
        aria-label="partly disclosed"
        className="inline-block h-3 w-3 rounded-full border-2 border-blue-700"
        style={{ background: "linear-gradient(90deg, #1d4ed8 50%, transparent 50%)" }}
      />
    );
  }
  return <span aria-label="not disclosed" className="text-neutral-300">·</span>;
}

// "How would an Indian patent examiner see this?" — computed on request
// (LLM only, no searches), then cached server-side for the report.
export default function ExaminationPreview({ reportId }: { reportId: string }) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ element: string; document: string } | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setPreview(await fetchExamination(reportId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't prepare the preview.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold text-neutral-900">Examination preview</h2>
        <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">
          Simulated · Indian Patents Act, 1970
        </span>
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        How an Indian patent examiner might read this evidence — before you pay filing fees.
        Not issued by the Indian Patent Office.
      </p>

      {!preview && (
        <div className="mt-4 print:hidden">
          <button
            onClick={load}
            disabled={loading}
            className="rounded-lg bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-neutral-700 disabled:bg-neutral-400"
          >
            {loading ? "Examining the evidence…" : "See how an Indian patent examiner would respond"}
          </button>
          <p className="mt-2 text-xs text-neutral-400">
            Checks Section 3 exclusions, then tests each element of your idea against the
            documents found. About 10 seconds; uses no search credits.
          </p>
          {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
        </div>
      )}

      {preview && <PreviewBody preview={preview} selected={selected} onSelect={setSelected} />}
    </div>
  );
}

function PreviewBody({
  preview,
  selected,
  onSelect,
}: {
  preview: Preview;
  selected: { element: string; document: string } | null;
  onSelect: (cell: { element: string; document: string } | null) => void;
}) {
  const outcome = OUTCOMES[preview.outcome];
  const docByKey = new Map(preview.documents.map((d) => [d.key, d]));
  const elementText = new Map(preview.elements.map((e) => [e.id, e.text]));
  const cell = new Map(preview.coverage.map((c) => [`${c.element}|${c.document}`, c]));
  const selectedCell = selected ? cell.get(`${selected.element}|${selected.document}`) : undefined;
  const docLabel = (key: string) => docByKey.get(key)?.title ?? key;

  return (
    <div className="mt-4 space-y-6">
      {preview.evidence_basis === "snippets" && (
        // Short snippets rarely mention every feature a document actually
        // claims, so thin evidence makes an idea look more novel than it is.
        // Say so before the verdict, not in the footnote.
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span className="font-semibold">Limited evidence.</span> This report was saved before
          full patent texts were kept, so only short search snippets could be checked. Expect
          fewer matches than a real examination would find; treat &ldquo;not found&rdquo; below
          as &ldquo;not visible in the snippet&rdquo;.
        </div>
      )}

      <div className={`flex gap-3 rounded-lg border p-4 ${outcome.box}`}>
        <span className={`text-lg font-bold leading-6 ${outcome.text}`} aria-hidden>
          {outcome.icon}
        </span>
        <div className={outcome.text}>
          <p className="font-semibold">{outcome.title}</p>
          <p className="mt-0.5 text-sm opacity-90">{outcome.body}</p>
          {preview.novelty_objections.map((key) => (
            <p key={key} className="mt-1.5 text-sm">
              Anticipated by{" "}
              <a href={docByKey.get(key)?.link} target="_blank" rel="noopener noreferrer" className="font-medium underline">
                {key} · {docLabel(key)}
              </a>
            </p>
          ))}
          {preview.inventive_step_objections.map((obj) => (
            <p key={obj.documents.join("+")} className="mt-1.5 text-sm">
              {obj.documents.map((key, i) => (
                <span key={key}>
                  {i > 0 && " + "}
                  <a href={docByKey.get(key)?.link} target="_blank" rel="noopener noreferrer" className="font-medium underline">
                    {key} · {docLabel(key)}
                  </a>
                </span>
              ))}
              {obj.same_field && <span className="ml-1 opacity-80">(same technical field)</span>}
            </p>
          ))}
        </div>
      </div>

      <section>
        <h3 className="font-semibold text-neutral-900">Section 3 — is it an &ldquo;invention&rdquo; at all?</h3>
        {preview.section3_flags.length === 0 ? (
          <p className="mt-1 text-sm text-neutral-600">
            <span className="font-semibold text-emerald-700">✓</span> Nothing in the idea as described
            falls under a Section 3 exclusion.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {preview.section3_flags.map((f) => (
              <li key={f.clause} className="rounded-lg border border-neutral-200 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-neutral-900 px-1.5 py-0.5 font-mono text-xs text-white">
                    s. {f.clause}
                  </span>
                  <span className="font-medium text-neutral-900">{f.title}</span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                      f.risk === "high" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {f.risk === "high" ? "High risk" : "Possible"}
                  </span>
                </div>
                <p className="mt-1.5 text-neutral-700">{f.reason}</p>
                <p className="mt-1 text-neutral-700">
                  <span className="font-medium">What helps:</span> {f.how_to_address}
                </p>
                <p className="mt-1.5 text-xs italic text-neutral-400">The law: {f.law_summary}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {preview.documents.length > 0 && (
        <section>
          <h3 className="font-semibold text-neutral-900">Element-by-element check</h3>
          <p className="mt-1 text-sm text-neutral-500">
            Each mark is backed by a sentence quoted from the document and checked against its
            text. Tap a mark to read the evidence.
          </p>
          {preview.documents.length > 3 && (
            <p className="mt-2 text-xs text-neutral-400 sm:hidden">Swipe the table sideways to see all {preview.documents.length} documents →</p>
          )}
          <div className="mt-3 overflow-x-auto">
            <table className="w-full border-separate border-spacing-0 text-sm">
              <thead>
                <tr>
                  <th className="sticky left-0 bg-white pb-2 pr-3 text-left text-xs font-medium text-neutral-500">
                    Element of your idea
                  </th>
                  {preview.documents.map((d) => (
                    <th key={d.key} className="px-1 pb-2 text-center text-xs font-medium text-neutral-500">
                      <a href={d.link} target="_blank" rel="noopener noreferrer" title={d.title} className="hover:text-neutral-900">
                        {d.key}
                      </a>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.elements.map((e) => {
                  const uncovered = preview.uncovered_elements.includes(e.id);
                  return (
                    <tr key={e.id}>
                      <td className="sticky left-0 min-w-44 max-w-64 border-t border-neutral-100 bg-white py-2 pr-3 align-top text-neutral-800">
                        {e.text}
                        {uncovered && (
                          <span className="ml-1.5 whitespace-nowrap rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-medium text-emerald-800">
                            not in searched documents
                          </span>
                        )}
                      </td>
                      {preview.documents.map((d) => {
                        const c = cell.get(`${e.id}|${d.key}`);
                        const isSelected = selected?.element === e.id && selected?.document === d.key;
                        return (
                          <td key={d.key} className="border-t border-neutral-100 px-1 py-2 text-center align-top">
                            {c ? (
                              <button
                                onClick={() => onSelect(isSelected ? null : { element: e.id, document: d.key })}
                                aria-label={`${c.status} in ${d.key}: show quote`}
                                aria-pressed={isSelected}
                                className={`flex h-7 w-7 items-center justify-center rounded-md transition ${
                                  isSelected ? "bg-blue-100 ring-2 ring-blue-400" : "hover:bg-neutral-100"
                                }`}
                              >
                                <CoverageMark status={c.status} />
                              </button>
                            ) : (
                              <span className="inline-flex h-7 w-7 items-center justify-center">
                                <CoverageMark status={null} />
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {selectedCell && (
            <blockquote className="mt-3 rounded-lg border-l-4 border-blue-300 bg-blue-50/60 px-3 py-2 text-sm text-neutral-800">
              <p className="text-xs font-medium text-neutral-500">
                {selectedCell.status === "disclosed" ? "Disclosed" : "Partly disclosed"} in{" "}
                {selectedCell.document} · {docLabel(selectedCell.document)} — for &ldquo;
                {elementText.get(selectedCell.element)}&rdquo;
              </p>
              <p className="mt-1 italic">&ldquo;{selectedCell.quote}&rdquo;</p>
            </blockquote>
          )}

          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500">
            <span className="flex items-center gap-1.5">
              <CoverageMark status="disclosed" /> disclosed
            </span>
            <span className="flex items-center gap-1.5">
              <CoverageMark status="partial" /> partly (doesn&apos;t count toward an objection)
            </span>
            <span className="flex items-center gap-1.5">
              <CoverageMark status={null} /> not found
            </span>
          </div>
          <ol className="mt-2 space-y-0.5 text-xs text-neutral-500">
            {preview.documents.map((d) => (
              <li key={d.key}>
                <span className="font-medium text-neutral-700">{d.key}</span>{" "}
                <a href={d.link} target="_blank" rel="noopener noreferrer" className="underline decoration-neutral-300 hover:text-neutral-900">
                  {d.title}
                </a>
              </li>
            ))}
          </ol>
        </section>
      )}

      {preview.uncovered_elements.length > 0 && (
        <section className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-4">
          <h3 className="font-semibold text-emerald-900">Your novelty core</h3>
          <p className="mt-1 text-sm text-emerald-800">
            None of the searched documents disclose these (that doesn&apos;t mean no document
            anywhere does). An application would need to be built
            around them — tell your patent agent this first.
          </p>
          <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-emerald-900">
            {preview.uncovered_elements.map((id) => (
              <li key={id}>{elementText.get(id)}</li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-neutral-400">
        Based on {preview.documents.length} documents found by this search (
        {preview.evidence_basis === "full_text"
          ? "abstracts and leading claims"
          : "search snippets only"}
        ). A real examiner searches far more widely, so &ldquo;no objection&rdquo; here means none
        from these documents.
        {preview.unverified_quotes_dropped > 0 &&
          ` ${preview.unverified_quotes_dropped} finding${preview.unverified_quotes_dropped === 1 ? " was" : "s were"} discarded because the quoted evidence couldn't be found in the document.`}{" "}
        A preview, not a legal opinion — a registered patent agent must confirm.
      </p>
    </div>
  );
}
