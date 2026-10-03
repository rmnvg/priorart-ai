"""Feature-level evidence: what the report's conclusion actually rests on.

A single model-generated novelty number can't be inspected. So the report's
headline is built from evidence instead: the idea is split into a few
essential features, and each one is either shown in a reviewed document —
with the exact passage, verified against that document's text in code — or
reported as not found in the evidence reviewed. "Not found" never means
"doesn't exist": it is bounded by what the search fetched, and every finding
records whether that was a patent's claims, its abstract, or only a search
snippet.

Quote verification lives here (rather than in the examination preview, which
introduced it) so every stage that quotes a document — novelty, citation
follow-up, re-check, redesign, examination — applies the same rule.
"""
import re
from typing import Literal

from pydantic import BaseModel

MIN_QUOTE_WORDS = 4
# An elided quote ("A ... B") stands for the source passage from A to B.
# Each fragment must be at least this long, and the passage no longer than
# this, so scattered words can't be strung into a quote.
MIN_FRAGMENT_WORDS = 2
MAX_ELIDED_PASSAGE_WORDS = 60
MAX_EVIDENCE_PER_FEATURE = 3

# What text a judgement was made from, strongest first.
EvidenceSource = Literal["claims", "abstract", "snippet"]
# How the document entered the report: the keyword search, or the citation
# follow-up that fetched a document the closest matches point at.
FoundVia = Literal["search", "citation"]


class IdeaFeature(BaseModel):
    id: str  # "F1"
    text: str


class EvidenceSection(BaseModel):
    label: str
    source: EvidenceSource
    text: str
    original_chars: int
    truncated: bool = False


class FeatureEvidence(BaseModel):
    result_id: str
    title: str
    link: str
    quote: str  # verified to occur in the document text
    evidence_source: EvidenceSource
    found_via: FoundVia = "search"
    section: EvidenceSection | None = None


class FeatureFinding(BaseModel):
    id: str
    feature: str
    evidence: list[FeatureEvidence] = []


# --- Quote verification ----------------------------------------------------------

_LOOKALIKES = str.maketrans(
    {
        "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
        "‘": "'", "’": "'", "“": '"', "”": '"', " ": " ",
    }
)


def _normalize(text: str) -> str:
    text = text.translate(_LOOKALIKES).lower()
    return " ".join(text.split())


def quote_is_verified(quote: str, document_text: str) -> bool:
    """The quote must actually occur in the document — modulo case,
    whitespace and typographic punctuation — and be long enough to be
    evidence rather than a coincidental phrase. A trailing ellipsis (models
    like to add one) is ignored."""
    cleaned = _normalize(quote).strip(" .…").strip('"')
    if len(cleaned.split()) < MIN_QUOTE_WORDS:
        return False
    return cleaned in _normalize(document_text)


_ELLIPSIS = re.compile(r"\s*(?:\.{3,}|…)\s*")


def _normalized_with_positions(text: str) -> tuple[str, list[int]]:
    """_normalize(text), plus each normalized character's index in text."""
    chars: list[str] = []
    positions: list[int] = []
    for i, ch in enumerate(text.translate(_LOOKALIKES)):
        if ch.isspace():
            if chars and chars[-1] != " ":
                chars.append(" ")
                positions.append(i)
            continue
        for lowered in ch.lower():
            chars.append(lowered)
            positions.append(i)
    if chars and chars[-1] == " ":
        chars.pop()
        positions.pop()
    return "".join(chars), positions


def _elided_span(fragments: list[str], doc: str) -> tuple[int, int] | None:
    """The shortest span of doc holding every fragment in order."""
    best = None
    start = doc.find(fragments[0])
    while start >= 0:
        end = start + len(fragments[0])
        for fragment in fragments[1:]:
            found = doc.find(fragment, end)
            if found < 0:
                return best  # a later start can't place this fragment either
            end = found + len(fragment)
        if best is None or end - start < best[1] - best[0]:
            best = (start, end)
        start = doc.find(fragments[0], start + 1)
    return best


