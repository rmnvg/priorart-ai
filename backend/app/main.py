from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app import service
from app.cache import get_cached_by_key, list_top_level_reports
from app.config import ALLOWED_ORIGINS, LIVE_MODE
from app.models import AnalysisResult

app = FastAPI(title="PriorArt AI")

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
    # Set when this run is a re-check of another report.
    parent_report_id: str | None = None


class ExampleReport(BaseModel):
    report_id: str
    idea_text: str
    language_name: str
    novelty_confidence: float
    results_count: int
    public_domain_count: int


@app.get("/health")
def health():
    return {"status": "ok", "live": LIVE_MODE}


@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    async def event_stream() -> AsyncGenerator[dict, None]:
        async for event in service.analyze(
            request.idea_text, request.language, request.parent_report_id
        ):
            yield {"event": event.type, "data": event.model_dump_json()}

    return EventSourceResponse(event_stream())


@app.get("/report/{report_id}", response_model=AnalysisResult)
def get_report(report_id: str) -> AnalysisResult:
    """A saved analysis by id — what a shared report link loads. Serves only
    what's already cached; never triggers a (billable) pipeline run."""
    events = get_cached_by_key(report_id)
    result = next((e for e in events or [] if e.type == "result"), None)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found")
    result.data.report_id = report_id
    return result.data


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
