"use client";

import { useEffect, useState } from "react";
import { verdictLevel } from "@/components/NoveltyVerdict";
import { fetchExamples } from "@/lib/analyzeStream";
import { englishLabel } from "@/lib/i18n";
import type { ExampleReport } from "@/types/analysis";

const MAX_SHOWN = 6;

// Saved analyses anyone can open instantly — no API keys, no quota. This is
// what a visitor (or a judge cloning the repo) sees working first.
export default function ExamplesGallery({ onOpen }: { onOpen: (reportId: string) => void }) {
  const [examples, setExamples] = useState<ExampleReport[]>([]);

  useEffect(() => {
    fetchExamples().then((all) => setExamples(all.slice(0, MAX_SHOWN)));
  }, []);

  if (examples.length === 0) return null;

  return (
    <div className="mx-auto w-full max-w-2xl">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-400">
        Example reports
      </h2>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {examples.map((ex) => {
          const verdict = verdictLevel(ex.novelty_confidence);
          return (
            <button
              key={ex.report_id}
              onClick={() => onOpen(ex.report_id)}
              className="rounded-xl border border-neutral-200 bg-white p-4 text-left shadow-sm transition hover:border-neutral-400 hover:shadow"
            >
              <p className="line-clamp-3 text-sm text-neutral-800">{ex.idea_text}</p>
              <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-neutral-500">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: verdict.color }} />
                  <span className="font-medium text-neutral-700">
                    {Math.round(ex.novelty_confidence * 100)}% · {englishLabel(verdict.label)}
                  </span>
                </span>
                <span>{ex.results_count} results</span>
                {ex.public_domain_count > 0 && <span>{ex.public_domain_count} free to build on</span>}
                {ex.language_name !== "English" && (
                  <span className="rounded bg-orange-100 px-1.5 py-0.5 font-medium text-orange-800">
                    {ex.language_name}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
