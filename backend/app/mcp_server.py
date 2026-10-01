"""PriorArt AI as an MCP server: prior-art checks from inside Claude Desktop,
Cursor, or any other MCP client.

    python -m app.mcp_server          # stdio transport, from backend/

It's the same pipeline as the web app, through the same service layer — same
cache, same report ids — so a check started in an AI assistant can be opened
as a full interactive report in the browser, and vice versa.
"""
import asyncio

from mcp.server.mcpserver import Context, MCPServer

from app import service
from app.cache import list_top_level_reports
from app.config import GROQ_API_KEY, PUBLIC_APP_URL
from app.models import AnalysisResult
from app.pipeline.ask import answer_question
from app.report_markdown import examination_to_markdown, report_to_markdown

# The pipeline's stages, in order — for progress reporting to the client.
STAGES = [
    "generating_queries",
    "searching_patents",
    "searching_scholar",
    "checking_market_availability",
    "ranking_results",
    "refining_search",
    "scoring_novelty",
    "done",
]

server = MCPServer(
    name="priorart-ai",
    instructions=(
        "PriorArt AI checks whether an invention idea already exists. It searches real "
        "patents (including Indian Patent Office filings), academic papers and products "
        "through SerpApi, and returns a novelty verdict with cited prior art, patents "
        "that have expired and are free to build on, and concrete ways to differentiate. "
        "Ideas can be written in English or any Indian language. A fresh check takes "
        "about a minute; repeated checks of the same idea return instantly."
    ),
)


def _report_url(report_id: str | None) -> str | None:
    return f"{PUBLIC_APP_URL}/?report={report_id}" if report_id else None


def _render(result: AnalysisResult) -> str:
    return report_to_markdown(result, _report_url(result.report_id))


@server.tool()
async def check_prior_art(idea: str, ctx: Context, language: str | None = None) -> str:
    """Check an invention idea against existing patents, papers and products.

    Args:
        idea: The invention, described in plain language — what it is, how it
            works, what's new about it. Any Indian language works.
        language: Optional ISO 639-1 code (e.g. "hi") to force the report
            language. By default the report follows the idea's language.
    """
    async for event in service.analyze(idea, language):
        if event.type == "progress":
            step = STAGES.index(event.stage) + 1 if event.stage in STAGES else 0
            await ctx.report_progress(step, len(STAGES), event.message)
        elif event.type == "error":
            return f"Prior-art check failed: {event.message}"
        elif event.type == "result":
            return _render(event.data)
    return "Prior-art check ended without a result."


@server.tool()
def get_prior_art_report(report_id: str) -> str:
    """Open a saved prior-art report by its id (the `report=` value in a
    PriorArt AI report link)."""
    report = service.load_report(report_id)
    if report is None:
        return f"No saved report with id {report_id!r}."
    return _render(report)


@server.tool()
async def ask_about_report(report_id: str, question: str) -> str:
    """Answer a follow-up question about a saved prior-art report, using only
    what that report's searches found (with the documents cited). Good for
    "which patent is the biggest risk?", "can I sell this in India?", etc.

    Args:
        report_id: The report's id (from check_prior_art or list_saved_reports).
        question: The question, in any language; the answer uses the same one.
    """
    if not GROQ_API_KEY:
        return "Questions need an LLM key: add GROQ_API_KEY to backend/.env."
    report = service.load_report(report_id)
    if report is None:
        return f"No saved report with id {report_id!r}."
    try:
        answer = await asyncio.to_thread(answer_question, report, question)
    except ValueError:
        return "Couldn't answer that right now — try again or rephrase."
    sources = "\n".join(f"[{s.key}] {s.title} — {s.link}" for s in answer.sources)
    return f"{answer.answer}\n\n{sources}" if sources else answer.answer


@server.tool()
async def preview_examination_report(report_id: str) -> str:
    """Preview how an Indian patent examiner might respond to a saved report:
    Section 3 exclusions (software per se, farming methods, traditional
    knowledge, ...), and novelty / inventive-step objections computed from
    an element-by-element check with verified quotes. A simulation, not
    legal advice.

    Args:
        report_id: The report's id (from check_prior_art or list_saved_reports).
    """
    report = service.load_report(report_id)
    if report is None:
        return f"No saved report with id {report_id!r}."
    try:
        preview = await asyncio.to_thread(service.examination_for, report_id, report)
    except service.LLMUnavailable:
        return "The examination preview needs an LLM key: add GROQ_API_KEY to backend/.env."
    except ValueError:
        return "Couldn't prepare the examination preview right now — try again."
    return examination_to_markdown(preview)


@server.tool()
def list_saved_reports() -> str:
    """List saved prior-art reports (id, idea, and verdict) — these open
    instantly without running a new search."""
    reports = list_top_level_reports()
    if not reports:
        return "No saved reports yet."
    lines = []
    for report_id, event in reports:
        data = event.data
        idea = (data.original_idea_text or data.idea_text).strip()
        short = idea if len(idea) <= 120 else idea[:117] + "..."
        found = sum(1 for f in data.feature_findings if f.evidence)
        verdict = (
            f"overlap in {found} of {len(data.feature_findings)} features"
            if data.feature_findings
            else f"{round(data.overall_novelty_confidence * 100)}% model novelty estimate"
        )
        lines.append(f"- `{report_id}` — {verdict}: {short}")
    return "\n".join(lines)


if __name__ == "__main__":
    server.run()
