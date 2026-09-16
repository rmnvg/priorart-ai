"use client";

import { useRef, useState } from "react";
import IdeaForm from "@/components/IdeaForm";
import ProgressChecklist from "@/components/ProgressChecklist";
import ResultsView from "@/components/ResultsView";
import { streamAnalysis } from "@/lib/analyzeStream";
import type { AnalysisResult, PipelineStage } from "@/types/analysis";

type ViewState = "idle" | "loading" | "results" | "error";

export default function Home() {
  const [viewState, setViewState] = useState<ViewState>("idle");
  const [currentStage, setCurrentStage] = useState<PipelineStage | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [previousConfidence, setPreviousConfidence] = useState<number | null>(null);
  const [appliedSuggestion, setAppliedSuggestion] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function runAnalysis(ideaText: string) {
    setViewState("loading");
    setCurrentStage(null);
    setResult(null);
    setErrorMessage(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamAnalysis(
        ideaText,
        (event) => {
          if (event.type === "progress") {
            setCurrentStage(event.stage);
          } else if (event.type === "result") {
            setResult(event.data);
            setViewState("results");
          } else if (event.type === "error") {
            setErrorMessage(event.message);
            setViewState("error");
          }
        },
        controller.signal
      );
    } catch {
      setErrorMessage("Couldn't reach the analysis server. Is the backend running?");
      setViewState("error");
    }
  }

  function handleSubmit(ideaText: string) {
    setPreviousConfidence(null);
    setAppliedSuggestion(null);
    runAnalysis(ideaText);
  }

  function handleApplySuggestion(suggestion: string) {
    if (!result) return;
    setPreviousConfidence(result.overall_novelty_confidence);
    setAppliedSuggestion(suggestion);
    runAnalysis(`${result.idea_text} Additionally, ${suggestion}`);
  }

  function handleReset() {
    abortRef.current?.abort();
    setViewState("idle");
    setCurrentStage(null);
    setResult(null);
    setErrorMessage(null);
    setPreviousConfidence(null);
    setAppliedSuggestion(null);
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10 bg-neutral-50 px-4 py-16">
      {viewState === "idle" && <IdeaForm onSubmit={handleSubmit} />}

      {viewState === "loading" && (
        <div className="flex flex-col items-center gap-8">
          <p className="text-neutral-500">
            {appliedSuggestion ? "Re-checking your idea..." : "Analyzing your idea..."}
          </p>
          <ProgressChecklist currentStage={currentStage} isComplete={false} />
        </div>
      )}

      {viewState === "error" && (
        <div className="mx-auto w-full max-w-md rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-red-800">{errorMessage}</p>
          <button
            onClick={handleReset}
            className="mt-4 rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700"
          >
            Try again
          </button>
        </div>
      )}

      {viewState === "results" && result && (
        <div className="w-full">
          <div className="mx-auto mb-6 flex w-full max-w-3xl justify-end">
            <button
              onClick={handleReset}
              className="text-sm text-neutral-500 underline hover:text-neutral-900"
            >
              Analyze another idea
            </button>
          </div>
          <ResultsView
            result={result}
            onApplySuggestion={handleApplySuggestion}
            previousConfidence={previousConfidence}
            appliedSuggestion={appliedSuggestion}
          />
        </div>
      )}
    </main>
  );
}
