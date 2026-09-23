"""Search-recall benchmark: does PriorArt AI find a real patent from a plain
description of the invention?

Each case in cases.json is a granted patent plus a plain-English description
written the way an inventor would say it, avoiding the patent's own title
and claim wording. For each case this runs the pipeline's search half —
query generation, the country-filtered patent searches, embedding ranking,
and the refinement agent — and records where (if anywhere) the real patent
lands, before and after refinement. That before/after pair is the
measurement of what the refinement agent is worth.

Usage, from backend/:

    python -m benchmark.run --dry-run        # plan + SerpApi cost, no API calls
    python -m benchmark.run                  # all cases
    python -m benchmark.run --cases cat-laser,coffee-pod
    python -m benchmark.run --resume         # skip cases already in latest.json

Cost: 3 google_patents searches per case, plus REFINEMENT_QUERIES (default
1). No details/market/Trends calls — recall only needs the search half.
Results are written after every case, so an interrupted run (quota, network)
loses nothing: rerun with --resume.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

BENCHMARK_DIR = Path(__file__).resolve().parent
CASES_PATH = BENCHMARK_DIR / "cases.json"
RESULTS_DIR = BENCHMARK_DIR / "results"
LATEST_JSON = RESULTS_DIR / "latest.json"
LATEST_MD = RESULTS_DIR / "latest.md"

TOP_K = 10
PATENT_QUERIES_PER_CASE = 3


class Case(BaseModel):
    id: str
    patent: str
    patent_title: str
    priority_date: str
    idea: str


class CaseResult(BaseModel):
    id: str
    patent: str
    rank_before: int | None  # 1-based among patents + papers; None = not found
    rank_after: int | None
    results_before: int
    results_after: int
    refined_queries: list[str] = []
    refinement_observation: str | None = None
    queries: list[str] = []
    searches_used: int
    error: str | None = None


def load_cases() -> list[Case]:
    return [Case(**c) for c in json.loads(CASES_PATH.read_text())["cases"]]


def _base_number(publication: str) -> str:
    # "US5960411A" -> "US5960411"; kind codes differ between family members
    # and publication stages, the number is what identifies the invention.
    match = re.match(r"([A-Z]{2}\d+)", publication)
    return match.group(1) if match else publication


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def find_rank(ranked, case: Case) -> int | None:
    """1-based position of the target among patent/scholar results. Matches
    the exact publication (any kind code), or a same-titled patent — family
    members (continuations, foreign filings) usually share the title and
    describe the same invention."""
    number = re.compile(rf"patent/{re.escape(_base_number(case.patent))}[A-Z]")
    title = _normalize_title(case.patent_title)
    documents = [r for r in ranked if r.source_type in ("patent", "scholar")]
    for position, r in enumerate(documents, start=1):
        if number.search(r.id):
            return position
        if r.source_type == "patent" and _normalize_title(r.title) == title and len(title) > 12:
            return position
    return None


def run_case(case: Case) -> CaseResult:
    # Imported here so --dry-run works without the ML/LLM stack or keys.
    from app.config import REFINEMENT_QUERIES
    from app.pipeline.query_generator import generate_queries
    from app.pipeline.rank import rank_and_dedupe
    from app.pipeline.refine import plan_refinement
    from app.pipeline.search import SearchLayerResult, run_queries

    query_result = generate_queries(case.idea)
    bundles = run_queries(query_result.queries)
    searches = len(bundles)
    if all(b.search_failed for b in bundles):
        return CaseResult(
            id=case.id,
            patent=case.patent,
            rank_before=None,
            rank_after=None,
            results_before=0,
            results_after=0,
            queries=[b.query for b in bundles],
            searches_used=searches,
            error="all searches failed (quota or network)",
        )

    ranked = rank_and_dedupe(SearchLayerResult(query_bundles=bundles, market_results=[]), case.idea)
    rank_before = find_rank(ranked, case)
    results_before = len(ranked)

    plan = plan_refinement(case.idea, query_result, ranked, REFINEMENT_QUERIES)
    if plan:
        refined = run_queries(plan.queries)
        searches += len(refined)
        bundles += refined
        ranked = rank_and_dedupe(
            SearchLayerResult(query_bundles=bundles, market_results=[]), case.idea
        )

    return CaseResult(
        id=case.id,
        patent=case.patent,
        rank_before=rank_before,
        rank_after=find_rank(ranked, case),
        results_before=results_before,
        results_after=len(ranked),
        refined_queries=[q.query for q in plan.queries] if plan else [],
        refinement_observation=plan.observation if plan else None,
        queries=[b.query for b in bundles],
        searches_used=searches,
    )


def _hit(rank: int | None, k: int) -> bool:
    return rank is not None and rank <= k


def summarize(results: list[CaseResult]) -> dict:
    scored = [r for r in results if r.error is None]
    n = len(scored)

    def rate(key: str, k: int | None) -> float:
        if not n:
            return 0.0
        ranks = [getattr(r, key) for r in scored]
        return sum(1 for x in ranks if (x is not None if k is None else _hit(x, k))) / n

    return {
        "cases": n,
        "errors": len(results) - n,
        "top1_before": rate("rank_before", 1),
        "top10_before": rate("rank_before", TOP_K),
        "found_before": rate("rank_before", None),
        "top1_after": rate("rank_after", 1),
        "top10_after": rate("rank_after", TOP_K),
        "found_after": rate("rank_after", None),
        "searches_used": sum(r.searches_used for r in results),
    }


def render_markdown(cases: dict[str, Case], results: list[CaseResult], summary: dict) -> str:
    def pct(x: float) -> str:
        return f"{round(x * 100)}%"

    def rank(r: int | None) -> str:
        return f"#{r}" if r is not None else "—"

    lines = [
        "# Search-recall benchmark",
        "",
        f"_Run {datetime.now().strftime('%Y-%m-%d %H:%M')} · {summary['cases']} cases · "
        f"{summary['searches_used']} SerpApi searches attempted_",
        "",
        "Given only a plain-English description of a real, granted invention, how often does "
        "the search surface the actual patent?",
        "",
        "| | Top 1 | Top 10 | Anywhere in results |",
        "|---|---|---|---|",
        f"| First search round | {pct(summary['top1_before'])} | {pct(summary['top10_before'])} "
        f"| {pct(summary['found_before'])} |",
        f"| After refinement agent | {pct(summary['top1_after'])} | {pct(summary['top10_after'])} "
        f"| {pct(summary['found_after'])} |",
        "",
        "| Case | Patent | Rank before | Rank after | Refined query |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        case = cases[r.id]
        refined = f"`{r.refined_queries[0]}`" if r.refined_queries else "—"
        if r.error:
            refined = f"error: {r.error}"
        lines.append(
            f"| {r.id} | [{case.patent}](https://patents.google.com/patent/{case.patent}/en) "
            f"{case.patent_title} | {rank(r.rank_before)} | {rank(r.rank_after)} | {refined} |"
        )
    lines += [
        "",
        "Ranks count patents and papers only (the full app also lists products). A match is the "
        "exact publication (any kind code) or a same-titled family member.",
    ]
    return "\n".join(lines) + "\n"


def save(cases: dict[str, Case], results: list[CaseResult]) -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = summarize(results)
    LATEST_JSON.write_text(
        json.dumps(
            {"summary": summary, "results": [r.model_dump() for r in results]}, indent=2
        )
    )
    LATEST_MD.write_text(render_markdown(cases, results, summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cases", help="comma-separated case ids (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="print plan and cost only")
    parser.add_argument("--resume", action="store_true", help="skip cases already in latest.json")
    args = parser.parse_args()

    all_cases = load_cases()
    by_id = {c.id: c for c in all_cases}
    selected = all_cases
    if args.cases:
        wanted = [c.strip() for c in args.cases.split(",") if c.strip()]
        unknown = [w for w in wanted if w not in by_id]
        if unknown:
            print(f"Unknown case ids: {', '.join(unknown)}", file=sys.stderr)
            return 2
        selected = [by_id[w] for w in wanted]

    previous: list[CaseResult] = []
    if args.resume and LATEST_JSON.exists():
        previous = [CaseResult(**r) for r in json.loads(LATEST_JSON.read_text())["results"]]
        done = {r.id for r in previous if r.error is None}
        previous = [r for r in previous if r.id in done]
        selected = [c for c in selected if c.id not in done]

    from app.config import REFINEMENT_QUERIES

    per_case = PATENT_QUERIES_PER_CASE + REFINEMENT_QUERIES
    print(
        f"{len(selected)} case(s) to run, up to {per_case} SerpApi searches each "
        f"(~{len(selected) * per_case} total)."
    )
    if args.dry_run:
        for c in selected:
            print(f"  {c.id:22} {c.patent:14} {c.patent_title}")
        return 0

    results = list(previous)
    for i, case in enumerate(selected, start=1):
        started = time.time()
        try:
            result = run_case(case)
        except Exception as e:  # one bad case shouldn't lose the run
            result = CaseResult(
                id=case.id,
                patent=case.patent,
                rank_before=None,
                rank_after=None,
                results_before=0,
                results_after=0,
                searches_used=0,
                error=type(e).__name__,
            )
        results.append(result)
        save(by_id, results)
        status = result.error or f"before {result.rank_before or '—'} → after {result.rank_after or '—'}"
        print(f"[{i}/{len(selected)}] {case.id}: {status} ({time.time() - started:.0f}s)")
        if result.error and "quota" in result.error:
            print("Stopping: searches are failing. Rerun later with --resume.", file=sys.stderr)
            break

    summary = save(by_id, results)
    print(
        f"\nTop-10 recall: {summary['top10_before']:.0%} → {summary['top10_after']:.0%} "
        f"after refinement ({summary['cases']} cases). Report: {LATEST_MD}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
