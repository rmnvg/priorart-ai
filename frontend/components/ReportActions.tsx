"use client";

import { useState } from "react";
import { buildReportBrief, downloadTextFile } from "@/lib/reportBrief";
import type { AnalysisResult } from "@/types/analysis";

function reportUrl(reportId: string | null | undefined): string | undefined {
  if (!reportId) return undefined;
  const url = new URL(window.location.origin + window.location.pathname);
  url.searchParams.set("report", reportId);
  return url.toString();
}

const BUTTON =
  "rounded-lg border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 shadow-sm transition hover:bg-neutral-50";

export default function ReportActions({ result }: { result: AnalysisResult }) {
  const [copied, setCopied] = useState(false);

  async function copyLink() {
    const url = reportUrl(result.report_id);
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can be blocked (insecure origin, permissions) — the link
      // is still in the address bar, so there's nothing useful to add.
    }
  }

  function downloadBrief() {
    downloadTextFile(
      `prior-art-brief-${result.report_id ?? "report"}.md`,
      buildReportBrief(result, reportUrl(result.report_id)),
      "text/markdown"
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 print:hidden">
      {result.report_id && (
        <button onClick={copyLink} className={BUTTON}>
          {copied ? "Link copied ✓" : "Copy share link"}
        </button>
      )}
      <button onClick={downloadBrief} className={BUTTON}>
        Download attorney brief
      </button>
      <button onClick={() => window.print()} className={BUTTON}>
        Print / save PDF
      </button>
    </div>
  );
}
