"""Stage 1.2: Search Layer.

Fires the generated queries against SerpApi's google_patents engine
(clustered=true, patents only) plus one plain `google` query for a
market-availability check and one scholar-only google_patents query for
academic papers. Papers get their own call because mixing them in
(scholar=true) fills the first page with papers on research-heavy topics: a
solar crop dryer's broad query returned 19 papers and 1 patent out of 20,
leaving no claims to quote. Keeps the query-to-result mapping intact for
debugging and for the landscape graph later.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel

from app.pipeline.query_generator import GeneratedQuery, QueryGenerationResult
from app.serpapi_client import client as _client
from app.serpapi_client import redact

logger = logging.getLogger(__name__)

SourceType = Literal["patent", "scholar", "product"]


class PatentResult(BaseModel):
    source_type: Literal["patent"] = "patent"
    id: str
    title: str
    snippet: str = ""
    link: str
    cpc_code: str | None = None
    cpc_description: str | None = None
    country_status: dict[str, str] = {}
    assignee: str | None = None
    priority_date: str | None = None


class ScholarResult(BaseModel):
    source_type: Literal["scholar"] = "scholar"
    id: str
    title: str
    snippet: str = ""
    link: str
    author: str | None = None
    publication_date: str | None = None


class ProductResult(BaseModel):
    source_type: Literal["product"] = "product"
    id: str
    title: str
    snippet: str = ""
    link: str


SearchResult = PatentResult | ScholarResult | ProductResult


class AssigneeStat(BaseModel):
    name: str
    percentage: float


class QueryBundle(BaseModel):
    query_type: str
    query: str
    country: str | None = None
    results: list[SearchResult]
    assignee_stats: list[AssigneeStat] = []
    # True when the search call itself raised (quota exhausted, network,
    # auth) rather than simply matching nothing. The orchestrator needs the
    # difference: "no prior art exists" and "we couldn't search" are very
    # different things to tell a user.
    search_failed: bool = False


class SearchLayerResult(BaseModel):
    query_bundles: list[QueryBundle]
    market_results: list[ProductResult]


def _parse_patents_organic_result(raw: dict) -> SearchResult | None:
    if raw.get("patent_id"):
        return PatentResult(
            id=raw["patent_id"],
            title=raw.get("title", ""),
            snippet=raw.get("snippet", ""),
            link=raw.get("patent_link", ""),
            cpc_code=raw.get("cpc"),
            cpc_description=raw.get("cpc_description"),
            country_status=raw.get("country_status", {}) or {},
            assignee=raw.get("assignee"),
            priority_date=raw.get("priority_date"),
        )
    if raw.get("scholar_id") or raw.get("is_scholar"):
        return ScholarResult(
            id=raw.get("scholar_id", raw.get("serpapi_link", "")),
            title=raw.get("title", ""),
            snippet=raw.get("snippet", ""),
            link=raw.get("scholar_link", ""),
            author=raw.get("author"),
            publication_date=raw.get("publication_date"),
        )
    return None


def _parse_assignee_stats(raw_response: dict, top_n: int = 6) -> list[AssigneeStat]:
    """Reads the clustered-search assignee breakdown SerpApi already returns
    (query-level stats over the full matching set, not just the returned
    page) — zero extra API calls. Skips the "Total" (100%) row."""
    raw_assignees = raw_response.get("summary", {}).get("assignee", []) or []
    stats = [
        AssigneeStat(name=a["key"], percentage=a["percentage"])
        for a in raw_assignees
        if a.get("key") and a.get("key") != "Total"
    ]
    stats.sort(key=lambda a: a.percentage, reverse=True)
    return stats[:top_n]


# The India-specific query is restricted to Indian Patent Office filings at
# the API level. Asking the LLM to "phrase it to catch IN filings" (the
# original approach) has no actual effect on what Google Patents returns —
# only the country filter does.
QUERY_COUNTRY_FILTERS: dict[str, str] = {"india_specific": "IN"}

# Results per patent query. SerpApi bills per request, not per result, so a
# 20-result page doubles what ranking can choose from at no extra cost.
PATENT_RESULTS_PER_QUERY = 20


def search_patents_for_query(
    query: str, country: str | None = None
) -> tuple[list[SearchResult], list[AssigneeStat]]:
    """Call google_patents for a single query, returning normalized results
    plus the query-level assignee breakdown."""
    params = dict(engine="google_patents", q=query, clustered=True, num=PATENT_RESULTS_PER_QUERY)
    if country:
        params["country"] = country
    response = _client.search(**params)
    raw_response = dict(response)
    raw_results = raw_response.get("organic_results", []) or []
    results = []
    for raw in raw_results:
        parsed = _parse_patents_organic_result(raw)
        if parsed is not None:
            results.append(parsed)
    return results, _parse_assignee_stats(raw_response)


def search_literature(query: str) -> list[SearchResult]:
    """Academic papers only (scholar=true, patents=false), one search."""
    response = _client.search(engine="google_patents", q=query, scholar=True, patents=False)
    raw_results = dict(response).get("organic_results", []) or []
    return [r for r in map(_parse_patents_organic_result, raw_results) if r is not None]


def run_literature_search(query_result: QueryGenerationResult) -> QueryBundle | None:
    """Papers for the broad-recall angle, kept as a bundle of their own so
    they rank alongside patents without displacing them. None when there is
    no broad-recall query; a failed search is an empty bundle, like
    _run_one_query."""
    broad = next((q for q in query_result.queries if q.type == "broad_recall"), None)
    if broad is None:
        return None
    query = clean_query(broad.query)
    try:
        results, failed = search_literature(query), False
    except Exception as e:
        logger.warning("Literature search failed: %s", redact(e))
        results, failed = [], True
    return QueryBundle(query_type="broad_recall", query=query, results=results, search_failed=failed)


def search_market_availability(query: str) -> list[ProductResult]:
    """Plain google search as a 'does something like this already exist
    commercially' check."""
    response = _client.search(engine="google", q=query)
    raw_results = dict(response).get("organic_results", []) or []
    return [
        ProductResult(
            id=raw.get("link", ""),
            title=raw.get("title", ""),
            snippet=raw.get("snippet", ""),
            link=raw.get("link", ""),
        )
        for raw in raw_results
    ]


