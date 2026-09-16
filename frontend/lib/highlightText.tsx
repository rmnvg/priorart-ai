import type { ReactNode } from "react";

// LLMs frequently "prettify" text they're asked to copy verbatim — swapping a
// plain hyphen for a Unicode non-breaking hyphen, straight quotes for curly
// ones, etc. — even when explicitly told not to. That silently breaks exact
// substring matching for highlighting. Every substitution here is one
// character for one character, so a match found in the normalized string
// maps to the same offsets in the original — we highlight the original text,
// never the normalized copy.
const PUNCTUATION_LOOKALIKES: Record<string, string> = {
  "‐": "-", // hyphen
  "‑": "-", // non-breaking hyphen
  "‒": "-", // figure dash
  "–": "-", // en dash
  "—": "-", // em dash
  "‘": "'", // left single quote
  "’": "'", // right single quote / apostrophe
  "“": '"', // left double quote
  "”": '"', // right double quote
  " ": " ", // non-breaking space
};

function normalize(text: string): string {
  let out = "";
  for (const ch of text) out += PUNCTUATION_LOOKALIKES[ch] ?? ch;
  return out.toLowerCase();
}

/** Whether `span` can be found as a punctuation-normalized, case-insensitive
 * substring of `text`. Used to decide whether a pair is highlight-worthy
 * before committing to it on either side — see findableSpans below. */
export function isSpanFindable(text: string, span: string): boolean {
  if (!span.trim()) return false;
  return normalize(text).includes(normalize(span));
}

export interface HighlightSpan {
  text: string;
  color: string;
  key: string;
}

/** Finds each span as a case-insensitive, punctuation-normalized substring of
 * `text` and wraps matches in a colored <mark>. Spans that can't be found are
 * silently skipped (no highlight), never thrown — LLM-sourced spans aren't
 * guaranteed to match. Overlapping matches: first span in the list wins. */
export function highlightSpans(text: string, spans: HighlightSpan[]): ReactNode[] {
  const normalizedText = normalize(text);
  const ranges: { start: number; end: number; color: string; key: string }[] = [];

  for (const span of spans) {
    if (!span.text.trim()) continue;
    const idx = normalizedText.indexOf(normalize(span.text));
    if (idx === -1) continue;
    const end = idx + span.text.length;
    const overlaps = ranges.some((r) => idx < r.end && end > r.start);
    if (!overlaps) ranges.push({ start: idx, end, color: span.color, key: span.key });
  }

  ranges.sort((a, b) => a.start - b.start);

  const nodes: ReactNode[] = [];
  let cursor = 0;
  for (const r of ranges) {
    if (r.start > cursor) nodes.push(text.slice(cursor, r.start));
    nodes.push(
      <mark key={r.key} style={{ backgroundColor: r.color }} className="rounded px-0.5">
        {text.slice(r.start, r.end)}
      </mark>
    );
    cursor = r.end;
  }
  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}