def locate_quote(quote: str, document_text: str) -> str | None:
    """The exact passage of document_text that the quote stands for, or None.

    Matching follows quote_is_verified. Models also elide ("first draught
    fan (5) ... sent into the drying shed") even when told not to; an elided
    quote resolves to the continuous source passage from its first fragment
    to its last. Either way the returned text is copied from the document,
    never from the model."""
    cleaned = _normalize(quote).strip(" .…").strip('"')
    fragments = [f.strip(' "') for f in _ELLIPSIS.split(cleaned) if f.strip(' "')]
    if not fragments:
        return None
    doc, positions = _normalized_with_positions(document_text)
    if len(fragments) == 1:
        if len(fragments[0].split()) < MIN_QUOTE_WORDS:
            return None
        start = doc.find(fragments[0])
        if start < 0:
            return None
        end = start + len(fragments[0])
    else:
        if any(len(f.split()) < MIN_FRAGMENT_WORDS for f in fragments):
            return None
        span = _elided_span(fragments, doc)
        if span is None:
            return None
        start, end = span
        if not MIN_QUOTE_WORDS <= len(doc[start:end].split()) <= MAX_ELIDED_PASSAGE_WORDS:
            return None
    return document_text[positions[start] : positions[end - 1] + 1]


# --- Document ids from model output ---------------------------------------------


def _id_core(doc_id: str) -> str:
    return "".join(ch for ch in doc_id.lower() if ch.isalnum())


def resolve_document_id(raw_id: str, known_ids: list[str]) -> str | None:
    """Maps an id the model wrote back to the id it was given. Models copy
    "patent/CN205448635U/en" as "patent/CN205448635U en" or drop the
    prefix, and an exact-match lookup then discards every assessment and
    quote for that document. Punctuation and case are ignored; a bare
    publication number resolves only when exactly one known id contains it."""
    if raw_id in known_ids:
        return raw_id
    core = _id_core(raw_id)
    if not core:
        return None
    for known in known_ids:
        if _id_core(known) == core:
            return known
    containing = [k for k in known_ids if core in _id_core(k)]
    return containing[0] if len(containing) == 1 else None


# --- Findings ----------------------------------------------------------------------


def empty_findings(features: list[IdeaFeature]) -> list[FeatureFinding]:
    return [FeatureFinding(id=f.id, feature=f.text) for f in features if f.text.strip()]


def attach_evidence(
    findings: list[FeatureFinding],
    feature_id: str,
    quote: str,
    *,
    result_id: str,
    title: str,
    link: str,
    document_text: str,
    evidence_source: EvidenceSource,
    found_via: FoundVia = "search",
    sections: list[EvidenceSection] | None = None,
) -> bool:
    """Adds the quote to the feature's evidence only if it verifies against
    the document text. The stored quote is the matching passage copied from
    the document (see locate_quote). One quote per document per feature.
    Returns whether it was added."""
    finding = next((f for f in findings if f.id == feature_id.strip().upper()), None)
    # New reports verify against one real section, never a concatenation
    # that could misattribute an abstract passage to a patent claim.
    section = None
    for candidate in sections or []:
        passage = locate_quote(quote, candidate.text)
        if passage:
            section = candidate
            break
    if sections and section is None:
        return False
    if section is None:
        passage = locate_quote(quote, document_text)
    if finding is None or not passage:
        return False
    quote = passage
    if any(e.result_id == result_id for e in finding.evidence):
        return False
    if len(finding.evidence) >= MAX_EVIDENCE_PER_FEATURE:
        return False
    finding.evidence.append(
        FeatureEvidence(
            result_id=result_id,
            title=title,
            link=link,
            quote=quote,
            evidence_source=section.source if section else evidence_source,
            found_via=found_via,
            section=section,
        )
    )
    return True


def headline(findings: list[FeatureFinding], documents_reviewed: int) -> str | None:
    """The report's conclusion in one sentence, built from verified evidence
    only. None when there's no feature breakdown (older reports)."""
    if not findings:
        return None
    found = [f.feature for f in findings if f.evidence]
    missing = [f.feature for f in findings if not f.evidence]
    docs = f"{documents_reviewed} document{'s' if documents_reviewed != 1 else ''} reviewed"
    if not found:
        return f"None of the {len(findings)} features of your idea was found in the {docs}."
    sentence = f"Overlap found in {len(found)} of {len(findings)} features: {'; '.join(found)}."
    if missing:
        sentence += f" Not found in the {docs}: {'; '.join(missing)}."
    else:
        sentence += f" Every feature appears in the {docs}."
    return sentence
