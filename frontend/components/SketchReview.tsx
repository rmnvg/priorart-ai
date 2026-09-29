"use client";

import { composeIdeaFromSketch, nextPartId, removePart, type SketchDraft } from "@/lib/sketch";

const INPUT =
  "w-full rounded-md border border-neutral-300 bg-white px-2.5 py-1.5 text-sm text-neutral-900 focus:border-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-900/10";
const REMOVE =
  "shrink-0 rounded-md px-2 py-1.5 text-sm text-neutral-400 transition hover:bg-neutral-100 hover:text-neutral-900";
const ADD = "mt-2 text-sm text-neutral-600 underline decoration-neutral-300 underline-offset-4 hover:text-neutral-900";

// What the vision model read from the inventor's sketch, laid out for
// correction. Nothing is searched until the inventor confirms it here, and
// what gets searched is shown word for word before they do.
export default function SketchReview({
  image,
  draft,
  uncertain,
  onChange,
  onSearch,
  onEditAsText,
  onDiscard,
}: {
  image: string;
  draft: SketchDraft;
  uncertain: string[];
  onChange: (draft: SketchDraft) => void;
  onSearch: (ideaText: string) => void;
  onEditAsText: (ideaText: string) => void;
  onDiscard: () => void;
}) {
  const composed = composeIdeaFromSketch(draft);
  const namedParts = draft.parts.filter((p) => p.name.trim());
  const tooShort = composed.trim().length < 10;

  function updatePart(id: string, field: "name" | "description", value: string) {
    onChange({ ...draft, parts: draft.parts.map((p) => (p.id === id ? { ...p, [field]: value } : p)) });
  }

  function updateConnection(index: number, field: "source" | "target" | "relation", value: string) {
    onChange({
      ...draft,
      connections: draft.connections.map((c, i) => (i === index ? { ...c, [field]: value } : c)),
    });
  }

  return (
    <div className="mt-7 rounded-xl border border-neutral-200 bg-white p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-neutral-900">Here&apos;s what we read from your sketch</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Fix anything we got wrong. Only what you confirm here is searched.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-[180px_1fr]">
        <img
          src={image}
          alt="Your uploaded sketch"
          className="max-h-56 w-full rounded-lg border border-neutral-200 bg-neutral-50 object-contain"
        />

        <div className="space-y-5">
          <label className="block">
            <span className="text-sm font-medium text-neutral-900">What it&apos;s for</span>
            <input
              value={draft.purpose}
              onChange={(e) => onChange({ ...draft, purpose: e.target.value })}
              placeholder="e.g. Keeps vegetables cool without electricity"
              className={`mt-1 ${INPUT}`}
            />
          </label>

          <div>
            <p className="text-sm font-medium text-neutral-900">Parts</p>
            <ul className="mt-1 space-y-2">
              {draft.parts.map((part) => (
                <li key={part.id} className="flex flex-col gap-1.5 sm:flex-row sm:items-center">
                  <input
                    value={part.name}
                    onChange={(e) => updatePart(part.id, "name", e.target.value)}
                    aria-label="Part name"
                    placeholder="Part"
                    className={`${INPUT} sm:w-44`}
                  />
                  <div className="flex flex-1 items-center gap-1.5">
                    <input
                      value={part.description}
                      onChange={(e) => updatePart(part.id, "description", e.target.value)}
                      aria-label={`What ${part.name || "this part"} is or does`}
                      placeholder="What it is, what it's made of, what it does"
                      className={INPUT}
                    />
                    <button
                      type="button"
                      onClick={() => onChange(removePart(draft, part.id))}
                      aria-label={`Remove ${part.name || "this part"}`}
                      className={REMOVE}
                    >
                      ✕
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() =>
                onChange({
                  ...draft,
                  parts: [...draft.parts, { id: nextPartId(draft.parts), name: "", description: "" }],
                })
              }
              className={ADD}
            >
              + Add a part
            </button>
          </div>

          <div>
            <p className="text-sm font-medium text-neutral-900">How the parts work together</p>
            {draft.connections.length === 0 && (
              <p className="mt-1 text-sm text-neutral-500">No connections read from the drawing.</p>
            )}
            <ul className="mt-1 space-y-2">
              {draft.connections.map((c, i) => (
                <li key={i} className="flex flex-wrap items-center gap-1.5 sm:flex-nowrap">
                  <select
                    value={c.source}
                    onChange={(e) => updateConnection(i, "source", e.target.value)}
                    aria-label="From part"
                    className={`${INPUT} w-auto sm:max-w-40`}
                  >
                    {namedParts.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  <input
                    value={c.relation}
                    onChange={(e) => updateConnection(i, "relation", e.target.value)}
                    aria-label="How they connect"
                    placeholder="sits inside"
                    className={`${INPUT} min-w-28 flex-1`}
                  />
                  <select
                    value={c.target}
                    onChange={(e) => updateConnection(i, "target", e.target.value)}
                    aria-label="To part"
                    className={`${INPUT} w-auto sm:max-w-40`}
                  >
                    {namedParts.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() =>
                      onChange({ ...draft, connections: draft.connections.filter((_, j) => j !== i) })
                    }
                    aria-label="Remove this connection"
                    className={REMOVE}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
            {namedParts.length >= 2 && (
              <button
                type="button"
                onClick={() =>
                  onChange({
                    ...draft,
                    connections: [
                      ...draft.connections,
                      { source: namedParts[0].id, target: namedParts[1].id, relation: "" },
                    ],
                  })
                }
                className={ADD}
              >
                + Add a connection
              </button>
            )}
          </div>

          {uncertain.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-3 text-sm text-amber-900">
              <p className="font-medium">We couldn&apos;t tell from the drawing:</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {uncertain.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
              <p className="mt-1.5 text-xs text-amber-800">
                If it matters to how your invention works, answer below.
              </p>
            </div>
          )}

          <label className="block">
            <span className="text-sm font-medium text-neutral-900">Anything the drawing doesn&apos;t show</span>
            <textarea
              value={draft.details}
              onChange={(e) => onChange({ ...draft, details: e.target.value })}
              rows={2}
              placeholder="Materials, sizes, how it's used... (any language)"
              className={`mt-1 resize-none ${INPUT}`}
            />
          </label>
        </div>
      </div>

      <div className="mt-5 rounded-lg bg-neutral-50 p-3.5">
        <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">What will be searched</p>
        <p className="mt-1 text-sm leading-relaxed text-neutral-700">
          {composed || <span className="text-neutral-400">Add a purpose or a part to search.</span>}
        </p>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-end gap-x-4 gap-y-2">
        <button
          type="button"
          onClick={onDiscard}
          className="text-sm text-neutral-500 underline decoration-neutral-300 underline-offset-4 hover:text-neutral-900"
        >
          Discard sketch
        </button>
        <button
          type="button"
          onClick={() => onEditAsText(composed)}
          disabled={tooShort}
          className="text-sm text-neutral-500 underline decoration-neutral-300 underline-offset-4 hover:text-neutral-900 disabled:opacity-50"
        >
          Edit as text instead
        </button>
        <button
          type="button"
          onClick={() => onSearch(composed)}
          disabled={tooShort}
          className="rounded-lg bg-neutral-900 px-6 py-2.5 font-medium text-white shadow-sm transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
        >
          Search prior art
        </button>
      </div>
    </div>
  );
}
