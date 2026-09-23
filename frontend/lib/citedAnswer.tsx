import type { ReactNode } from "react";
import type { AnswerSource } from "@/types/analysis";

/** Splits an answer's inline [D3] keys into numbered source links — numbered
 * by first citation (1, 2, 3...) rather than the backend's document key, so
 * the reader sees a tidy sequence. Keys without a source are dropped (the
 * backend already strips those; this is belt and braces). */
export function renderCitedAnswer(answer: string, sources: AnswerSource[]): ReactNode[] {
  const numberByKey = new Map(sources.map((s, i) => [s.key, i + 1]));
  const sourceByKey = new Map(sources.map((s) => [s.key, s]));
  return answer.split(/\[(D\d+)\]/).map((part, i) => {
    // split() with a capture group alternates text, key, text, key...
    if (i % 2 === 0) return part;
    const source = sourceByKey.get(part);
    if (!source) return null;
    return (
      <a
        key={`${part}-${i}`}
        href={source.link}
        target="_blank"
        rel="noopener noreferrer"
        title={source.title}
        className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-blue-100 px-1 align-super text-[10px] font-semibold text-blue-800 no-underline hover:bg-blue-200"
      >
        {numberByKey.get(part)}
      </a>
    );
  });
}
