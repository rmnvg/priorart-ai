"use client";

import { useState } from "react";
import { askReport } from "@/lib/analyzeStream";
import { renderCitedAnswer } from "@/lib/citedAnswer";
import type { Translate } from "@/lib/i18n";
import type { AnswerSource, AskTurn } from "@/types/analysis";

interface Exchange extends AskTurn {
  sources: AnswerSource[];
}

// Follow-up questions about a saved report, answered strictly from what its
// searches found, with the documents cited. Asked in Hindi, answered in Hindi.
export default function AskReport({ reportId, t }: { reportId: string; t: Translate }) {
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask(text: string) {
    const q = text.trim();
    if (q.length < 3 || pending) return;
    setPending(q);
    setError(null);
    setQuestion("");
    try {
      const history = exchanges.map(({ question, answer }) => ({ question, answer }));
      const answer = await askReport(reportId, q, history);
      setExchanges((prev) => [...prev, { question: q, answer: answer.answer, sources: answer.sources }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't get an answer.");
      setQuestion(q); // give the question back so it can be retried
    } finally {
      setPending(null);
    }
  }

  const suggestions = [t("ask_q1"), t("ask_q2"), t("ask_q3")];

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 shadow-sm sm:p-5 print:hidden">
      <h2 className="text-lg font-semibold text-neutral-900">{t("ask_title")}</h2>
      <p className="mt-1 text-sm text-neutral-500">{t("ask_subtitle")}</p>

      {exchanges.length > 0 && (
        <div className="mt-4 space-y-4">
          {exchanges.map((ex, i) => (
            <div key={i} className="space-y-2">
              <p className="ml-auto w-fit max-w-[90%] rounded-2xl rounded-br-sm bg-neutral-900 px-3.5 py-2 text-sm text-white">
                {ex.question}
              </p>
              <div className="max-w-[95%] rounded-2xl rounded-bl-sm border border-neutral-200 bg-white px-3.5 py-2.5 text-sm leading-relaxed text-neutral-800">
                <p className="whitespace-pre-line">{renderCitedAnswer(ex.answer, ex.sources)}</p>
                {ex.sources.length > 0 && (
                  <ol className="mt-2 space-y-0.5 border-t border-neutral-100 pt-2 text-xs text-neutral-500">
                    {ex.sources.map((s, n) => (
                      <li key={s.key} className="flex gap-1.5">
                        <span className="font-semibold text-blue-800">{n + 1}</span>
                        <a
                          href={s.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="truncate underline decoration-neutral-300 hover:text-neutral-900"
                        >
                          {s.title}
                        </a>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {pending && (
        <div className="mt-4 space-y-2">
          <p className="ml-auto w-fit max-w-[90%] rounded-2xl rounded-br-sm bg-neutral-900 px-3.5 py-2 text-sm text-white">
            {pending}
          </p>
          <p className="w-fit animate-pulse rounded-2xl rounded-bl-sm border border-neutral-200 bg-white px-3.5 py-2 text-sm text-neutral-400">
            …
          </p>
        </div>
      )}

      {exchanges.length === 0 && !pending && (
        <div className="mt-4 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => ask(s)}
              className="rounded-full border border-blue-200 bg-white px-3 py-1.5 text-left text-xs text-blue-900 transition hover:border-blue-400"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end"
      >
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              ask(question);
            }
          }}
          rows={2}
          maxLength={500}
          placeholder={t("ask_placeholder")}
          className="min-w-0 flex-1 resize-none rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-900 focus:outline-none"
        />
        <button
          type="submit"
          disabled={question.trim().length < 3 || pending !== null}
          className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
        >
          {t("ask_button")}
        </button>
      </form>
    </div>
  );
}
