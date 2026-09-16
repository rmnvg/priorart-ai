"use client";

import { useState } from "react";
import { SAMPLE_IDEA } from "@/lib/sampleIdea";

interface IdeaFormProps {
  onSubmit: (ideaText: string) => void;
  disabled?: boolean;
}

const STEPS = [
  "Generates targeted patent search queries from your description",
  "Searches real patents, academic papers, and products on the market",
  "Scores novelty and tells you how to differentiate — with citations",
];

export default function IdeaForm({ onSubmit, disabled }: IdeaFormProps) {
  const [ideaText, setIdeaText] = useState("");
  const tooShort = ideaText.trim().length < 10;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (tooShort) return;
    onSubmit(ideaText);
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <h1 className="text-4xl font-bold tracking-tight text-neutral-900">
        Has your idea already been invented?
      </h1>
      <p className="mt-3 text-lg text-neutral-600">
        Describe an invention in plain English and get a novelty verdict backed by real
        prior art — in about a minute, not a $2,000 search.
      </p>

      <ul className="mt-5 space-y-1.5">
        {STEPS.map((step, i) => (
          <li key={step} className="flex gap-2.5 text-sm text-neutral-500">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-neutral-200 text-xs font-semibold text-neutral-600">
              {i + 1}
            </span>
            {step}
          </li>
        ))}
      </ul>

      <form onSubmit={handleSubmit} className="mt-7">
        <textarea
          value={ideaText}
          onChange={(e) => setIdeaText(e.target.value)}
          disabled={disabled}
          rows={6}
          placeholder="e.g. A smart water bottle that tracks how much you drink and reminds you to hydrate via a phone app, using a pressure sensor at the base."
          className="w-full resize-none rounded-xl border border-neutral-300 bg-white p-4 text-neutral-900 shadow-sm transition placeholder:text-neutral-400 focus:border-neutral-900 focus:outline-none focus:ring-4 focus:ring-neutral-900/5 disabled:bg-neutral-50 disabled:text-neutral-400"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => setIdeaText(SAMPLE_IDEA)}
            disabled={disabled}
            className="text-sm text-neutral-500 underline decoration-neutral-300 underline-offset-4 transition hover:text-neutral-900 disabled:opacity-50"
          >
            Try a sample idea
          </button>
          <div className="flex items-center gap-4">
            <span className="text-sm text-neutral-400">
              {tooShort ? "Add a bit more detail" : `${ideaText.trim().length} characters`}
            </span>
            <button
              type="submit"
              disabled={disabled || tooShort}
              className="rounded-lg bg-neutral-900 px-6 py-2.5 font-medium text-white shadow-sm transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:bg-neutral-300 disabled:shadow-none"
            >
              Analyze idea
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