def build_market_query(query_result: QueryGenerationResult) -> str:
    return " ".join(query_result.core_concepts[:4])


# LLMs "typeset" their output — non-breaking hyphens, curly quotes — and
# Google Patents treats those as different characters: a curly-quoted phrase
# is no longer a phrase, and "foam‑filled" with U+2011 matches nothing.
_QUERY_PUNCTUATION = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
)


def clean_query(query: str) -> str:
    return " ".join(query.translate(_QUERY_PUNCTUATION).split())


def _run_one_query(gq: GeneratedQuery) -> QueryBundle:
    country = QUERY_COUNTRY_FILTERS.get(gq.type)
    query = clean_query(gq.query)
    search_failed = False
    try:
        results, assignee_stats = search_patents_for_query(query, country)
    except Exception as e:
        logger.warning("Patent search failed for %s query: %s", gq.type, redact(e))
        results, assignee_stats, search_failed = [], [], True
    return QueryBundle(
        query_type=gq.type,
        query=query,
        country=country,
        results=results,
        assignee_stats=assignee_stats,
        search_failed=search_failed,
    )


def run_queries(queries: list[GeneratedQuery]) -> list[QueryBundle]:
    """Run queries against google_patents, concurrently — the calls are
    independent and each is a few seconds of network wait. Never raises on a
    single failed query — a bad query shouldn't kill the whole search stage;
    it just contributes an empty bundle. Bundle order matches query order
    regardless of which call finishes first."""
    if not queries:
        return []
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        return list(pool.map(_run_one_query, queries))


def run_patent_scholar_search(query_result: QueryGenerationResult) -> list[QueryBundle]:
    return run_queries(query_result.queries)


def run_market_search(query_result: QueryGenerationResult) -> list[ProductResult]:
    try:
        return search_market_availability(build_market_query(query_result))
    except Exception:
        return []


def run_search_layer(query_result: QueryGenerationResult) -> SearchLayerResult:
    """Convenience wrapper running the phases in sequence — used by direct
    pipeline tests. The orchestrator calls the phases separately so it
    can emit progress events between them."""
    bundles = run_patent_scholar_search(query_result)
    literature = run_literature_search(query_result)
    if literature is not None:
        bundles.append(literature)
    market_results = run_market_search(query_result)
    return SearchLayerResult(query_bundles=bundles, market_results=market_results)
