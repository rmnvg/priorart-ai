"use client";

import { useState } from "react";

interface IdeaFormProps {
  onSubmit: (ideaText: string) => void;
  disabled?: boolean;
}

export default function IdeaForm({ onSubmit, disabled }: IdeaFormProps) {
  const [ideaText, setIdeaText] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (ideaText.trim().length < 10) return;
    onSubmit(ideaText);
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <h1 className="text-3xl font-bold tracking-tight text-neutral-900">PriorArt AI</h1>
      <p className="mt-2 text-neutral-600">
        Describe your invention idea in plain English. We&apos;ll search real patents,
        academic papers, and existing products, then give you a novelty verdict with
        concrete suggestions on how to differentiate it.
      </p>
      <form onSubmit={handleSubmit} className="mt-6">
        <textarea
          value={ideaText}
          onChange={(e) => setIdeaText(e.target.value)}
          disabled={disabled}
          rows={7}
          placeholder="e.g. A smart water bottle that tracks how much you drink and reminds you to hydrate via a phone app, using a pressure sensor at the base."
          className="w-full resize-none rounded-lg border border-neutral-300 p-4 text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-500 focus:outline-none disabled:bg-neutral-50 disabled:text-neutral-400"
        />
        <div className="mt-3 flex items-center justify-between">
          <span className="text-sm text-neutral-400">
            {ideaText.trim().length < 10
              ? "Add a bit more detail to get started"
              : `${ideaText.trim().length} characters`}
          </span>
          <button
            type="submit"
            disabled={disabled || ideaText.trim().length < 10}
            className="rounded-lg bg-neutral-900 px-5 py-2.5 font-medium text-white transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
          >
            Analyze idea
          </button>
        </div>
      </form>
    </div>
  );
}
