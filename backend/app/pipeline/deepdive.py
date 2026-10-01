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

The same details response also carries each patent's backward citations
(`patent_citations`) and forward citations (`cited_by`). Those are kept as
lightweight references for the citation-chasing stage — they cost nothing
extra, since the details call is being made anyway.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel

from app.pipeline.evidence import EvidenceSource
from app.pipeline.rank import RankedResult
from app.pipeline.search import SourceType
from app.serpapi_client import client as _client

MAX_SUMMARY_CHARS = 1200


class CitationRef(BaseModel):
    patent_id: str
    title: str = ""
    assignee: str | None = None
    priority_date: str | None = None
    # backward = this candidate cites it (older art); forward = it cites
    # this candidate (later work building on it).
    direction: Literal["backward", "forward"]
    examiner_cited: bool = False


class CandidateDetail(BaseModel):
    id: str
    source_type: SourceType
    title: str
    link: str
    summary_text: str
    # What summary_text was built from: the claims are the strongest
    # evidence, a search snippet the weakest.
    evidence_source: EvidenceSource = "snippet"
    prior_art_keywords: list[str] = []
    citation_refs: list[CitationRef] = []


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


def _parse_citation_refs(raw: dict) -> list[CitationRef]:
    """Only the "original" lists are used: "family_to_family" citations are
    attributed to the whole patent family and overlap heavily with them."""
    refs: list[CitationRef] = []
    for key, direction in (("patent_citations", "backward"), ("cited_by", "forward")):
        block = raw.get(key) or {}
        for item in block.get("original") or []:
            patent_id = item.get("patent_id")
            if not patent_id:
                continue
            refs.append(
                CitationRef(
                    patent_id=patent_id,
                    title=(item.get("title") or "").strip(),
                    assignee=item.get("assignee_original"),
                    priority_date=item.get("priority_date"),
                    direction=direction,
                    # SerpApi marks examiner citations with "*".
                    examiner_cited=bool(item.get("examiner_cited")),
                )
            )
    return refs


def _evidence_source(raw: dict, source_type: str) -> EvidenceSource:
    if source_type == "patent":
        if raw.get("claims"):
            return "claims"
        return "abstract" if raw.get("abstract") else "snippet"
    return "abstract" if raw.get("snippet") or raw.get("concepts") else "snippet"


def fetch_detail(
    doc_id: str, source_type: SourceType, title: str, link: str, snippet: str = ""
) -> CandidateDetail:
    try:
        raw = dict(_client.search(engine="google_patents_details", patent_id=doc_id))
    except Exception:
        raw = {}

    if source_type == "patent":
        summary_text = _summarize_patent_details(raw, snippet)
    else:
        summary_text = _summarize_scholar_details(raw, snippet)

    return CandidateDetail(
        id=doc_id,
        source_type=source_type,
        # Citation follow-ups know only a publication number; the details
        # response carries the real title.
        title=title or (raw.get("title") or "").strip() or doc_id,
        link=link,
        summary_text=summary_text,
        evidence_source=_evidence_source(raw, source_type),
        prior_art_keywords=raw.get("prior_art_keywords") or [],
        citation_refs=_parse_citation_refs(raw) if source_type == "patent" else [],
    )


def get_candidate_detail(candidate: RankedResult) -> CandidateDetail:
    return fetch_detail(
        candidate.id, candidate.source_type, candidate.title, candidate.link, candidate.snippet
    )


def deep_dive(ranked_results: list[RankedResult], top_n: int = 8) -> list[CandidateDetail]:
    """Selects the top-ranked patent/scholar candidates (products excluded)
    and pulls+condenses their full details. The lookups are independent, so
    they run concurrently; output order still follows the ranking, which
    downstream stages rely on (the first candidate is the closest match)."""
    candidates = [r for r in ranked_results if r.source_type in ("patent", "scholar")][:top_n]
    if not candidates:
        return []
    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        return list(pool.map(get_candidate_detail, candidates))
