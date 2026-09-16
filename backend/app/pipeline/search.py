"""Stage 1.2: Search Layer.

Fires the generated queries against SerpApi's google_patents engine
(scholar=true, clustered=true — this mixes real patents and scholar articles
into one organic_results list, distinguished by the presence of patent_id vs.
scholar_id/is_scholar) plus one plain `google` query for a market-availability
check. Keeps the query-to-result mapping intact for debugging and for the
landscape graph later.
"""
from typing import Literal

from pydantic import BaseModel

from app.pipeline.query_generator import QueryGenerationResult
from app.serpapi_client import client as _client

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


class QueryBundle(BaseModel):
    query_type: str
    query: str
    results: list[SearchResult]


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


def search_patents_for_query(query: str) -> list[SearchResult]:
    """Call google_patents for a single query, returning normalized results."""
    response = _client.search(
        engine="google_patents",
        q=query,
        scholar=True,
        clustered=True,
    )
    raw_results = dict(response).get("organic_results", []) or []
    results = []
    for raw in raw_results:
        parsed = _parse_patents_organic_result(raw)
        if parsed is not None:
            results.append(parsed)
    return results


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


def _build_market_query(query_result: QueryGenerationResult) -> str:
    return " ".join(query_result.core_concepts[:4])


def run_patent_scholar_search(query_result: QueryGenerationResult) -> list[QueryBundle]:
    """Run all generated queries against google_patents. Never raises on a
    single failed query — a bad query shouldn't kill the whole search stage;
    it just contributes an empty bundle."""
    bundles: list[QueryBundle] = []
    for gq in query_result.queries:
        try:
            results = search_patents_for_query(gq.query)
        except Exception:
            results = []
        bundles.append(QueryBundle(query_type=gq.type, query=gq.query, results=results))
    return bundles


def run_market_search(query_result: QueryGenerationResult) -> list[ProductResult]:
    try:
        return search_market_availability(_build_market_query(query_result))
    except Exception:
        return []


def run_search_layer(query_result: QueryGenerationResult) -> SearchLayerResult:
    """Convenience wrapper running both phases in sequence — used by direct
    pipeline tests. The orchestrator calls the two phases separately so it
    can emit progress events between them."""
    bundles = run_patent_scholar_search(query_result)
    market_results = run_market_search(query_result)
    return SearchLayerResult(query_bundles=bundles, market_results=market_results)
