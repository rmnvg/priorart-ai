"use client";

import { useEffect, useRef, useState } from "react";
import ExamplesGallery from "@/components/ExamplesGallery";
import IdeaForm from "@/components/IdeaForm";
import ProgressChecklist from "@/components/ProgressChecklist";
import ResultsView, { type AppliedSuggestion } from "@/components/ResultsView";
import { fetchLiveMode, fetchReport, streamAnalysis } from "@/lib/analyzeStream";
import type { AnalysisResult, AnalyzeRequest, PipelineStage } from "@/types/analysis";

type ViewState = "idle" | "loading" | "results" | "error";

// Keeps the address bar pointing at the current report, so the URL a user
// copies (or bookmarks) always reopens what they're looking at.
function setReportInUrl(reportId: string | null) {
  const url = new URL(window.location.href);
  if (reportId) url.searchParams.set("report", reportId);
  else url.searchParams.delete("report");
  window.history.replaceState(null, "", url);
}

export default function Home() {
  const [viewState, setViewState] = useState<ViewState>("idle");
  const [currentStage, setCurrentStage] = useState<PipelineStage | null>(null);
  const [stageMessage, setStageMessage] = useState<string | null>(null);
  const [live, setLive] = useState<boolean | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [previousConfidence, setPreviousConfidence] = useState<number | null>(null);
  const [appliedSuggestion, setAppliedSuggestion] = useState<string | null>(null);
  const [openingReport, setOpeningReport] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  function openReport(reportId: string) {
    setViewState("loading");
    setOpeningReport(true);
    setPreviousConfidence(null);
    setAppliedSuggestion(null);
    fetchReport(reportId)
      .then((report) => {
        if (report) {
          setResult(report);
          setViewState("results");
          setReportInUrl(reportId);
          window.scrollTo(0, 0);
        } else {
          setErrorMessage("That report link has expired or doesn't exist. Run a new analysis instead.");
          setViewState("error");
          setReportInUrl(null);
        }
      })
      .catch(() => {
        setErrorMessage("Couldn't reach the analysis server. Is the backend running?");
        setViewState("error");
      })
      .finally(() => setOpeningReport(false));
  }

  // A shared report link (?report=<id>) opens straight onto that saved
  // analysis. Read from window rather than useSearchParams, which would
  // force a Suspense boundary around the whole page for one mount-time read.
  useEffect(() => {
    fetchLiveMode().then(setLive);
    const reportId = new URLSearchParams(window.location.search).get("report");
    if (reportId) openReport(reportId);
  }, []);

  async function runAnalysis(request: AnalyzeRequest) {
    setViewState("loading");
    setCurrentStage(null);
    setStageMessage(null);
    setResult(null);
    setErrorMessage(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamAnalysis(
        request,
        (event) => {
          if (event.type === "progress") {
            setCurrentStage(event.stage);
            setStageMessage(event.message);
          } else if (event.type === "result") {
            setResult(event.data);
            setViewState("results");
            setReportInUrl(event.data.report_id ?? null);
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
    runAnalysis({ idea_text: ideaText });
  }

  function handleApplySuggestion({ english, shown }: AppliedSuggestion) {
    if (!result) return;
    setPreviousConfidence(result.overall_novelty_confidence);
    setAppliedSuggestion(shown);
    // The pipeline always gets English (the report's idea_text already is);
    // the language pin keeps the re-checked report in the reader's language.
    runAnalysis({
      idea_text: `${result.idea_text} Additionally, ${english}`,
      language: result.language_code && result.language_code !== "en" ? result.language_code : undefined,
      parent_report_id: result.report_id ?? undefined,
    });
  }

  function handleReset() {
    abortRef.current?.abort();
    setReportInUrl(null);
    setViewState("idle");
    setCurrentStage(null);
    setStageMessage(null);
    setResult(null);
    setErrorMessage(null);
    setPreviousConfidence(null);
    setAppliedSuggestion(null);
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10 bg-neutral-50 px-4 py-8 sm:py-16">
      {viewState === "idle" && (
        <>
          <IdeaForm onSubmit={handleSubmit} live={live} />
          <ExamplesGallery onOpen={openReport} />
        </>
      )}

      {viewState === "loading" && openingReport && (
        <p className="text-neutral-500">Opening saved report...</p>
      )}

      {viewState === "loading" && !openingReport && (
        <div className="flex flex-col items-center gap-8">
          <p className="text-neutral-500">
            {appliedSuggestion ? "Re-checking your idea..." : "Analyzing your idea..."}
          </p>
          <ProgressChecklist currentStage={currentStage} isComplete={false} message={stageMessage} />
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
          <div className="mx-auto mb-6 flex w-full max-w-3xl justify-end print:hidden">
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
