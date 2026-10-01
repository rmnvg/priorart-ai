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
    python -m benchmark.run --split heldout  # only the held-out cases

Cases are split into "development" (available while the search was built and
tuned) and "heldout" (written afterwards, never used for tuning, some in
Hindi). The report gives each split its own figures — a held-out number is
the one to quote.

Cost: 3 google_patents searches per case, plus REFINEMENT_QUERIES (default
1). No details/market/Trends calls — recall only needs the search half.
Non-English cases also make one LLM translation call, exactly as the app does.
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
from typing import Literal

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
    split: Literal["development", "heldout"] = "development"
    language: str = "en"


# "exact": the target's own publication number (any kind code).
# "family": a different publication with the identical title — usually the
# same invention filed elsewhere or continued, but not verified to be, so
# it's reported separately and never folded into the exact figures.
MatchKind = Literal["exact", "family"]


class CaseResult(BaseModel):
    id: str
    patent: str
    rank_before: int | None  # 1-based among patents + papers; None = not found
    rank_after: int | None
    match_before: MatchKind | None = None
    match_after: MatchKind | None = None
    seconds: float = 0.0
    results_before: int
    results_after: int
    refined_queries: list[str] = []
    refinement_observation: str | None = None
    queries: list[str] = []
    searches_used: int
    error: str | None = None
    split: str = "development"
    translated_idea: str | None = None  # the English the search ran on, when translated


def load_cases() -> list[Case]:
    return [Case(**c) for c in json.loads(CASES_PATH.read_text())["cases"]]


def _base_number(publication: str) -> str:
    # "US5960411A" -> "US5960411"; kind codes differ between family members
    # and publication stages, the number is what identifies the invention.
    match = re.match(r"([A-Z]{2}\d+)", publication)
    return match.group(1) if match else publication


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def find_rank(ranked, case: Case) -> tuple[int | None, MatchKind | None]:
    """1-based position of the target among patent/scholar results, and how
    it matched. An exact publication match anywhere wins over a same-title
    match higher up, so "exact" figures are never inflated by a lookalike."""
    number = re.compile(rf"patent/{re.escape(_base_number(case.patent))}[A-Z]")
    title = _normalize_title(case.patent_title)
    documents = [r for r in ranked if r.source_type in ("patent", "scholar")]
    for position, r in enumerate(documents, start=1):
        if number.search(r.id):
            return position, "exact"
    for position, r in enumerate(documents, start=1):
        if r.source_type == "patent" and _normalize_title(r.title) == title and len(title) > 12:
            return position, "family"
    return None, None


def run_case(case: Case) -> CaseResult:
    # Imported here so --dry-run works without the ML/LLM stack or keys.
    from app.config import REFINEMENT_QUERIES
    from app.pipeline.language import detect_and_translate
    from app.pipeline.query_generator import generate_queries
    from app.pipeline.rank import rank_and_dedupe
    from app.pipeline.refine import plan_refinement
    from app.pipeline.search import SearchLayerResult, run_queries

    # Same first step as the app: everything downstream runs on English.
    idea = detect_and_translate(case.idea).english_text
    translated = idea if idea != case.idea else None
    query_result = generate_queries(idea)
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
            split=case.split,
            translated_idea=translated,
        )

    ranked = rank_and_dedupe(SearchLayerResult(query_bundles=bundles, market_results=[]), idea)
    rank_before, match_before = find_rank(ranked, case)
    results_before = len(ranked)

    plan = plan_refinement(idea, query_result, ranked, REFINEMENT_QUERIES)
    if plan:
        refined = run_queries(plan.queries)
        searches += len(refined)
        bundles += refined
        ranked = rank_and_dedupe(
            SearchLayerResult(query_bundles=bundles, market_results=[]), idea
        )

    rank_after, match_after = find_rank(ranked, case)
    return CaseResult(
        id=case.id,
        patent=case.patent,
        rank_before=rank_before,
        rank_after=rank_after,
        match_before=match_before,
        match_after=match_after,
        results_before=results_before,
        results_after=len(ranked),
        refined_queries=[q.query for q in plan.queries] if plan else [],
        refinement_observation=plan.observation if plan else None,
        queries=[b.query for b in bundles],
        searches_used=searches,
        split=case.split,
        translated_idea=translated,
    )


def _hit(rank: int | None, k: int) -> bool:
    return rank is not None and rank <= k


