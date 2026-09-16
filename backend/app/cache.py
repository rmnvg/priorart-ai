"""Simple in-memory cache keyed on idea text, so re-running the same demo
query during development/rehearsal doesn't re-burn SerpApi/Groq quota. Caches
the full event list (progress + result) so a cache hit replays identically.
Process-local and unbounded — fine for a single-instance hackathon demo, not
meant to survive restarts or scale beyond that.
"""
from app.models import AnalyzeStreamEvent

_cache: dict[str, list[AnalyzeStreamEvent]] = {}


def _normalize(idea_text: str) -> str:
    return " ".join(idea_text.strip().lower().split())


def get_cached(idea_text: str) -> list[AnalyzeStreamEvent] | None:
    return _cache.get(_normalize(idea_text))


def set_cached(idea_text: str, events: list[AnalyzeStreamEvent]) -> None:
    _cache[_normalize(idea_text)] = events
