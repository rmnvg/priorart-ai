"""Pydantic models for the /analyze SSE stream — mirrors
frontend/types/analysis.ts. Keep the two in sync.
"""
from typing import Literal

from pydantic import BaseModel

from app.pipeline.india_status import IndiaStatus
from app.pipeline.novelty import CandidateAssessment, Citation
from app.pipeline.rank import RankedResult

PipelineStage = Literal[
    "generating_queries",
    "searching_patents",
    "searching_scholar",
    "checking_market_availability",
    "ranking_results",
    "scoring_novelty",
    "done",
]


class ProgressEvent(BaseModel):
    type: Literal["progress"] = "progress"
    stage: PipelineStage
    message: str


class AnalysisResult(BaseModel):
    idea_text: str
    ranked_results: list[RankedResult]
    candidate_assessments: list[CandidateAssessment]
    overall_novelty_confidence: float
    differentiation_suggestions: list[str]
    citations: list[Citation]
    india_status: IndiaStatus


class ResultEvent(BaseModel):
    type: Literal["result"] = "result"
    data: AnalysisResult


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


AnalyzeStreamEvent = ProgressEvent | ResultEvent | ErrorEvent
