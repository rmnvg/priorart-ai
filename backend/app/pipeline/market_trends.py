"""Market-interest signal from Google Trends.

Patent search answers "can I protect this?"; it says nothing about "does
anyone want this?". Five years of Google search interest in the product
category is a cheap, honest proxy for demand — and it's the one question an
independent inventor should ask before paying for a patent at all.

One SerpApi `google_trends` call per analysis. Best-effort: any failure, or a
category too niche for Trends to have data on, yields None and the report
simply omits the section.
"""
import logging
from typing import Literal

from pydantic import BaseModel

from app.serpapi_client import client as _client
from app.serpapi_client import redact

logger = logging.getLogger(__name__)

TRENDS_WINDOW = "today 5-y"
TRENDS_MAX_QUERY_CHARS = 100  # Google Trends' own per-query limit
# Compare the average of the most recent year against the year before it.
# Weekly data points, so one "year" is 52 of them.
PERIOD_POINTS = 52
# Relative change needed before calling a direction; below it, "steady".
DIRECTION_THRESHOLD = 0.15
# Series whose peak is this low are mostly zeros — Trends' way of saying
# "not enough searches". Showing a flat line at zero would imply "no demand"
# when the truth is "no data".
MIN_PEAK_INTEREST = 10

TrendDirection = Literal["rising", "steady", "declining"]


class TrendPoint(BaseModel):
    date: str
    value: int


class MarketTrend(BaseModel):
    keyword: str
    points: list[TrendPoint]
    direction: TrendDirection
    change_pct: int  # most recent year vs. the year before, in percent


def _direction(values: list[int]) -> tuple[TrendDirection, int]:
    if len(values) < PERIOD_POINTS * 2:
        half = len(values) // 2
        recent, previous = values[half:], values[:half]
    else:
        recent = values[-PERIOD_POINTS:]
        previous = values[-PERIOD_POINTS * 2 : -PERIOD_POINTS]
    prev_avg = sum(previous) / len(previous) if previous else 0
    recent_avg = sum(recent) / len(recent) if recent else 0
    if prev_avg == 0:
        return ("rising" if recent_avg > 0 else "steady"), 0
    change = (recent_avg - prev_avg) / prev_avg
    if change >= DIRECTION_THRESHOLD:
        direction: TrendDirection = "rising"
    elif change <= -DIRECTION_THRESHOLD:
        direction = "declining"
    else:
        direction = "steady"
    return direction, round(change * 100)


def parse_trend(keyword: str, raw: dict) -> MarketTrend | None:
    timeline = (raw.get("interest_over_time") or {}).get("timeline_data") or []
    points: list[TrendPoint] = []
    for entry in timeline:
        values = entry.get("values") or []
        if not values:
            continue
        value = values[0].get("extracted_value")
        if not isinstance(value, (int, float)):
            continue
        points.append(TrendPoint(date=entry.get("date", ""), value=int(value)))

    if not points or max(p.value for p in points) < MIN_PEAK_INTEREST:
        return None

    direction, change_pct = _direction([p.value for p in points])
    return MarketTrend(keyword=keyword, points=points, direction=direction, change_pct=change_pct)


def fetch_market_trend(keyword: str | None) -> MarketTrend | None:
    keyword = (keyword or "").strip()[:TRENDS_MAX_QUERY_CHARS]
    if not keyword:
        return None
    try:
        raw = dict(
            _client.search(engine="google_trends", q=keyword, data_type="TIMESERIES", date=TRENDS_WINDOW)
        )
    except Exception as e:
        logger.warning("Google Trends lookup failed for %r: %s", keyword, redact(e))
        return None
    return parse_trend(keyword, raw)
