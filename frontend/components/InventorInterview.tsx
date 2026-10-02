"use client";

import { useEffect, useState } from "react";
import { fetchInterview } from "@/lib/analyzeStream";
import { interviewDescription, MAX_IDEA_LENGTH } from "@/lib/interview";
import type { InterviewPlan } from "@/types/analysis";

export default function InventorInterview({ idea, disabled, onSearch, onBack }: {
  idea: string;
  disabled?: boolean;
  onSearch: (text: string) => void;
  onBack: () => void;
}) {
  const [plan, setPlan] = useState<InterviewPlan | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [unknown, setUnknown] = useState<boolean[]>([]);
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetchInterview(idea, controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      setPlan(result);
      if (!result.questions.length) setDraft(idea);
    }).catch((e) => {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Couldn't prepare questions.");
    });
    return () => controller.abort();
  }, [idea, attempt]);

  const button = "rounded-lg border border-neutral-300 px-4 py-2 text-sm disabled:opacity-50";
  return (
    <section className="mt-7 rounded-xl border border-neutral-200 bg-white p-5 shadow-sm" aria-busy={!plan && !error}>
      <h2 className="text-xl font-semibold">Clarify your invention</h2>
      <p className="mt-2 text-sm text-neutral-600">Answer in your own language. Skip anything you don’t know. You’ll review the exact description before searching.</p>
      {!plan && !error && <p role="status" className="mt-4 text-sm">Checking which details would help the search…</p>}
      {error && <div className="mt-4 text-sm text-red-700" role="alert">
        <p>{error}</p>
        <button type="button" className="mt-2 underline" disabled={disabled} onClick={() => { setError(null); setAttempt(attempt + 1); }}>Retry questions</button>
      </div>}
      {plan && draft === null && <form className="mt-5 space-y-5" onSubmit={(e) => {
        e.preventDefault();
        setDraft(interviewDescription(idea, plan, answers.map((answer, i) => unknown[i] ? "" : answer)));
      }}>
        {plan.questions.map((q, index) => <div key={q.question}>
          <label htmlFor={`interview-${index}`} className="block font-medium">{index + 1}. {q.question}</label>
          <p id={`interview-help-${index}`} className="mt-1 text-sm text-neutral-500">{q.reason}</p>
          <textarea id={`interview-${index}`} aria-describedby={`interview-help-${index}`} rows={2} maxLength={1000}
            disabled={disabled || unknown[index]} value={answers[index] ?? ""}
            onChange={(e) => setAnswers((prev) => { const next = [...prev]; next[index] = e.target.value; return next; })}
            className="mt-2 w-full rounded-lg border border-neutral-300 p-3 disabled:bg-neutral-100" />
          <label className="mt-2 flex items-center gap-2 text-sm text-neutral-600">
            <input type="checkbox" checked={unknown[index] ?? false} disabled={disabled}
              onChange={(e) => setUnknown((prev) => { const next = [...prev]; next[index] = e.target.checked; return next; })} />
            I don’t know yet — leave this out of the search
          </label>
        </div>)}
        <button type="submit" disabled={disabled} className={`${button} bg-neutral-900 text-white`}>Review search description</button>
      </form>}
      {draft !== null && <div className="mt-5">
        {plan?.questions.length === 0 && <p className="mb-3 text-sm text-emerald-800">Your description has enough detail to start. No extra questions.</p>}
        <label htmlFor="interview-description" className="font-medium">Exact description to search</label>
        <p id="description-help" className="mt-1 text-sm text-neutral-500">Your original idea and the answers you supplied. Correct anything before continuing.</p>
        <textarea id="interview-description" aria-describedby="description-help" rows={8} value={draft} disabled={disabled}
          onChange={(e) => setDraft(e.target.value)} className="mt-2 w-full rounded-lg border border-neutral-300 p-3" />
        <p className={`text-xs ${draft.length > MAX_IDEA_LENGTH ? "text-red-700" : "text-neutral-500"}`}>{draft.length} / {MAX_IDEA_LENGTH} characters</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <button type="button" className={`${button} bg-neutral-900 text-white`} disabled={disabled || draft.trim().length < 10 || draft.length > MAX_IDEA_LENGTH} onClick={() => onSearch(draft.trim())}>Confirm & search</button>
          {!!plan?.questions.length && <button type="button" className={button} disabled={disabled} onClick={() => setDraft(null)}>Edit answers</button>}
        </div>
      </div>}
      <div className="mt-5 flex flex-wrap gap-4 border-t border-neutral-100 pt-4 text-sm">
        <button type="button" disabled={disabled} onClick={onBack} className="underline disabled:opacity-50">Back to my idea</button>
        <button type="button" disabled={disabled} onClick={() => onSearch(idea)} className="underline disabled:opacity-50">Skip questions & search original idea</button>
      </div>
    </section>
  );
}
