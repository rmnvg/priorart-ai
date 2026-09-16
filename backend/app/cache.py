"""Cache of completed analyses, keyed on idea text.

Two layers: an in-process dict for speed, backed by JSON files on disk so a
cached analysis survives a server restart. That disk layer matters more than
it sounds — a single analysis costs 4-12 SerpApi searches, the free tier
allows 250/month, and an in-memory-only cache silently throws away every
result the moment the process dies. Cached runs are what make a demo
reproducible without live quota.

Caches the full event list (progress + result) so a cache hit replays the
staged-progress UI identically. Only successful runs are cached by the caller.
"""
import hashlib
import json
import logging
from pathlib import Path

from app.models import AnalyzeStreamEvent, ErrorEvent, ProgressEvent, ResultEvent

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

_memory: dict[str, list[AnalyzeStreamEvent]] = {}


def _normalize(idea_text: str) -> str:
    return " ".join(idea_text.strip().lower().split())


def _cache_key(idea_text: str) -> str:
    return hashlib.sha256(_normalize(idea_text).encode()).hexdigest()[:16]


def _path_for(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _deserialize_event(raw: dict) -> AnalyzeStreamEvent | None:
    event_type = raw.get("type")
    if event_type == "progress":
        return ProgressEvent.model_validate(raw)
    if event_type == "result":
        return ResultEvent.model_validate(raw)
    if event_type == "error":
        return ErrorEvent.model_validate(raw)
    return None


def get_cached(idea_text: str) -> list[AnalyzeStreamEvent] | None:
    key = _cache_key(idea_text)
    if key in _memory:
        return _memory[key]

    path = _path_for(key)
    if not path.exists():
        return None

    # A cache file written by an older schema version will fail validation —
    # treat that as a miss rather than an error, so a schema change degrades
    # to "re-run it" instead of breaking the endpoint.
    try:
        payload = json.loads(path.read_text())
        events = [e for e in (_deserialize_event(r) for r in payload["events"]) if e is not None]
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Ignoring unreadable cache file %s: %s", path.name, e)
        return None

    if not events:
        return None
    _memory[key] = events
    return events


def set_cached(idea_text: str, events: list[AnalyzeStreamEvent]) -> None:
    key = _cache_key(idea_text)
    _memory[key] = events

    # Disk persistence is best-effort: if it fails, the in-memory cache still
    # works for this process and the request itself must not fail.
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "idea_text": idea_text,
            "events": [e.model_dump(mode="json") for e in events],
        }
        _path_for(key).write_text(json.dumps(payload, indent=2))
    except OSError as e:
        logger.warning("Could not persist cache for key %s: %s", key, e)
