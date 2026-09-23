from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.cache import cache_key, get_cached, get_cached_by_key, set_cached
from app.config import ALLOWED_ORIGINS
from app.models import AnalysisResult, AnalyzeStreamEvent
from app.pipeline.orchestrator import run_pipeline

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


def _with_report_id(event: AnalyzeStreamEvent, report_id: str) -> AnalyzeStreamEvent:
    # The report id is the cache key, so a shared link resolves to exactly
    # the cached analysis. Stamped on replay as well as on fresh runs, so
    # analyses cached before permalinks existed get one too.
    if event.type == "result":
        event.data.report_id = report_id
    return event


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    report_id = cache_key(request.idea_text)

    async def event_stream() -> AsyncGenerator[dict, None]:
        cached_events = get_cached(request.idea_text)
        if cached_events is not None:
            for event in cached_events:
                event = _with_report_id(event, report_id)
                yield {"event": event.type, "data": event.model_dump_json()}
            return

        collected: list[AnalyzeStreamEvent] = []
        async for event in run_pipeline(request.idea_text):
            event = _with_report_id(event, report_id)
            collected.append(event)
            yield {"event": event.type, "data": event.model_dump_json()}

        if collected and collected[-1].type == "result":
            set_cached(request.idea_text, collected)

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
