"""Evidence-backed re-check: did the change actually move the idea away from
the patents that mattered?

"Apply & re-check" re-runs the whole pipeline on the revised idea. Comparing
the two novelty-confidence numbers alone is weak evidence — the number comes
from a model, and a new search can simply rank the old closest matches lower,
making an overlap vanish from view without being resolved.

So the re-check keeps the ORIGINAL closest matches in the comparison and
tests the revised idea against their saved texts (no new API calls):

- Is the applied change already in this document? Decided by evidence: only
  a quote from the document, verified against its text, can say "yes". No
  verifiable quote means the document doesn't show the change.
- What does the revised idea still share with it? Each shared feature must
  also carry a verified quote.

It then lists the close matches the revised idea's own search surfaced that
the original search hadn't — a change can open new overlaps as well as close
old ones.
"""
import logging
import re

from pydantic import BaseModel, ValidationError

from app.llm import complete_json
from app.models import (
    AnalysisResult,
    NewMatch,
    OriginalMatchCheck,
    RecheckComparison,
    SharedFeature,
)
from app.pipeline.examination import quote_is_verified, select_documents
from app.pipeline.novelty import CandidateAssessment

logger = logging.getLogger(__name__)

MAX_ORIGINAL_MATCHES = 3
MAX_SHARED_FEATURES = 3
SEVERITY = {"blocking": 0, "partially_overlapping": 1, "not_relevant": 2}
# The reader never sees the D1/D2 keys used in the prompt.
_DOC_KEY = re.compile(r"\b(?:from |in |than )?D\d+\b")


SYSTEM_PROMPT = """You compare a revised invention against prior-art documents, \
strictly from the documents' text. You always respond with a single valid JSON object \
and nothing else."""

PROMPT = """Revised invention:
---
{idea}
---

The inventor just added this change to distinguish it from earlier matches:
"{change}"

Documents (key, title, text):
{documents}

For EACH document, report:
- "change_quote": if the document's text ALREADY describes the added change, the \
sentence that shows it, COPIED EXACTLY (5-40 words). Otherwise "".
- "still_shared": up to {max_shared} features of the revised invention that this \
document still discloses, each {{"feature": "<short phrase>", "quote": "<sentence from \
the document, COPIED EXACTLY, 5-40 words>"}}. Empty list if none.
- "explanation": one plain sentence on whether the change distinguishes the invention \
from this document. Say "this document", never its key.

Quotes are checked against the document text automatically and discarded if they do \
not appear in it word for word — never paraphrase.

Respond with a single JSON object:
{{"documents": [{{"key": "D1", "change_quote": "", "still_shared": [], "explanation": "..."}}]}}
"""


class _RawShared(BaseModel):
    feature: str
    quote: str


class _RawDocCheck(BaseModel):
    key: str
    change_quote: str = ""
    still_shared: list[_RawShared] = []
    explanation: str = ""


class _RawChecks(BaseModel):
    documents: list[_RawDocCheck]


def original_closest(parent: AnalysisResult) -> list[CandidateAssessment]:
    """The parent report's real matches, most severe first."""
    relevance = {r.id: r.relevance_score for r in parent.ranked_results}
    matches = [a for a in parent.candidate_assessments if a.verdict != "not_relevant"]
    matches.sort(key=lambda a: (SEVERITY[a.verdict], -relevance.get(a.result_id, 0.0)))
    return matches[:MAX_ORIGINAL_MATCHES]


def new_close_matches(parent: AnalysisResult, revised: AnalysisResult) -> list[NewMatch]:
    """Close matches in the revised run that the original search never
    returned at all."""
    seen = {r.id for r in parent.ranked_results}
    source_type = {r.id: r.source_type for r in revised.ranked_results}
    relevance = {r.id: r.relevance_score for r in revised.ranked_results}
    matches = [
        a for a in revised.candidate_assessments
        if a.verdict != "not_relevant" and a.result_id not in seen
    ]
    matches.sort(key=lambda a: (SEVERITY[a.verdict], -relevance.get(a.result_id, 0.0)))
    return [
        NewMatch(
            id=a.result_id,
            title=a.title,
            link=a.link,
            verdict=a.verdict,
            source_type=source_type.get(a.result_id, "patent"),
        )
        for a in matches
    ]


def _without_keys(text: str) -> str:
    """Models mention document keys despite instructions; rewrite them."""
    cleaned = _DOC_KEY.sub(
        lambda m: (m.group(0).split()[0] + " this document") if " " in m.group(0) else "this document",
        text.strip(),
    )
    return re.sub(r"\s{2,}", " ", cleaned)


def build_checks(
    originals: list[CandidateAssessment], texts: dict[str, str], raw: _RawChecks
) -> list[OriginalMatchCheck]:
    """Turn the model's claims into checks that only assert what verified
    quotes support. A document the model skipped is reported with no
    evidence either way rather than dropped."""
    by_key = {c.key.strip().upper(): c for c in raw.documents}
    checks = []
    for i, original in enumerate(originals, start=1):
        text = texts.get(original.result_id, "")
        found = by_key.get(f"D{i}")
        change_quote = found.change_quote.strip() if found else ""
        change_found = bool(change_quote) and quote_is_verified(change_quote, text)
        shared = [
            SharedFeature(feature=s.feature.strip(), quote=s.quote.strip())
            for s in (found.still_shared if found else [])
            if s.feature.strip() and quote_is_verified(s.quote, text)
        ][:MAX_SHARED_FEATURES]
        checks.append(
            OriginalMatchCheck(
                id=original.result_id,
                title=original.title,
                link=original.link,
                verdict_before=original.verdict,
                change_found_in_document=change_found,
                change_quote=change_quote if change_found else None,
                still_shared=shared,
                explanation=_without_keys(found.explanation if found else "")
                or "No evidence either way was found in this document's text.",
            )
        )
    return checks


def compare_recheck(
    parent: AnalysisResult,
    parent_report_id: str,
    revised: AnalysisResult,
    applied_change: str,
) -> RecheckComparison | None:
    """None when there's nothing to compare or the model fails — the UI then
    falls back to the plain before/after confidence."""
    originals = original_closest(parent)
    docs, basis = select_documents(parent)
    texts = {d.meta.id: d.text for d in docs}
    originals = [o for o in originals if texts.get(o.result_id, "").strip()]

    checks: list[OriginalMatchCheck] = []
    if originals:
        prompt = PROMPT.format(
            idea=revised.idea_text,
            change=applied_change,
            max_shared=MAX_SHARED_FEATURES,
            documents="\n\n".join(
                f"[D{i}] {o.title}\n{texts[o.result_id]}" for i, o in enumerate(originals, start=1)
            ),
        )
        try:
            raw = _RawChecks.model_validate(
                complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.1)
            )
        except (ValueError, ValidationError) as e:
            logger.warning("Re-check comparison failed: %s", e)
            return None
        checks = build_checks(originals, texts, raw)

    return RecheckComparison(
        parent_report_id=parent_report_id,
        applied_change=applied_change,
        confidence_before=parent.overall_novelty_confidence,
        original_matches=checks,
        new_matches=new_close_matches(parent, revised),
        evidence_basis=basis,
    )
