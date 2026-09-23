"""Citation chasing: prior art that keyword search can't find.

Keyword search only finds documents that use words like the ones in the
query. Professional patent searchers close that gap by "citation chasing" —
following the references of the closest matches backward (what they cite)
and forward (what later cites them). A document that several of the closest
matches all point at is almost certainly relevant, whatever words it uses.

Runs entirely on citation lists already returned by google_patents_details
during the deep-dive — no extra API calls.

Also produces the citation edges between search results, which turn the
landscape graph's links from "similar to your idea" into real, documented
relationships between patents.
"""
from typing import Literal

from pydantic import BaseModel

from app.pipeline.deepdive import CandidateDetail, CitationRef
from app.pipeline.public_domain import PATENT_TERM_YEARS, years_since
from app.pipeline.rank import RankedResult

# Referenced by at least this many distinct top candidates to count as a
# discovery on its own. One shared reference between two unrelated patents
# is common; two of the *closest matches* agreeing on a document isn't.
MIN_SHARED_REFERENCES = 2
MAX_DISCOVERIES = 8
# Fallback when nothing is shared: the examiner-cited references of the
# closest match — the documents the patent office itself judged most relevant.
MAX_EXAMINER_FALLBACK = 3

DiscoveryReason = Literal["shared_reference", "examiner_cited"]


class CitationDiscovery(BaseModel):
    id: str
    title: str
    link: str
    assignee: str | None = None
    priority_date: str | None = None
    referenced_by: list[str]  # ids of the top candidates that cite / are cited by it
    direction: Literal["backward", "forward", "both"]
    examiner_cited: bool
    reason: DiscoveryReason
    likely_expired: bool


class CitationEdge(BaseModel):
    source: str
    target: str


class CitationNetwork(BaseModel):
    discoveries: list[CitationDiscovery] = []
    edges: list[CitationEdge] = []
    references_scanned: int = 0


def patent_link(patent_id: str) -> str:
    # SerpApi patent ids are Google Patents paths ("patent/US5208813A/en").
    return f"https://patents.google.com/{patent_id}"


def _publication_number(patent_id: str) -> str:
    parts = patent_id.split("/")
    return parts[1] if len(parts) >= 2 else patent_id


def _likely_expired(priority_date: str | None) -> bool:
    age = years_since(priority_date)
    return age is not None and age >= PATENT_TERM_YEARS


def _build_edges(candidates: list[CandidateDetail], ranked_ids: set[str]) -> list[CitationEdge]:
    seen: set[frozenset[str]] = set()
    edges: list[CitationEdge] = []
    for c in candidates:
        for ref in c.citation_refs:
            if ref.patent_id == c.id or ref.patent_id not in ranked_ids:
                continue
            pair = frozenset((c.id, ref.patent_id))
            if pair in seen:
                continue
            seen.add(pair)
            # Edges point from the citing patent to the cited one.
            if ref.direction == "backward":
                edges.append(CitationEdge(source=c.id, target=ref.patent_id))
            else:
                edges.append(CitationEdge(source=ref.patent_id, target=c.id))
    return edges


def _to_discovery(
    patent_id: str, refs: list[tuple[str, CitationRef]], reason: DiscoveryReason
) -> CitationDiscovery:
    # Any one ref carries the metadata; prefer one that actually has a title.
    best = next((r for _, r in refs if r.title), refs[0][1])
    directions = {r.direction for _, r in refs}
    return CitationDiscovery(
        id=patent_id,
        title=best.title or _publication_number(patent_id),
        link=patent_link(patent_id),
        assignee=best.assignee,
        priority_date=best.priority_date,
        referenced_by=sorted({cid for cid, _ in refs}),
        direction=directions.pop() if len(directions) == 1 else "both",
        examiner_cited=any(r.examiner_cited for _, r in refs),
        reason=reason,
        likely_expired=_likely_expired(best.priority_date),
    )


def chase_citations(
    candidates: list[CandidateDetail], ranked_results: list[RankedResult]
) -> CitationNetwork:
    ranked_ids = {r.id for r in ranked_results}

    # Group every reference to a document not already in the search results
    # by the document it points at.
    by_target: dict[str, list[tuple[str, CitationRef]]] = {}
    scanned = 0
    for c in candidates:
        for ref in c.citation_refs:
            scanned += 1
            if ref.patent_id in ranked_ids:
                continue
            by_target.setdefault(ref.patent_id, []).append((c.id, ref))

    shared = [
        (pid, refs)
        for pid, refs in by_target.items()
        if len({cid for cid, _ in refs}) >= MIN_SHARED_REFERENCES
    ]
    # Most-agreed-upon first; examiner citations break ties, since those are
    # the office's own relevance judgement rather than the applicant's.
    shared.sort(
        key=lambda item: (
            len({cid for cid, _ in item[1]}),
            any(r.examiner_cited for _, r in item[1]),
        ),
        reverse=True,
    )
    discoveries = [_to_discovery(pid, refs, "shared_reference") for pid, refs in shared]

    # The closest match might be a scholar article, which has no citation
    # data — fall back to the closest *patent*.
    closest = next((c for c in candidates if c.citation_refs), None)
    if not discoveries and closest:
        fallback = [
            ref
            for ref in closest.citation_refs
            if ref.direction == "backward"
            and ref.examiner_cited
            and ref.patent_id not in ranked_ids
        ]
        discoveries = [
            _to_discovery(ref.patent_id, [(closest.id, ref)], "examiner_cited")
            for ref in fallback[:MAX_EXAMINER_FALLBACK]
        ]

    return CitationNetwork(
        discoveries=discoveries[:MAX_DISCOVERIES],
        edges=_build_edges(candidates, ranked_ids),
        references_scanned=scanned,
    )
