"""Analysis as a service: cache lookup, demo-mode guard, pipeline run, cache
write — shared by the HTTP API (app.main) and the MCP server
(app.mcp_server), so both entry points behave identically: the same report
ids, the same cache, the same refusal without API keys.
"""
import asyncio
from collections.abc import AsyncGenerator

from app.cache import cache_key, get_cached, is_valid_key, set_cached
from app.config import LIVE_MODE, REPLAY_STEP_SECONDS
from app.models import AnalyzeStreamEvent, ErrorEvent
from app.pipeline.orchestrator import run_pipeline

DEMO_MODE_MESSAGE = (
    "This copy of PriorArt AI is running in demo mode (no API keys configured), so it "
    "can't analyze new ideas — but every example report works. To run live analyses, "
    "add SERPAPI_API_KEY and GROQ_API_KEY to backend/.env and restart the server."
)


def cache_text_for(idea_text: str, language: str | None) -> str:
    # The same idea asked for in a different report language is a different
    # report, so the language is part of what's cached.
    if language:
        return f"{idea_text}\n[report-language:{language.lower()}]"
    return idea_text


def report_id_for(idea_text: str, language: str | None) -> str:
    return cache_key(cache_text_for(idea_text, language))


def _with_report_id(event: AnalyzeStreamEvent, report_id: str) -> AnalyzeStreamEvent:
    # The report id is the cache key, so a shared link resolves to exactly
    # the cached analysis. Stamped on replay as well as on fresh runs, so
    # analyses cached before permalinks existed get one too.
    if event.type == "result":
        event.data.report_id = report_id
    return event


async def analyze(
    idea_text: str,
    language: str | None = None,
    parent_report_id: str | None = None,
) -> AsyncGenerator[AnalyzeStreamEvent, None]:
    """Yields the same events as the pipeline, replaying from cache when the
    idea has been analyzed before."""
    cache_text = cache_text_for(idea_text, language)
    report_id = cache_key(cache_text)
    parent = parent_report_id if parent_report_id and is_valid_key(parent_report_id) else None

    cached_events = get_cached(cache_text)
    if cached_events is not None:
        for event in cached_events:
            if event.type == "progress" and REPLAY_STEP_SECONDS > 0:
                await asyncio.sleep(REPLAY_STEP_SECONDS)
            yield _with_report_id(event, report_id)
        return

    if not LIVE_MODE:
        yield ErrorEvent(message=DEMO_MODE_MESSAGE)
        return

    collected: list[AnalyzeStreamEvent] = []
    async for event in run_pipeline(idea_text, language):
        event = _with_report_id(event, report_id)
        collected.append(event)
        yield event

    if collected and collected[-1].type == "result":
        set_cached(cache_text, collected, parent_report_id=parent)
