import type { AnalysisResult } from "@/types/analysis";

// English source strings for the labels the backend localizes along with a
// report (keys match UI_LABELS in backend/app/pipeline/language.py). A
// report in English — or one cached before localization existed — simply
// uses these.
const ENGLISH_LABELS = {
  novelty_verdict: "Novelty verdict",
  looks_novel: "Looks novel",
  looks_novel_blurb: "No strong blocking prior art surfaced for this idea.",
  partial_overlap: "Partial overlap",
  partial_overlap_blurb:
    "Real prior art shares elements with this idea, but it isn't fully anticipated.",
  heavy_overlap: "Heavy overlap",
  heavy_overlap_blurb: "Close matches already exist — differentiation will be essential.",
  what_this_means: "What this means for you",
  differentiate_title: "How to differentiate your idea",
  differentiate_subtitle:
    "Specific changes that would move this idea away from its closest matches. Apply one to re-run the analysis and watch the verdict move.",
  apply_recheck: "Apply & re-check →",
  based_on: "Based on:",
  free_to_build: "Free to build on",
  india_signal: "India patentability signal",
  ask_title: "Ask about this report",
  ask_subtitle: "Answers come only from what this search found, with sources.",
  ask_placeholder: "Ask a question about your idea and this report...",
  ask_button: "Ask",
  ask_q1: "Which patent is the biggest risk for my idea, and why?",
  ask_q2: "Can I make and sell this in India?",
  ask_q3: "What can I build on freely without worrying about patents?",
} as const;

export type LabelKey = keyof typeof ENGLISH_LABELS;
export type Translate = (key: LabelKey) => string;

export const englishLabel: Translate = (key) => ENGLISH_LABELS[key];

/** Label lookup for a report, in its language unless `english` is set. */
export function labelsFor(result: AnalysisResult, english: boolean): Translate {
  const localized = english ? null : result.localized?.ui_labels;
  return (key) => localized?.[key] || ENGLISH_LABELS[key];
}
