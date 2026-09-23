"""Pydantic models for the /analyze SSE stream — mirrors
frontend/types/analysis.ts. Keep the two in sync.
"""
from typing import Literal

from pydantic import BaseModel

from app.pipeline.citation_chase import CitationNetwork
from app.pipeline.india_status import IndiaStatus
from app.pipeline.language import LocalizedContent
from app.pipeline.market_trends import MarketTrend
from app.pipeline.novelty import CandidateAssessment, Citation, ClaimChartPair
from app.pipeline.public_domain import PublicDomainSummary
from app.pipeline.rank import RankedResult
from app.pipeline.search import AssigneeStat

PipelineStage = Literal[
    "generating_queries",
    "searching_patents",
    "searching_scholar",
    "checking_market_availability",
    "ranking_results",
    "refining_search",
    "scoring_novelty",
    "done",
]


class ProgressEvent(BaseModel):
    type: Literal["progress"] = "progress"
    stage: PipelineStage
    message: str


class ClaimChart(BaseModel):
    candidate_result_id: str
    candidate_title: str
    candidate_link: str
    candidate_text: str
    pairs: list[ClaimChartPair]


class SearchQueryInfo(BaseModel):
    type: str
    query: str
    rationale: str
    country: str | None = None
    result_count: int
    failed: bool = False


class SearchStrategy(BaseModel):
    """How the report was built — the exact queries and every SerpApi call
    behind it, so a user can audit the search or pick it up themselves."""
    core_concepts: list[str]
    suggested_cpc: str | None = None
    queries: list[SearchQueryInfo]
    market_query: str
    trends_keyword: str | None = None
    serpapi_calls: dict[str, int]
    # What the refinement agent noticed in the first round, and the
    # patent vocabulary it searched again with.
    refinement_observation: str | None = None
    refinement_terms: list[str] = []


class AnalysisResult(BaseModel):
    idea_text: str
    ranked_results: list[RankedResult]
    candidate_assessments: list[CandidateAssessment]
    overall_novelty_confidence: float
    differentiation_suggestions: list[str]
    citations: list[Citation]
    india_status: IndiaStatus
    claim_chart: ClaimChart | None = None
    top_assignees: list[AssigneeStat] = []
    public_domain: PublicDomainSummary | None = None
    # Everything below was added after the first cached demo runs, so each
    # has a default — older cache files still validate and simply render
    # without those sections.
    search_strategy: SearchStrategy | None = None
    citation_network: CitationNetwork | None = None
    market_trend: MarketTrend | None = None
    # Written for the inventor in plain language (English source).
    plain_summary: str = ""
    # Language support: idea_text above is always the English the pipeline
    # ran on; the inventor's own words are kept here when they differed.
    original_idea_text: str | None = None
    language_code: str = "en"
    language_name: str = "English"
    localized: LocalizedContent | None = None
    # Set by the API layer (it's the cache key), not the pipeline.
    report_id: str | None = None


class ResultEvent(BaseModel):
    type: Literal["result"] = "result"
    data: AnalysisResult


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


AnalyzeStreamEvent = ProgressEvent | ResultEvent | ErrorEvent
