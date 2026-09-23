"""Stage 1.3: Rank & Dedupe.

Merges results across all query bundles (patents, scholar, market/product),
dedupes by id, and scores each candidate's relevance to the original idea
using embedding similarity (sentence-transformers) rather than an extra LLM
call per candidate — cheaper and fast enough for this many candidates.

sentence-transformers (and torch under it) is imported on first use, not at
module import: it takes seconds and hundreds of MB, and demo mode, the report
endpoints and the test suite never rank anything. Call `warm_up()` at server
start to pay that cost before the first request instead of during it.
"""
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.pipeline.search import SearchLayerResult, SearchResult, SourceType

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_model: "SentenceTransformer | None" = None


def _get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def warm_up() -> None:
    """Load the embedding model now rather than on the first analysis."""
    _get_model()


class RankedResult(BaseModel):
    id: str
    source_type: SourceType
    title: str
    snippet: str
    link: str
    relevance_score: float
    cpc_code: str | None = None
    cpc_description: str | None = None
    country_status: dict[str, str] = {}
    query_types: list[str] = []
    assignee: str | None = None
    priority_date: str | None = None


def _dedupe(search_result: SearchLayerResult) -> list[tuple[SearchResult, list[str]]]:
    """Merge results across bundles, deduping by id. Returns each unique
    result paired with the list of query types that surfaced it."""
    by_id: dict[str, tuple[SearchResult, list[str]]] = {}

    for bundle in search_result.query_bundles:
        for result in bundle.results:
            if result.id in by_id:
                by_id[result.id][1].append(bundle.query_type)
            else:
                by_id[result.id] = (result, [bundle.query_type])

    for product in search_result.market_results:
        if product.id in by_id:
            by_id[product.id][1].append("market_availability")
        else:
            by_id[product.id] = (product, ["market_availability"])

    return list(by_id.values())


def rank_and_dedupe(search_result: SearchLayerResult, idea_text: str) -> list[RankedResult]:
    deduped = _dedupe(search_result)
    if not deduped:
        return []

    model = _get_model()
    idea_embedding = model.encode(idea_text, convert_to_tensor=True)

    candidate_texts = [f"{r.title}. {r.snippet}" for r, _ in deduped]
    candidate_embeddings = model.encode(candidate_texts, convert_to_tensor=True)

    from sentence_transformers import util

    similarities = util.cos_sim(idea_embedding, candidate_embeddings)[0]

    ranked: list[RankedResult] = []
    for (result, query_types), score in zip(deduped, similarities):
        relevance_score = max(0.0, float(score))
        common = dict(
            id=result.id,
            source_type=result.source_type,
            title=result.title,
            snippet=result.snippet,
            link=result.link,
            relevance_score=relevance_score,
            query_types=query_types,
        )
        if result.source_type == "patent":
            common["cpc_code"] = result.cpc_code
            common["cpc_description"] = result.cpc_description
            common["country_status"] = result.country_status
            common["assignee"] = result.assignee
            common["priority_date"] = result.priority_date
        ranked.append(RankedResult(**common))

    ranked.sort(key=lambda r: r.relevance_score, reverse=True)
    return ranked
