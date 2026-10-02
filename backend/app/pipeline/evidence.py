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
from typing import Literal

from pydantic import BaseModel

MIN_QUOTE_WORDS = 4
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
    the document text. One quote per document per feature. Returns whether
    it was added."""
    finding = next((f for f in findings if f.id == feature_id.strip().upper()), None)
    quote = quote.strip()
    # New reports verify against one real section, never a concatenation
    # that could misattribute an abstract passage to a patent claim.
    section = next((s for s in sections or [] if quote_is_verified(quote, s.text)), None)
    if sections and section is None:
        return False
    if finding is None or not quote_is_verified(quote, section.text if section else document_text):
        return False
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
