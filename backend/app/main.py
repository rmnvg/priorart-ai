import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app import service
from app.cache import list_top_level_reports
from app.config import ALLOWED_ORIGINS, GROQ_API_KEY, LIVE_MODE
from app.models import AnalysisResult
from app.pipeline.ask import AskTurn, ReportAnswer, answer_question
from app.pipeline.examination import ExaminationPreview
from app.pipeline.rank import warm_up


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # The embedding model takes seconds to load; do it at startup so the
    # first analysis doesn't. Demo mode never ranks, so it skips the cost.
    if LIVE_MODE:
        await asyncio.to_thread(warm_up)
    yield


app = FastAPI(title="PriorArt AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    idea_text: str
    # Forces the report language (ISO 639-1). Omitted, the report follows
    # the language the idea is written in.
    language: str | None = None
    # Set when this run is a re-check of another report: which report, and
    # the change applied (English) — for the evidence comparison.
    parent_report_id: str | None = None
    applied_change: str | None = Field(default=None, max_length=1000)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    # Earlier turns, oldest first, so follow-ups ("and in India?") resolve.
    history: list[AskTurn] = Field(default=[], max_length=10)


class ExampleReport(BaseModel):
    report_id: str
    idea_text: str
    language_name: str
    novelty_confidence: float
    results_count: int
    public_domain_count: int


def _load_report(report_id: str) -> AnalysisResult:
    """A saved report by id, or 404."""
    report = service.load_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/health")
def health():
    return {"status": "ok", "live": LIVE_MODE}


@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    async def event_stream() -> AsyncGenerator[dict, None]:
        async for event in service.analyze(
            request.idea_text, request.language, request.parent_report_id, request.applied_change
        ):
            yield {"event": event.type, "data": event.model_dump_json()}

    return EventSourceResponse(event_stream())


@app.get("/report/{report_id}", response_model=AnalysisResult)
def get_report(report_id: str) -> AnalysisResult:
    """A saved analysis by id — what a shared report link loads. Serves only
    what's already cached; never triggers a (billable) pipeline run."""
    return _load_report(report_id)


@app.get("/examples", response_model=list[ExampleReport])
def list_examples() -> list[ExampleReport]:
    """Saved analyses for the examples gallery — what a judge or visitor
    sees without API keys. Re-checks of other reports are left out."""
    examples = []
    for report_id, event in list_top_level_reports():
        data = event.data
        examples.append(
            ExampleReport(
                report_id=report_id,
                idea_text=data.original_idea_text or data.idea_text,
                language_name=data.language_name,
                novelty_confidence=data.overall_novelty_confidence,
                results_count=len(data.ranked_results),
                public_domain_count=data.public_domain.count if data.public_domain else 0,
            )
        )
    return examples


@app.post("/report/{report_id}/ask", response_model=ReportAnswer)
async def ask_about_report(report_id: str, request: AskRequest) -> ReportAnswer:
    """A follow-up question answered from a saved report alone. Needs only
    the LLM key — no searches — so it works in demo mode when Groq is set."""
    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Questions need an LLM key: add GROQ_API_KEY to backend/.env.",
        )
    report = _load_report(report_id)
    try:
        return await asyncio.to_thread(answer_question, report, request.question, request.history)
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Couldn't answer that right now — try again or rephrase the question.",
        )



@app.post("/report/{report_id}/examination", response_model=ExaminationPreview)
async def examination_preview(report_id: str) -> ExaminationPreview:
    """How an Indian patent examiner might read this report's evidence.
    Computed once per report (LLM only, no searches), then served from the
    cache — so it's stable across views and instant in a demo."""
    report = _load_report(report_id)
    try:
        return await asyncio.to_thread(service.examination_for, report_id, report)
    except service.LLMUnavailable:
        raise HTTPException(
            status_code=503,
            detail="The examination preview needs an LLM key: add GROQ_API_KEY to backend/.env.",
        )
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Couldn't prepare the examination preview right now — please try again.",
        )
