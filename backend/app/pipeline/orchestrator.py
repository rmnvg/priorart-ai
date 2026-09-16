"""Stage 1.7: wires stages 1.1-1.6 into a single async generator that yields
progress events as it goes, ending with either a result or an error event.
This is what the FastAPI SSE endpoint (section 2) will consume directly —
the staging lives here, not bolted on in the API layer.

Each blocking pipeline call is run via asyncio.to_thread so the event loop
stays free to flush progress events promptly.
"""
import asyncio
from collections.abc import AsyncGenerator

from app.models import AnalysisResult, AnalyzeStreamEvent, ErrorEvent, ProgressEvent, ResultEvent
from app.pipeline.deepdive import deep_dive
from app.pipeline.india_status import compute_india_status
from app.pipeline.novelty import assess_novelty
from app.pipeline.query_generator import generate_queries
from app.pipeline.rank import rank_and_dedupe
from app.pipeline.search import SearchLayerResult, run_market_search, run_patent_scholar_search

MIN_IDEA_LENGTH = 10
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

        result = AnalysisResult(
            idea_text=idea_text,
            ranked_results=ranked,
            candidate_assessments=novelty_result.candidate_assessments,
            overall_novelty_confidence=novelty_result.overall_novelty_confidence,
            differentiation_suggestions=novelty_result.differentiation_suggestions,
            citations=novelty_result.citations,
            india_status=india_status,
        )

        yield ProgressEvent(stage="done", message="Analysis complete.")
        yield ResultEvent(data=result)

    except Exception as e:
        yield ErrorEvent(message=f"Something went wrong while analyzing your idea: {e}")
