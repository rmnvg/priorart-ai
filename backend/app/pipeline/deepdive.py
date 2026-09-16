"""Stage 1.4: Deep-Dive on Top Candidates.

Pulls full claims (patents) or concepts (scholar articles) for the top-ranked
candidates via google_patents_details, then truncates/condenses that text
before it goes near an LLM prompt. Product/market results are excluded here —
they don't have a patent_id, so there's nothing for google_patents_details to
look up; they still count toward overall novelty context downstream, just
without a claims deep-dive.

Truncation is a plain heuristic (abstract + first independent claim(s), or
snippet + concepts for scholar), not a separate LLM summarization call — this
keeps the pipeline to one LLM call per candidate at the novelty-verdict stage
(1.5), rather than two.
"""
from pydantic import BaseModel

from app.pipeline.rank import RankedResult
from app.pipeline.search import SourceType
from app.serpapi_client import client as _client

MAX_SUMMARY_CHARS = 1200


class CandidateDetail(BaseModel):
    id: str
    source_type: SourceType
    title: str
    link: str
    summary_text: str
    prior_art_keywords: list[str] = []


def _truncate(text: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def _summarize_patent_details(raw: dict, fallback_snippet: str) -> str:
    abstract = raw.get("abstract") or fallback_snippet
    claims = raw.get("claims") or []
    parts = [abstract]
    for i, claim in enumerate(claims[:2]):
        parts.append(f"Claim {i + 1}: {claim}")
    return _truncate(" ".join(p for p in parts if p))


def _summarize_scholar_details(raw: dict, fallback_snippet: str) -> str:
    snippet = raw.get("snippet") or fallback_snippet
    concepts = raw.get("concepts") or []
    text = snippet
    if concepts:
        text += " Key concepts: " + ", ".join(concepts)
    return _truncate(text)


def get_candidate_detail(candidate: RankedResult) -> CandidateDetail:
    try:
        raw = dict(_client.search(engine="google_patents_details", patent_id=candidate.id))
    except Exception:
        raw = {}

    if candidate.source_type == "patent":
        summary_text = _summarize_patent_details(raw, candidate.snippet)
    else:
        summary_text = _summarize_scholar_details(raw, candidate.snippet)

    return CandidateDetail(
        id=candidate.id,
        source_type=candidate.source_type,
        title=candidate.title,
        link=candidate.link,
        summary_text=summary_text,
        prior_art_keywords=raw.get("prior_art_keywords") or [],
    )


def deep_dive(ranked_results: list[RankedResult], top_n: int = 8) -> list[CandidateDetail]:
    """Selects the top-ranked patent/scholar candidates (products excluded)
    and pulls+condenses their full details."""
    candidates = [r for r in ranked_results if r.source_type in ("patent", "scholar")][:top_n]
    return [get_candidate_detail(c) for c in candidates]
