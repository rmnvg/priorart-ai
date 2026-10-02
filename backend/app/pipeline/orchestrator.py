"""Stage 1.7: wires every stage into a single async generator that yields
progress events as it goes, ending with either a result or an error event.
This is what the FastAPI SSE endpoint (and the MCP server) consume directly —
the staging lives here, not bolted on in the API layer.

Each blocking pipeline call is run via asyncio.to_thread so the event loop
stays free to flush progress events promptly. The market and Trends lookups
depend only on the generated queries, so they're started alongside the patent
search and collected later rather than waited on in sequence.

Progress messages are written for the person watching: where a stage makes a
decision (the language it detected, the terminology the refinement agent
found), the message says what it decided, not just which stage is running.
"""
import asyncio
import logging
from collections.abc import AsyncGenerator

from app.config import CITATION_FOLLOWUPS, DEEP_DIVE_TOP_N, ENABLE_TRENDS, REFINEMENT_QUERIES
from app.models import (
    AnalysisResult,
    AnalyzeStreamEvent,
    ClaimChart,
    ErrorEvent,
    ExaminedDocument,
    ProgressEvent,
    ResultEvent,
    SearchQueryInfo,
    SearchStrategy,
)
from app.pipeline.citation_chase import chase_citations
from app.pipeline.citation_followup import (
    FollowUpOutcome,
    follow_up_citations,
    select_discoveries,
)
from app.pipeline.deepdive import deep_dive
from app.pipeline.india_status import compute_india_status
from app.pipeline.language import detect_and_translate, language_name_for, localize_report
from app.pipeline.market_trends import fetch_market_trend
from app.pipeline.novelty import assess_novelty
from app.pipeline.public_domain import find_public_domain
from app.pipeline.query_generator import GeneratedQuery, generate_queries
from app.pipeline.rank import rank_and_dedupe
from app.pipeline.recheck import compare_recheck
from app.pipeline.refine import plan_refinement
from app.pipeline.search import (
    QueryBundle,
    SearchLayerResult,
    build_market_query,
    run_market_search,
    run_queries,
)

logger = logging.getLogger(__name__)

MIN_IDEA_LENGTH = 10
MAX_IDEA_LENGTH = 6000  # generous multi-paragraph allowance; guards against pathological pastes
MARKET_CONTEXT_TOP_N = 3

# Language codes the report is never translated into: English needs no
# translation, and "und" means detection itself failed.
NO_LOCALIZATION = {"en", "und"}


def _count_serpapi_calls(
    patent_queries: int, deep_dives: int, used_trends: bool, followups: int = 0
) -> dict[str, int]:
    calls = {
        "google_patents": patent_queries,
        "google": 1,
        "google_patents_details": deep_dives + followups,
    }
    if used_trends:
        calls["google_trends"] = 1
    return calls


async def _noop() -> None:
    return None


