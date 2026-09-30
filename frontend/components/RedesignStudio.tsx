"use client";

import { useState } from "react";
import type { AppliedSuggestion } from "@/components/ResultsView";
import { fetchFeatures, fetchRedesign } from "@/lib/analyzeStream";
import type { DesignAlternative, Feature, RedesignResult } from "@/types/analysis";

const PRESET_CONSTRAINTS = [
  "No electricity",
  "Hand-operated",
  "Locally available materials",
  "Easy to repair locally",
  "No moving parts",
];
const MAX_CONSTRAINTS = 6;

const CHIP =
  "rounded-full border px-3 py-1 text-sm transition focus:outline-none focus:ring-2 focus:ring-neutral-900/20";
const CHIP_ON = "border-neutral-900 bg-neutral-900 text-white";
const CHIP_OFF = "border-neutral-300 bg-white text-neutral-700 hover:border-neutral-500";

// "Keep what matters, respect my limits, get away from the closest match."
// The inventor locks features and sets constraints; the model proposes
// three alternatives, each tied to a verified passage in a closest match it
// steps away from. Every design is labelled a hypothesis until re-checked,
// which runs the full search and the evidence comparison on it.
export default function RedesignStudio({
  reportId,
  onRecheck,
}: {
  reportId: string;
  onRecheck?: (design: AppliedSuggestion) => void;
}) {
  const [features, setFeatures] = useState<Feature[] | null>(null);
  const [locked, setLocked] = useState<Set<string>>(new Set());
  const [constraints, setConstraints] = useState<string[]>([]);
  const [custom, setCustom] = useState("");
  const [cost, setCost] = useState("");
  const [result, setResult] = useState<RedesignResult | null>(null);
  const [loading, setLoading] = useState<"features" | "designs" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const costValue = Number.parseInt(cost.replace(/[^\d]/g, ""), 10);
  const costTarget = Number.isFinite(costValue) && costValue > 0 ? costValue : null;
  const customConstraints = constraints.filter((c) => !PRESET_CONSTRAINTS.includes(c));

  async function start() {
    setLoading("features");
    setError(null);
    try {
      setFeatures(await fetchFeatures(reportId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load the idea's features.");
    } finally {
      setLoading(null);
    }
  }

  async function propose() {
    setLoading("designs");
    setError(null);
    try {
      setResult(
        await fetchRedesign(reportId, {
          locked_features: [...locked],
          constraints,
          cost_target_inr: costTarget,
        })
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't propose designs.");
    } finally {
      setLoading(null);
    }
  }

  function toggleLock(id: string) {
    setLocked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleConstraint(c: string) {
    setConstraints((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : prev.length < MAX_CONSTRAINTS ? [...prev, c] : prev
    );
  }

  function addCustom(e: React.FormEvent) {
    e.preventDefault();
    const c = custom.trim().replace(/\s+/g, " ").slice(0, 120);
    if (c && !constraints.some((x) => x.toLowerCase() === c.toLowerCase()) && constraints.length < MAX_CONSTRAINTS) {
      setConstraints((prev) => [...prev, c]);
    }
    setCustom("");
  }

  return (
    <div className="rounded-xl border border-violet-200 bg-violet-50/40 p-4 shadow-sm sm:p-5 print:hidden">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold text-neutral-900">Redesign studio</h2>
        <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800">
          Designs are hypotheses until re-checked
        </span>
      </div>
      <p className="mt-1 text-sm text-neutral-600">
        Choose what must stay and the limits you&apos;re working within. Get three alternative
        designs, each tied to the passage in a closest match it moves away from, then re-check
        the one you like.
      </p>

      {!features && (
        <div className="mt-4">
          <button
            onClick={start}
            disabled={loading !== null}
            className="rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-violet-800 disabled:bg-violet-300"
          >
            {loading === "features" ? "Reading your idea's features…" : "Start a redesign"}
          </button>
          {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
        </div>
      )}

      {features && (
        <div className="mt-5 space-y-5">
          <section>
            <h3 className="text-sm font-semibold text-neutral-900">1 · What must stay?</h3>
            <p className="text-xs text-neutral-500">Lock the features every design has to keep.</p>
            <ul className="mt-2 space-y-1.5">
              {features.map((f) => {
                const on = locked.has(f.id);
                return (
                  <li key={f.id}>
                    <button
                      type="button"
                      onClick={() => toggleLock(f.id)}
                      aria-pressed={on}
                      className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left text-sm transition ${
                        on
                          ? "border-violet-400 bg-white text-neutral-900 ring-1 ring-violet-300"
                          : "border-neutral-200 bg-white/70 text-neutral-700 hover:border-neutral-400"
                      }`}
                    >
                      <span
                        className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${
                          on ? "bg-violet-700 text-white" : "bg-neutral-100 text-neutral-500"
                        }`}
                      >
                        {on ? "Must keep" : "Can change"}
                      </span>
                      {f.text}
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-neutral-900">2 · Your constraints</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {[...PRESET_CONSTRAINTS, ...customConstraints].map((c) => {
                const on = constraints.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => toggleConstraint(c)}
                    aria-pressed={on}
                    className={`${CHIP} ${on ? CHIP_ON : CHIP_OFF}`}
                  >
                    {on && <span aria-hidden>✓ </span>}
                    {c}
                  </button>
                );
              })}
            </div>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
              <form onSubmit={addCustom} className="flex flex-1 gap-2">
                <input
                  value={custom}
                  onChange={(e) => setCustom(e.target.value)}
                  maxLength={120}
                  placeholder="Add your own, e.g. fits in a bicycle basket"
                  aria-label="Add a constraint"
                  className="min-w-0 flex-1 rounded-md border border-neutral-300 bg-white px-2.5 py-1.5 text-sm focus:border-neutral-900 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={!custom.trim() || constraints.length >= MAX_CONSTRAINTS}
                  className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
                >
                  Add
                </button>
              </form>
              <label className="flex items-center gap-2 text-sm text-neutral-700">
                <span className="whitespace-nowrap">Target cost under ₹</span>
                <input
                  value={cost}
                  onChange={(e) => setCost(e.target.value)}
                  inputMode="numeric"
                  placeholder="2,000"
                  aria-label="Target cost per unit in rupees"
                  className="w-24 rounded-md border border-neutral-300 bg-white px-2.5 py-1.5 text-sm focus:border-neutral-900 focus:outline-none"
                />
                <span className="text-neutral-500">per unit</span>
              </label>
            </div>
          </section>

          <div>
            <button
              onClick={propose}
              disabled={loading !== null}
              className="rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-violet-800 disabled:bg-violet-300"
            >
              {loading === "designs" ? "Designing alternatives…" : result ? "Propose again with these choices" : "Propose 3 designs"}
            </button>
            <p className="mt-2 text-xs text-neutral-500">
              About 15 seconds; uses no search credits.
            </p>
            {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
          </div>

          {result && <Alternatives result={result} onRecheck={onRecheck} />}
        </div>
      )}
    </div>
  );
}

function Alternatives({
  result,
  onRecheck,
}: {
  result: RedesignResult;
  onRecheck?: (design: AppliedSuggestion) => void;
}) {
  const featureText = new Map(result.features.map((f) => [f.id, f.text]));
  const basis =
    result.evidence_basis === "full_text" ? "abstracts and leading claims" : "search snippets only";

  return (
    <section className="space-y-3">
      {result.alternatives.map((alt, i) => (
        <DesignCard
          key={`${i}-${alt.title}`}
          index={i + 1}
          design={alt}
          constraints={result.constraints}
          featureText={featureText}
          onRecheck={onRecheck}
        />
      ))}
      <p className="text-xs text-neutral-500">
        Proposed by the model from the {result.matches_considered.length} original closest
        matches&apos; {basis}. A passage is shown only when its quote is found word for word in
        the document
        {result.unverified_quotes_dropped > 0 &&
          ` (${result.unverified_quotes_dropped} that weren't were left out)`}
        . Costs and performance are design targets, not tested. Re-check a design to search it
        and compare it with the original closest matches.
      </p>
    </section>
  );
}

function DesignCard({
  index,
  design,
  constraints,
  featureText,
  onRecheck,
}: {
  index: number;
  design: DesignAlternative;
  constraints: string[];
  featureText: Map<string, string>;
  onRecheck?: (design: AppliedSuggestion) => void;
}) {
  const noteFor = new Map(design.constraint_notes.map((n) => [n.constraint, n.approach]));

  return (
    <article className="rounded-lg border border-neutral-200 bg-white p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold text-neutral-900">
          {index}. {design.title}
        </h3>
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
          Hypothesis · not yet re-checked
        </span>
      </div>
      <p className="mt-2 leading-relaxed text-neutral-700">{design.how_it_works}</p>
      {design.what_changes && (
        <p className="mt-2 text-neutral-700">
          <span className="font-medium text-neutral-900">What changes: </span>
          {design.what_changes}
        </p>
      )}

      <div className="mt-3 border-t border-neutral-100 pt-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">Moves away from</p>
        {design.avoids.length === 0 ? (
          <p className="mt-1 text-neutral-600">
            No passage in the closest matches backs this difference. Treat it with extra caution.
          </p>
        ) : (
          <ul className="mt-1 space-y-2">
            {design.avoids.map((v) => (
              <li key={v.document_id}>
                <span className="text-neutral-900">{v.mechanism}</span>{" "}
                <span className="text-neutral-500">in </span>
                <a
                  href={v.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-neutral-700 underline decoration-neutral-300 underline-offset-2 hover:decoration-neutral-900"
                >
                  {v.title}
                </a>
                <blockquote className="mt-1 border-l-2 border-neutral-200 pl-2.5 text-xs italic text-neutral-500">
                  &ldquo;{v.quote}&rdquo;
                </blockquote>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(design.keeps.length > 0 || design.drops_locked.length > 0) && (
        <div className="mt-3 border-t border-neutral-100 pt-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">Must-keep features</p>
          <ul className="mt-1 space-y-0.5">
            {design.keeps.map((id) => (
              <li key={id} className="text-emerald-800">
                ✓ {featureText.get(id) ?? id}
              </li>
            ))}
            {design.drops_locked.map((id) => (
              <li key={id} className="text-red-800">
                ✕ Doesn&apos;t say it keeps: {featureText.get(id) ?? id}
              </li>
            ))}
          </ul>
        </div>
      )}

      {constraints.length > 0 && (
        <div className="mt-3 border-t border-neutral-100 pt-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
            Constraints · design targets, not tested
          </p>
          <ul className="mt-1 space-y-1">
            {constraints.map((c) => (
              <li key={c} className="text-neutral-700">
                <span className="font-medium text-neutral-900">{c}:</span>{" "}
                {noteFor.get(c) ?? <span className="text-neutral-400">not addressed by this design</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {onRecheck && (
        <button
          onClick={() =>
            onRecheck({
              english: design.change_summary,
              shown: `${design.title}: ${design.what_changes || design.change_summary}`,
              revisedIdea: design.revised_idea,
            })
          }
          className="mt-4 rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-neutral-700"
        >
          Re-check this design →
        </button>
      )}
    </article>
  );
}
