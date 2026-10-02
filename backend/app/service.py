"""Analysis as a service: cache lookup, demo-mode guard, pipeline run, cache
write — shared by the HTTP API (app.main) and the MCP server
(app.mcp_server), so both entry points behave identically: the same report
ids, the same cache, the same refusal without API keys.
"""
import asyncio
import hashlib
from collections.abc import AsyncGenerator
from threading import Lock

from app.cache import (
    cache_key,
    get_attachment,
    get_cached,
    get_cached_by_key,
    is_valid_key,
    set_attachment,
    set_cached,
)
from app.config import GROQ_API_KEY, LIVE_MODE, REPLAY_STEP_SECONDS
from app.models import AnalysisResult, AnalyzeStreamEvent, ErrorEvent
from app.pipeline.challenge import (
    ChallengeResult,
    ChallengeUnavailable,
    challenge_finding,
    missing_feature,
)
from app.pipeline.examination import ExaminationPreview, preview_examination
from app.pipeline.orchestrator import run_pipeline
from app.pipeline.redesign import (
    FeatureList,
    RedesignBrief,
    RedesignResult,
    brief_key,
    extract_features,
    features_from_texts,
    normalize_brief,
    propose_redesigns,
)
from app.pipeline.sketch import SketchReading, decode_image, read_sketch

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
    applied_change: str | None = None,
) -> AsyncGenerator[AnalyzeStreamEvent, None]:
    """Yields the same events as the pipeline, replaying from cache when the
    idea has been analyzed before. A re-check names the report it revises
    and the change applied, for the evidence comparison."""
    cache_text = cache_text_for(idea_text, language)
    report_id = cache_key(cache_text)
    parent = parent_report_id if parent_report_id and is_valid_key(parent_report_id) else None

    cached_events = get_cached(cache_text)
    if cached_events is not None:
        for event in cached_events:
            if event.type == "progress":
                if REPLAY_STEP_SECONDS > 0:
                    await asyncio.sleep(REPLAY_STEP_SECONDS)
                event = event.model_copy(update={"replayed": True})
            yield _with_report_id(event, report_id)
        return

    if not LIVE_MODE:
        yield ErrorEvent(message=DEMO_MODE_MESSAGE)
        return

    parent_report = load_report(parent) if parent else None
    collected: list[AnalyzeStreamEvent] = []
    async for event in run_pipeline(
        idea_text,
        language,
        parent=parent_report,
        parent_report_id=parent if parent_report else None,
        applied_change=(applied_change or "").strip() or None,
    ):
        event = _with_report_id(event, report_id)
        collected.append(event)
        yield event

    if collected and collected[-1].type == "result":
        set_cached(cache_text, collected, parent_report_id=parent)


class LLMUnavailable(Exception):
    """An LLM-only feature was requested without an LLM key configured."""


# Fixed lock stripes bound memory and coalesce concurrent requests in this process.
_challenge_locks = [Lock() for _ in range(32)]


def _challenge_name(report: AnalysisResult, feature_id: str) -> str:
    feature = missing_feature(report, feature_id)
    digest = hashlib.sha256(f"{feature.id}:{feature.feature}".encode()).hexdigest()[:16]
    return f"challenge-v1-{digest}"


def saved_challenge(report_id: str, report: AnalysisResult, feature_id: str) -> ChallengeResult | None:
    cached = get_attachment(report_id, _challenge_name(report, feature_id))
    if cached is not None:
        try:
            return ChallengeResult.model_validate(cached)
        except ValueError:
            pass
    return None


def challenge_for(report_id: str, report: AnalysisResult, feature_id: str) -> ChallengeResult:
    name = _challenge_name(report, feature_id)
    with _challenge_locks[hash((report_id, name)) % len(_challenge_locks)]:
        cached = saved_challenge(report_id, report, feature_id)
        if cached is not None:
            return cached
        if not LIVE_MODE:
            raise ChallengeUnavailable(
                "New challenges need SERPAPI_API_KEY and GROQ_API_KEY. Saved challenges still work."
            )
        result = challenge_finding(report, feature_id)
        # Incomplete attempts remain retryable, not permanently cached as absence.
        if result.outcome != "inconclusive":
            set_attachment(report_id, name, result.model_dump(mode="json"))
        return result


