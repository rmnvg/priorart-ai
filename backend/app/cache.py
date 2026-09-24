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
import re
from pathlib import Path

from app.models import AnalyzeStreamEvent, ErrorEvent, ProgressEvent, ResultEvent

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

_memory: dict[str, list[AnalyzeStreamEvent]] = {}

_KEY_PATTERN = re.compile(r"[0-9a-f]{16}")


def _normalize(idea_text: str) -> str:
    return " ".join(idea_text.strip().lower().split())


def cache_key(idea_text: str) -> str:
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
    return get_cached_by_key(cache_key(idea_text))


def is_valid_key(key: str) -> bool:
    """Keys arrive from report URLs, so they're untrusted — anything but the
    exact 16-hex-char shape we generate is rejected before it can become a
    file path."""
    return _KEY_PATTERN.fullmatch(key) is not None


def get_cached_by_key(key: str) -> list[AnalyzeStreamEvent] | None:
    if not is_valid_key(key):
        return None
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


def set_cached(
    idea_text: str, events: list[AnalyzeStreamEvent], parent_report_id: str | None = None
) -> None:
    """`parent_report_id` marks a re-check ("Apply & re-check" on another
    report) so the examples gallery can leave these variants out."""
    key = cache_key(idea_text)
    _memory[key] = events

    # Disk persistence is best-effort: if it fails, the in-memory cache still
    # works for this process and the request itself must not fail.
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "idea_text": idea_text,
            "parent_report_id": parent_report_id,
            "events": [e.model_dump(mode="json") for e in events],
        }
        _path_for(key).write_text(json.dumps(payload, indent=2))
    except OSError as e:
        logger.warning("Could not persist cache for key %s: %s", key, e)


def list_top_level_reports() -> list[tuple[str, ResultEvent]]:
    """Every cached analysis that isn't a re-check of another one, newest
    first — the examples gallery. Unreadable files are skipped, the same as
    a cache miss."""
    if not CACHE_DIR.exists():
        return []
    reports: list[tuple[float, str, ResultEvent]] = []
    for path in CACHE_DIR.glob("*.json"):
        key = path.stem
        if not is_valid_key(key):
            continue
        try:
            if json.loads(path.read_text()).get("parent_report_id"):
                continue
            mtime = path.stat().st_mtime
        except (OSError, json.JSONDecodeError):
            continue
        events = get_cached_by_key(key)
        result = next((e for e in events or [] if isinstance(e, ResultEvent)), None)
        if result is not None:
            reports.append((mtime, key, result))
    reports.sort(key=lambda r: r[0], reverse=True)
    return [(key, result) for _, key, result in reports]


def evict(key: str) -> None:
    """Forget a cached analysis (memory and disk), so the next request for
    it runs the pipeline fresh."""
    if not is_valid_key(key):
        return
    _memory.pop(key, None)
    _path_for(key).unlink(missing_ok=True)
    # Attachments were computed from the old analysis; they go with it.
    for path in CACHE_DIR.glob(f"{key}.*.json"):
        path.unlink(missing_ok=True)


# --- Per-report attachments --------------------------------------------------
# Things computed on demand from a saved report (the examination preview),
# stored beside it as "<key>.<name>.json" so they're computed once and replay
# instantly. The report listing ignores these files: their stems aren't keys.


def _attachment_path(key: str, name: str) -> Path:
    return CACHE_DIR / f"{key}.{name}.json"


def get_attachment(key: str, name: str) -> dict | None:
    if not is_valid_key(key):
        return None
    try:
        return json.loads(_attachment_path(key, name).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def set_attachment(key: str, name: str, payload: dict) -> None:
    if not is_valid_key(key):
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _attachment_path(key, name).write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    except OSError as e:
        logger.warning("Could not persist %s for key %s: %s", name, key, e)
