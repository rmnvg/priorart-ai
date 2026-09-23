"use client";

import { useState } from "react";
import VoiceInput from "@/components/VoiceInput";
import { HINDI_SAMPLE_IDEA, SAMPLE_IDEA } from "@/lib/sampleIdea";

interface IdeaFormProps {
  onSubmit: (ideaText: string) => void;
  disabled?: boolean;
  // false = backend has no API keys (saved reports only); null = unknown.
  live?: boolean | null;
}

const STEPS = [
  "Generates targeted patent search queries from your description",
  "Searches real patents, academic papers, and products on the market",
  "Scores novelty and tells you how to differentiate — with citations",
  "Works in Hindi, Tamil, Bengali and other Indian languages — type or speak",
];

export default function IdeaForm({ onSubmit, disabled, live }: IdeaFormProps) {
  const [ideaText, setIdeaText] = useState("");
  const tooShort = ideaText.trim().length < 10;

  function appendTranscript(text: string) {
    if (!text) return;
    setIdeaText((prev) => (prev.trim() ? `${prev.trimEnd()} ${text}` : text));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (tooShort) return;
    onSubmit(ideaText);
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <h1 className="text-3xl font-bold tracking-tight text-neutral-900 sm:text-4xl">
        Has your idea already been invented?
      </h1>
      <p className="mt-3 text-base text-neutral-600 sm:text-lg">
        Describe an invention in plain words — English, Hindi or any Indian language — and get a novelty verdict backed by real
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

      {live === false && (
        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span className="font-semibold">Demo mode.</span> No API keys are configured, so new
          ideas can&apos;t be analyzed here, but the example reports below are fully
          interactive. Add <code className="font-mono text-xs">SERPAPI_API_KEY</code> and{" "}
          <code className="font-mono text-xs">GROQ_API_KEY</code> to{" "}
          <code className="font-mono text-xs">backend/.env</code> to run live.
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-7">
        <textarea
          value={ideaText}
          onChange={(e) => setIdeaText(e.target.value)}
          disabled={disabled}
          rows={6}
          placeholder="e.g. A smart water bottle that tracks how much you drink and reminds you to hydrate via a phone app, using a pressure sensor at the base. (Any Indian language works.)"
          className="w-full resize-none rounded-xl border border-neutral-300 bg-white p-4 text-neutral-900 shadow-sm transition placeholder:text-neutral-400 focus:border-neutral-900 focus:outline-none focus:ring-4 focus:ring-neutral-900/5 disabled:bg-neutral-50 disabled:text-neutral-400"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <VoiceInput onTranscript={appendTranscript} disabled={disabled} />
            <button
              type="button"
              onClick={() => setIdeaText(SAMPLE_IDEA)}
              disabled={disabled}
              className="text-sm text-neutral-500 underline decoration-neutral-300 underline-offset-4 transition hover:text-neutral-900 disabled:opacity-50"
            >
              Try a sample
            </button>
            <button
              type="button"
              onClick={() => setIdeaText(HINDI_SAMPLE_IDEA)}
              disabled={disabled}
              className="text-sm text-neutral-500 underline decoration-neutral-300 underline-offset-4 transition hover:text-neutral-900 disabled:opacity-50"
            >
              हिंदी में उदाहरण
            </button>
          </div>
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