def load_report(report_id: str) -> AnalysisResult | None:
    events = get_cached_by_key(report_id)
    result = next((e for e in events or [] if e.type == "result"), None)
    if result is None:
        return None
    result.data.report_id = report_id
    return result.data


EXAMINATION_ATTACHMENT = "examination"


def examination_for(report_id: str, report: AnalysisResult) -> ExaminationPreview:
    """The report's examination preview: from the cache when it's been
    computed before (stable across views, instant in a demo), otherwise
    computed now and cached. Raises LLMUnavailable without a Groq key, and
    ValueError if the model can't produce usable output."""
    cached = get_attachment(report_id, EXAMINATION_ATTACHMENT)
    if cached is not None:
        try:
            return ExaminationPreview.model_validate(cached)
        except ValueError:
            pass  # written by an older schema: recompute
    if not GROQ_API_KEY:
        raise LLMUnavailable
    preview = preview_examination(report)
    set_attachment(report_id, EXAMINATION_ATTACHMENT, preview.model_dump(mode="json"))
    return preview


FEATURES_ATTACHMENT = "features"


def features_for(report_id: str, report: AnalysisResult) -> FeatureList:
    """The idea's features for the redesign studio. When the examination
    preview has been run, its elements are reused, so both views name the
    same parts; otherwise they're extracted now. Cached either way."""
    cached = get_attachment(report_id, FEATURES_ATTACHMENT)
    if cached is not None:
        try:
            return FeatureList.model_validate(cached)
        except ValueError:
            pass
    examination = get_attachment(report_id, EXAMINATION_ATTACHMENT)
    features = None
    if examination is not None:
        try:
            elements = ExaminationPreview.model_validate(examination).elements
            features = FeatureList(features=features_from_texts([e.text for e in elements]))
        except ValueError:
            features = None
    if features is None:
        if not GROQ_API_KEY:
            raise LLMUnavailable
        features = extract_features(report.idea_text)
    set_attachment(report_id, FEATURES_ATTACHMENT, features.model_dump(mode="json"))
    return features


def redesign_for(report_id: str, report: AnalysisResult, brief: RedesignBrief) -> RedesignResult:
    """Alternative designs for this brief: cached per report and brief, so a
    demo replays the same designs and a repeat request costs nothing."""
    features = features_for(report_id, report).features
    locked, constraints = normalize_brief(brief, features)
    name = f"redesign-{brief_key(locked, constraints)}"
    cached = get_attachment(report_id, name)
    if cached is not None:
        try:
            return RedesignResult.model_validate(cached)
        except ValueError:
            pass
    if not GROQ_API_KEY:
        raise LLMUnavailable
    result = propose_redesigns(report, features, brief)
    set_attachment(report_id, name, result.model_dump(mode="json"))
    return result


SKETCH_ATTACHMENT = "sketch"


def sketch_reading_for(image_data_url: str, note: str | None) -> SketchReading:
    """A sketch read into parts and connections. Cached on the image and
    note, so the same drawing gives the same reading on stage. Raises
    SketchUnreadable for an image the inventor should replace."""
    image = decode_image(image_data_url)
    note = (note or "").strip()
    key = hashlib.sha256(image + b"\0" + note.encode()).hexdigest()[:16]
    cached = get_attachment(key, SKETCH_ATTACHMENT)
    if cached is not None:
        try:
            return SketchReading.model_validate(cached)
        except ValueError:
            pass
    if not GROQ_API_KEY:
        raise LLMUnavailable
    reading = read_sketch(image_data_url, note)
    set_attachment(key, SKETCH_ATTACHMENT, reading.model_dump(mode="json"))
    return reading