def summarize(results: list[CaseResult]) -> dict:
    scored = [r for r in results if r.error is None]
    n = len(scored)

    def rate(phase: str, k: int | None, exact_only: bool = False) -> float:
        if not n:
            return 0.0
        hits = 0
        for r in scored:
            rank, kind = getattr(r, f"rank_{phase}"), getattr(r, f"match_{phase}")
            if exact_only and kind != "exact":
                continue
            hits += rank is not None if k is None else _hit(rank, k)
        return hits / n

    def worse(r: CaseResult) -> bool:
        # Refinement re-ranks everything, so it can push the target down.
        if r.rank_before is None:
            return False
        return r.rank_after is None or r.rank_after > r.rank_before

    return {
        "cases": n,
        "errors": len(results) - n,
        "top1_before": rate("before", 1),
        "top10_before": rate("before", TOP_K),
        "found_before": rate("before", None),
        "top1_after": rate("after", 1),
        "top10_after": rate("after", TOP_K),
        "found_after": rate("after", None),
        "top10_exact_before": rate("before", TOP_K, exact_only=True),
        "top10_exact_after": rate("after", TOP_K, exact_only=True),
        "refinement_improved": sum(
            1 for r in scored
            if r.rank_after is not None and (r.rank_before is None or r.rank_after < r.rank_before)
        ),
        "refinement_worsened": sum(1 for r in scored if worse(r)),
        "searches_used": sum(r.searches_used for r in results),
        "median_seconds": sorted(r.seconds for r in scored)[n // 2] if n else 0.0,
        "total_seconds": round(sum(r.seconds for r in results), 1),
    }


def _worsened(r: CaseResult) -> bool:
    return r.rank_before is not None and (r.rank_after is None or r.rank_after > r.rank_before)


def _summary_table(summary: dict) -> list[str]:
    def pct(x: float) -> str:
        return f"{round(x * 100)}%"

    return [
        "| | Top 1 | Top 10 | Top 10, exact publication only | Anywhere in results |",
        "|---|---|---|---|---|",
        f"| First search round | {pct(summary['top1_before'])} | {pct(summary['top10_before'])} "
        f"| {pct(summary['top10_exact_before'])} | {pct(summary['found_before'])} |",
        f"| After refinement agent | {pct(summary['top1_after'])} | {pct(summary['top10_after'])} "
        f"| {pct(summary['top10_exact_after'])} | {pct(summary['found_after'])} |",
        "",
        f"{summary['cases']} case(s) scored, {summary['errors']} error(s). Refinement moved the "
        f"target up in {summary['refinement_improved']} case(s) and down (or out) in "
        f"{summary['refinement_worsened']}. {summary['searches_used']} SerpApi searches; "
        f"{summary['total_seconds']:.0f}s in total, median {summary['median_seconds']:.0f}s per case.",
    ]


def render_markdown(cases: dict[str, Case], results: list[CaseResult], summary: dict) -> str:
    def rank(r: int | None, kind: str | None) -> str:
        if r is None:
            return "—"
        return f"#{r}" + (" (family)" if kind == "family" else "")

    lines = [
        "# Search-recall benchmark",
        "",
        f"_Run {datetime.now().strftime('%Y-%m-%d %H:%M')} · {summary['cases']} cases · "
        f"{summary['searches_used']} SerpApi searches attempted_",
        "",
        "Given only a plain description of a real, granted invention, how often does the search "
        "surface the actual patent? The held-out cases were written after the search was tuned "
        "and include Hindi descriptions; quote those figures, not the development ones.",
        "",
    ]
    for split, title in (("heldout", "Held-out cases"), ("development", "Development cases")):
        subset = [r for r in results if r.split == split]
        if subset:
            lines += [f"## {title}", ""] + _summary_table(summarize(subset)) + [""]
    lines += ["## All cases", ""] + _summary_table(summary) + [""]

    lines += [
        "## Per case",
        "",
        "| Case | Split | Patent | Rank before | Rank after | Seconds | Searches |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        case = cases[r.id]
        lines.append(
            f"| {r.id} | {r.split} | [{case.patent}](https://patents.google.com/patent/{case.patent}/en) "
            f"{case.patent_title} | {rank(r.rank_before, r.match_before)} | "
            f"{rank(r.rank_after, r.match_after)} | {r.seconds:.0f} | {r.searches_used} |"
        )

    worsened = [r for r in results if r.error is None and _worsened(r)]
    if worsened:
        lines += ["", "## Where refinement made it worse", ""]
        for r in worsened:
            lines.append(
                f"- **{r.id}**: {rank(r.rank_before, r.match_before)} → "
                f"{rank(r.rank_after, r.match_after)}. Refined query: "
                f"`{r.refined_queries[0] if r.refined_queries else '—'}`. "
                f"Agent's reasoning: {r.refinement_observation or '—'}"
            )

    missed = [r for r in results if r.error is None and not _hit(r.rank_after, TOP_K)]
    errored = [r for r in results if r.error]
    if missed or errored:
        lines += ["", f"## Failures (target not in the top {TOP_K})", ""]
        for r in missed:
            case = cases[r.id]
            where = f"ranked {rank(r.rank_after, r.match_after)}" if r.rank_after else "not returned at all"
            lines.append(f"### {r.id} — {where}")
            lines.append("")
            lines.append(f"- Description: {case.idea}")
            if r.translated_idea:
                lines.append(f"- Translated for the search: {r.translated_idea}")
            lines.append("- Queries run: " + "; ".join(f"`{q}`" for q in r.queries))
            if r.refinement_observation:
                lines.append(f"- Refinement agent noticed: {r.refinement_observation}")
            lines.append(
                f"- Results returned: {r.results_after}. "
                + (
                    "The patent was found but ranked below results whose wording sits closer to "
                    "the description."
                    if r.rank_after
                    else "None of the queries used vocabulary that retrieves this patent."
                )
            )
            lines.append("")
        for r in errored:
            lines.append(f"- **{r.id}**: not scored — {r.error}")

    lines += [
        "",
        "Ranks count patents and papers only (the full app also lists products). A match is the "
        "exact publication (any kind code); \"(family)\" marks a different publication with the "
        "identical title, which is likely but not verified to be the same invention. This "
        "measures retrieval, not the legal accuracy of any verdict.",
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
    parser.add_argument(
        "--split", choices=["development", "heldout"], help="run only one split (default: both)"
    )
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
    if args.split:
        selected = [c for c in selected if c.split == args.split]

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
            print(f"  {c.id:22} {c.split:11} {c.patent:14} {c.patent_title}")
        return 0

    results = list(previous)
    for i, case in enumerate(selected, start=1):
        started = time.time()
        try:
            result = run_case(case)
            result.seconds = round(time.time() - started, 1)
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
                split=case.split,
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
