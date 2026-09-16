"""Stage 1.7: wires stages 1.1-1.6 into a single async generator that yields
progress events as it goes, ending with either a result or an error event.
This is what the FastAPI SSE endpoint (section 2) will consume directly —
the staging lives here, not bolted on in the API layer.

Each blocking pipeline call is run via asyncio.to_thread so the event loop
stays free to flush progress events promptly.
"""
import asyncio
import logging
from collections.abc import AsyncGenerator

from app.models import (
    AnalysisResult,
    AnalyzeStreamEvent,
    ClaimChart,
    ErrorEvent,
    ProgressEvent,
    ResultEvent,
)
from app.pipeline.deepdive import deep_dive
from app.pipeline.india_status import compute_india_status
from app.pipeline.novelty import assess_novelty
from app.pipeline.query_generator import generate_queries
from app.pipeline.rank import rank_and_dedupe
from app.pipeline.search import SearchLayerResult, run_market_search, run_patent_scholar_search

logger = logging.getLogger(__name__)

MIN_IDEA_LENGTH = 10
MAX_IDEA_LENGTH = 6000  # generous multi-paragraph allowance; guards against pathological pastes
DEEP_DIVE_TOP_N = 8
MARKET_CONTEXT_TOP_N = 3


async def run_pipeline(idea_text: str) -> AsyncGenerator[AnalyzeStreamEvent, None]:
    idea_text = (idea_text or "").strip()
    if len(idea_text) < MIN_IDEA_LENGTH:
        yield ErrorEvent(
            message="Please provide a more detailed description of your idea "
            "(at least a sentence or two)."
        )
        return
    if len(idea_text) > MAX_IDEA_LENGTH:
        idea_text = idea_text[:MAX_IDEA_LENGTH]

    try:
        yield ProgressEvent(
            stage="generating_queries",
            message="Extracting core concepts and generating search queries...",
        )
        query_result = await asyncio.to_thread(generate_queries, idea_text)

        yield ProgressEvent(
            stage="searching_patents",
            message=f"Searching patents across {len(query_result.queries)} query angles...",
        )
        bundles = await asyncio.to_thread(run_patent_scholar_search, query_result)
        # The major_markets query is the most precisely-targeted one, so its
        # assignee breakdown (from SerpApi's clustered=true summary — no
        # extra API call) is the most meaningful "who owns this space" view.
        major_markets_bundle = next((b for b in bundles if b.query_type == "major_markets"), None)
        top_assignees = major_markets_bundle.assignee_stats if major_markets_bundle else []

        yield ProgressEvent(
            stage="searching_scholar",
            message="Reviewing academic literature matches...",
        )
        # Scholar results arrive bundled with patent results from the same
        # google_patents call above — this stage is a UI checkpoint, not a
        # separate network call.

        yield ProgressEvent(
            stage="checking_market_availability",
            message="Checking whether a similar product already exists commercially...",
        )
        market_results = await asyncio.to_thread(run_market_search, query_result)
        search_result = SearchLayerResult(query_bundles=bundles, market_results=market_results)

        yield ProgressEvent(
            stage="ranking_results",
            message="Ranking and deduplicating results by relevance to your idea...",
        )
        ranked = await asyncio.to_thread(rank_and_dedupe, search_result, idea_text)

        if not ranked:
            # Distinguish "the search worked and found nothing" from "the
            # search never ran" (quota exhausted, network, auth). Telling a
            # user to reword their idea when the provider is down sends them
            # chasing a problem that isn't theirs.
            if bundles and all(b.search_failed for b in bundles):
                logger.error("All patent searches failed — provider unavailable or out of quota")
                yield ErrorEvent(
                    message="The patent search service is currently unavailable — this is a "
                    "problem on our side, not with your idea. Please try again shortly."
                )
            else:
                yield ErrorEvent(
                    message="No related patents, papers, or products were found for this idea. "
                    "Try describing it with more specific technical detail."
                )
            return

        yield ProgressEvent(
            stage="scoring_novelty",
            message="Pulling full claims for top candidates and scoring novelty...",
        )
        top_candidates = await asyncio.to_thread(deep_dive, ranked, DEEP_DIVE_TOP_N)
        top_products = [r for r in ranked if r.source_type == "product"][:MARKET_CONTEXT_TOP_N]
        novelty_result = await asyncio.to_thread(
            assess_novelty, idea_text, top_candidates, top_products
        )
        india_status = compute_india_status(ranked, DEEP_DIVE_TOP_N)

        # The claim chart always compares against the top deep-dived
        # candidate (the closest match) — the novelty prompt was instructed
        # to target that same candidate, so no id resolution is needed here.
        claim_chart = None
        if top_candidates and novelty_result.claim_chart_pairs:
            top = top_candidates[0]
            claim_chart = ClaimChart(
                candidate_result_id=top.id,
                candidate_title=top.title,
                candidate_link=top.link,
                candidate_text=top.summary_text,
                pairs=novelty_result.claim_chart_pairs,
            )

        result = AnalysisResult(
            idea_text=idea_text,
            ranked_results=ranked,
            candidate_assessments=novelty_result.candidate_assessments,
            overall_novelty_confidence=novelty_result.overall_novelty_confidence,
            differentiation_suggestions=novelty_result.differentiation_suggestions,
            citations=novelty_result.citations,
            india_status=india_status,
            claim_chart=claim_chart,
            top_assignees=top_assignees,
        )

        yield ProgressEvent(stage="done", message="Analysis complete.")
        yield ResultEvent(data=result)

    except Exception as e:
        # Never echo the raw exception to the client: SerpApi's own errors
        # embed the API key in the request URL (it's a query param), and any
        # future code path that reaches this top-level handler unwrapped
        # would otherwise leak it into a user-visible message. Log server-side,
        # show a generic message.
        logger.exception("Pipeline failed for idea_text=%r", idea_text)
        yield ErrorEvent(
            message="Something went wrong while analyzing your idea. Please try again "
            "in a moment — if it keeps happening, the search or AI provider may be "
            "temporarily unavailable."
        )
