from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.cache import get_cached, set_cached
from app.models import AnalyzeStreamEvent
from app.pipeline.orchestrator import run_pipeline

app = FastAPI(title="PriorArt AI")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    idea_text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    async def event_stream() -> AsyncGenerator[dict, None]:
        cached_events = get_cached(request.idea_text)
        if cached_events is not None:
            for event in cached_events:
                yield {"event": event.type, "data": event.model_dump_json()}
            return

        collected: list[AnalyzeStreamEvent] = []
        async for event in run_pipeline(request.idea_text):
            collected.append(event)
            yield {"event": event.type, "data": event.model_dump_json()}

        if collected and collected[-1].type == "result":
            set_cached(request.idea_text, collected)

    return EventSourceResponse(event_stream())
