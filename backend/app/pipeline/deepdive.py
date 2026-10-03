"""Stage 1.4: Deep-Dive on Top Candidates.

Pulls full claims (patents) or concepts (scholar articles) for the top-ranked
candidates via google_patents_details, then truncates/condenses that text
before it goes near an LLM prompt. Product/market results are excluded here —
they don't have a patent_id, so there's nothing for google_patents_details to
look up; they still count toward overall novelty context downstream, just
without a claims deep-dive.

The abstract and first six claims each have their own character allowance, so
an abstract cannot displace every claim. Sections preserve attribution and
record truncation; this is bounded review, not full-specification analysis.

The same details response also carries each patent's backward citations
(`patent_citations`) and forward citations (`cited_by`). Those are kept as
lightweight references for the citation-chasing stage — they cost nothing
extra, since the details call is being made anyway.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel

from app.pipeline.evidence import EvidenceSection, EvidenceSource
from app.pipeline.rank import RankedResult
from app.pipeline.search import SourceType
from app.serpapi_client import client as _client

MAX_SUMMARY_CHARS = 1200
MAX_ABSTRACT_CHARS = 2400
MAX_CLAIM_CHARS = 1600
MAX_REVIEWED_CLAIMS = 6


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
    # Aggregate document label for older consumers. Individual quotations
    # are attributed using sections, never this document-level label.
    evidence_source: EvidenceSource = "snippet"
    prior_art_keywords: list[str] = []
    citation_refs: list[CitationRef] = []
    sections: list[EvidenceSection] = []
    total_claims: int = 0


def _truncate(text: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def _summarize_patent_details(raw: dict, fallback_snippet: str) -> str:
    sections = patent_sections(raw, fallback_snippet)
    if len(sections) == 1 and sections[0].source == "snippet":
        return sections[0].text
    return section_text(sections)


def _section(label: str, source: EvidenceSource, text: str, limit: int) -> EvidenceSection:
    text = text.strip()
    return EvidenceSection(label=label, source=source, text=text[:limit],
                           original_chars=len(text), truncated=len(text) > limit)


def patent_sections(raw: dict, fallback_snippet: str = "") -> list[EvidenceSection]:
    sections = []
    abstract = raw.get("abstract")
    if isinstance(abstract, str) and abstract.strip():
        sections.append(_section("Abstract", "abstract", abstract, MAX_ABSTRACT_CHARS))
    elif fallback_snippet.strip():
        sections.append(_section("Search snippet", "snippet", fallback_snippet, MAX_SUMMARY_CHARS))
    claims = raw.get("claims") or []
    if isinstance(claims, list):
        for index, claim in enumerate(claims[:MAX_REVIEWED_CLAIMS], 1):
            if isinstance(claim, str) and claim.strip():
                sections.append(_section(f"Claim {index}", "claims", claim, MAX_CLAIM_CHARS))
    return sections


def section_text(sections: list[EvidenceSection]) -> str:
    return "\n\n".join(f"{s.label}: {s.text}" + (" [excerpt ends]" if s.truncated else "") for s in sections)


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
        sections = patent_sections(raw, snippet)
        summary_text = section_text(sections)
    else:
        summary_text = _summarize_scholar_details(raw, snippet)
        sections = [_section("Scholar excerpt", "snippet", summary_text, MAX_SUMMARY_CHARS)] if summary_text else []

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
        sections=sections,
        total_claims=len(raw.get("claims") or []) if isinstance(raw.get("claims"), list) else 0,
    )


def get_candidate_detail(candidate: RankedResult) -> CandidateDetail:
    return fetch_detail(
        candidate.id, candidate.source_type, candidate.title, candidate.link, candidate.snippet
    )


def select_candidates(ranked_results: list[RankedResult], top_n: int) -> list[RankedResult]:
    """Patents get the detail slots first: a patent lookup returns claims to
    quote and citations to chase, while a scholar lookup returns only a
    snippet and keywords for the same search. Scholar articles fill any
    slots left over. The selection keeps ranking order."""
    patents = [r for r in ranked_results if r.source_type == "patent"][:top_n]
    scholars = [r for r in ranked_results if r.source_type == "scholar"][: top_n - len(patents)]
    chosen = {id(r) for r in patents + scholars}
    return [r for r in ranked_results if id(r) in chosen]


def deep_dive(ranked_results: list[RankedResult], top_n: int = 8) -> list[CandidateDetail]:
    """Selects the top-ranked candidates, patents first (products excluded),
    and pulls+condenses their full details. The lookups are independent, so
    they run concurrently; output order still follows the ranking, which
    downstream stages rely on (the first candidate is the closest match)."""
    candidates = select_candidates(ranked_results, top_n)
    if not candidates:
        return []
    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        return list(pool.map(get_candidate_detail, candidates))