async def run_pipeline(
    idea_text: str,
    language: str | None = None,
    parent: AnalysisResult | None = None,
    parent_report_id: str | None = None,
    applied_change: str | None = None,
) -> AsyncGenerator[AnalyzeStreamEvent, None]:
    """`language` forces the report language (ISO 639-1). Without it, the
    report comes back in whatever language the idea was written in.

    A re-check passes the report it revises (`parent`) and the change that
    was applied; the result then carries an evidence comparison against the
    parent's closest matches."""
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
        idea_language = await asyncio.to_thread(detect_and_translate, idea_text)
        translated = idea_language.code != "en" and idea_language.english_text != idea_text
        if translated:
            yield ProgressEvent(
                stage="generating_queries",
                message=f"Understood your idea in {idea_language.name} — translating it into "
                "patent-search English and extracting its core concepts...",
            )
        # Everything downstream (queries, embeddings, claim chart) runs on
        # English: that's the language of the patent corpus.
        english_idea = idea_language.english_text
        output_code = (language or idea_language.code).lower()
        output_name = (
            idea_language.name
            if output_code == idea_language.code
            else language_name_for(output_code)
        )

        query_result = await asyncio.to_thread(generate_queries, english_idea)

        yield ProgressEvent(
            stage="searching_patents",
            message=f"Searching patents across {len(query_result.queries)} query angles, "
            "including Indian Patent Office filings...",
        )
        market_task = asyncio.create_task(asyncio.to_thread(run_market_search, query_result))
        trend_task = asyncio.create_task(
            asyncio.to_thread(fetch_market_trend, query_result.trends_keyword)
            if ENABLE_TRENDS
            else _noop()
        )
        bundles: list[QueryBundle] = await asyncio.to_thread(run_queries, query_result.queries)
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
        market_results = await market_task
        market_trend = await trend_task

        yield ProgressEvent(
            stage="ranking_results",
            message="Ranking and deduplicating results by relevance to your idea...",
        )
        ranked = await asyncio.to_thread(
            rank_and_dedupe,
            SearchLayerResult(query_bundles=bundles, market_results=market_results),
            english_idea,
        )

        all_queries: list[GeneratedQuery] = list(query_result.queries)
        refinement = None
        # Skip refinement when the search provider itself is down: the
        # follow-up queries would fail the same way.
        if REFINEMENT_QUERIES > 0 and not all(b.search_failed for b in bundles):
            yield ProgressEvent(
                stage="refining_search",
                message="Reading the first results to learn the terminology patents use for "
                "this idea...",
            )
            refinement = await asyncio.to_thread(
                plan_refinement, english_idea, query_result, ranked, REFINEMENT_QUERIES
            )
            if refinement:
                yield ProgressEvent(stage="refining_search", message=refinement.observation)
                refined_bundles = await asyncio.to_thread(run_queries, refinement.queries)
                bundles = bundles + refined_bundles
                all_queries += refinement.queries
                ranked = await asyncio.to_thread(
                    rank_and_dedupe,
                    SearchLayerResult(query_bundles=bundles, market_results=market_results),
                    english_idea,
                )

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
            message="Pulling full claims and citations for top candidates and scoring novelty...",
        )
        top_candidates = await asyncio.to_thread(deep_dive, ranked, DEEP_DIVE_TOP_N)
        top_products = [r for r in ranked if r.source_type == "product"][:MARKET_CONTEXT_TOP_N]
        novelty_result = await asyncio.to_thread(
            assess_novelty, english_idea, top_candidates, top_products
        )
        india_status = compute_india_status(ranked, DEEP_DIVE_TOP_N)
        # Prior art whose protection has ended — free to build on, and the
        # most actionable part of the report for an independent inventor.
        public_domain = find_public_domain(ranked)
        citation_network = chase_citations(top_candidates, ranked)

        # Second investigation step: fetch the strongest citation discoveries
        # and assess them against the same features, so what citation chasing
        # finds can change the conclusion rather than just being listed.
        feature_findings = novelty_result.feature_findings
        candidate_assessments = list(novelty_result.candidate_assessments)
        followup = FollowUpOutcome()
        to_follow = select_discoveries(citation_network, CITATION_FOLLOWUPS)
        if to_follow and feature_findings:
            yield ProgressEvent(
                stage="scoring_novelty",
                message=f"Following up {len(to_follow)} document(s) the closest matches cite "
                "but the keyword search missed...",
            )
            followup = await asyncio.to_thread(
                follow_up_citations,
                english_idea,
                citation_network,
                feature_findings,
                CITATION_FOLLOWUPS,
            )
            candidate_assessments += followup.assessments
            feature_text = {f.id: f.feature for f in feature_findings}
            for f in followup.followups:
                if f.changed_conclusion:
                    yield ProgressEvent(
                        stage="scoring_novelty",
                        message=f"Citation follow-up changed the conclusion: \"{f.title}\" shows "
                        + "; ".join(feature_text[x] for x in f.newly_found)
                        + ", which no searched document did.",
                    )

        localized = None
        if output_code not in NO_LOCALIZATION:
            yield ProgressEvent(
                stage="scoring_novelty",
                message=f"Writing your report in {output_name}...",
            )
            localized = await asyncio.to_thread(
                localize_report,
                output_code,
                output_name,
                novelty_result.plain_summary,
                novelty_result.differentiation_suggestions,
                [c.claim for c in novelty_result.citations],
            )

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
            idea_text=english_idea,
            ranked_results=ranked,
            candidate_assessments=candidate_assessments,
            overall_novelty_confidence=novelty_result.overall_novelty_confidence,
            differentiation_suggestions=novelty_result.differentiation_suggestions,
            citations=novelty_result.citations,
            india_status=india_status,
            claim_chart=claim_chart,
            top_assignees=top_assignees,
            public_domain=public_domain,
            search_strategy=SearchStrategy(
                core_concepts=query_result.core_concepts,
                suggested_cpc=query_result.suggested_cpc,
                queries=[
                    SearchQueryInfo(
                        type=b.query_type,
                        query=b.query,
                        rationale=gq.rationale,
                        country=b.country,
                        result_count=len(b.results),
                        failed=b.search_failed,
                    )
                    for b, gq in zip(bundles, all_queries)
                ],
                market_query=build_market_query(query_result),
                trends_keyword=query_result.trends_keyword if ENABLE_TRENDS else None,
                serpapi_calls=_count_serpapi_calls(
                    len(bundles),
                    len(top_candidates),
                    ENABLE_TRENDS and bool(query_result.trends_keyword),
                    followup.lookups,
                ),
                refinement_observation=refinement.observation if refinement else None,
                refinement_terms=refinement.new_terms if refinement else [],
            ),
            citation_network=citation_network,
            examined_documents=[
                ExaminedDocument(
                    id=c.id,
                    source_type=c.source_type,
                    title=c.title,
                    link=c.link,
                    text=c.summary_text,
                    sections=c.sections,
                    total_claims=c.total_claims,
                    evidence_source=c.evidence_source,
                    found_via=found_via,
                )
                for c, found_via in [(c, "search") for c in top_candidates]
                + [(c, "citation") for c in followup.details]
            ],
            feature_findings=feature_findings,
            citation_followups=followup.followups,
            market_trend=market_trend,
            plain_summary=novelty_result.plain_summary,
            original_idea_text=idea_text if translated else None,
            # Reflects what the report actually contains: if localization
            # failed, it's English regardless of what was asked for.
            language_code=output_code if localized else "en",
            language_name=output_name if localized else "English",
            localized=localized,
        )

        if parent is not None and parent_report_id and applied_change:
            yield ProgressEvent(
                stage="scoring_novelty",
                message="Checking whether your change sets the idea apart from the original "
                "closest patents...",
            )
            result.recheck = await asyncio.to_thread(
                compare_recheck, parent, parent_report_id, result, applied_change
            )

        yield ProgressEvent(stage="done", message="Analysis complete.")
        yield ResultEvent(data=result)

    except Exception:
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
