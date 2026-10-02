"""Citation follow-up: the second investigation step.

Citation chasing (app.pipeline.citation_chase) finds documents that several
of the closest matches point at but keyword search never returned. On its
own that's a list of titles. This step follows the strongest of them up the
way a searcher would:

    discovered citation -> fetch its details -> assess it against the idea's
    features -> update the conclusion if the evidence warrants it

"Update the conclusion" is deliberately narrow and deterministic: a
follow-up changes the report only by adding verified evidence for a feature.
When it shows a feature that no searched document did, that feature moves
from "not found" to "found", and the follow-up is recorded as the discovery
that changed the conclusion — so the report can say exactly which citation
did it.

Costs one google_patents_details call per document (capped, default 2) and
one LLM call for all of them together.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, ValidationError, computed_field

from app.llm import complete_json
from app.pipeline.citation_chase import CitationDiscovery, CitationNetwork
from app.pipeline.deepdive import CandidateDetail, fetch_detail
from app.pipeline.evidence import EvidenceSource, FeatureFinding, attach_evidence
from app.pipeline.novelty import CandidateAssessment, NoveltyVerdict

logger = logging.getLogger(__name__)


class CitationFollowUp(BaseModel):
    id: str
    title: str
    link: str
    referenced_by: list[str]
    reason: str  # the discovery's reason: "shared_reference" | "examiner_cited"
    evidence_source: EvidenceSource
    verdict: NoveltyVerdict
    features_found: list[str]  # feature ids this document shows, with verified quotes
    newly_found: list[str]  # of those, the ones no searched document showed
    explanation: str

    @computed_field
    @property
    def changed_conclusion(self) -> bool:
        return bool(self.newly_found)


class FollowUpOutcome(BaseModel):
    followups: list[CitationFollowUp] = []
    details: list[CandidateDetail] = []  # fetched documents, for examined_documents
    assessments: list[CandidateAssessment] = []  # the relevant ones, as candidates
    lookups: int = 0  # google_patents_details calls made


SYSTEM_PROMPT = """You are a patent analyst checking documents found by citation \
chasing against an inventor's idea, strictly from the documents' text. You always \
respond with a single valid JSON object and nothing else."""

PROMPT = """Invention idea:
---
{idea}
---

Its essential features:
{features}

Documents that the closest prior art cites or is cited by (key, title, text):
{documents}

For EACH document, report:
- "verdict": "blocking" (discloses the idea as a whole), "partially_overlapping" \
(discloses some features), or "not_relevant".
- "feature_evidence": for each feature the document's text actually discloses, \
{{"feature": "<feature id, e.g. F2>", "quote": "<sentence or clause from the document, \
COPIED EXACTLY, 5-40 words>"}}. Quotes are checked against the text automatically and \
discarded unless they appear in it word for word — never paraphrase.
- "explanation": one plain sentence on how this document relates to the idea. Say \
"this document", never its key.

Respond with a single JSON object:
{{"documents": [{{"key": "C1", "verdict": "...", "feature_evidence": [], "explanation": "..."}}]}}
"""


class _RawQuote(BaseModel):
    feature: str
    quote: str


class _RawDoc(BaseModel):
    key: str
    verdict: NoveltyVerdict = "not_relevant"
    feature_evidence: list[_RawQuote] = []
    explanation: str = ""


class _RawFollowUps(BaseModel):
    documents: list[_RawDoc]


def select_discoveries(network: CitationNetwork | None, limit: int) -> list[CitationDiscovery]:
    """Strongest first, as citation chasing already ordered them."""
    if network is None or limit <= 0:
        return []
    return network.discoveries[:limit]


def _fetch(discovery: CitationDiscovery) -> CandidateDetail:
    return fetch_detail(discovery.id, "patent", discovery.title, discovery.link)


def apply_followups(
    findings: list[FeatureFinding],
    discoveries: list[CitationDiscovery],
    details: list[CandidateDetail],
    raw: _RawFollowUps,
) -> tuple[list[CitationFollowUp], list[CandidateAssessment]]:
    """Merges verified evidence into `findings` in place and reports what
    each follow-up contributed. A feature counts as newly found only if no
    document had shown it before *any* follow-up was applied, so two
    follow-ups showing the same feature don't both claim the change."""
    found_before = {f.id for f in findings if f.evidence}
    by_key = {d.key.strip().upper(): d for d in raw.documents}
    feature_text = {f.id: f.feature for f in findings}
    followups: list[CitationFollowUp] = []
    assessments: list[CandidateAssessment] = []
    claimed: set[str] = set()

    for i, (discovery, detail) in enumerate(zip(discoveries, details), start=1):
        doc = by_key.get(f"C{i}")
        found: list[str] = []
        if doc is not None:
            for fe in doc.feature_evidence:
                feature_id = fe.feature.strip().upper()
                added = attach_evidence(
                    findings,
                    feature_id,
                    fe.quote,
                    result_id=detail.id,
                    title=detail.title,
                    link=detail.link,
                    document_text=detail.summary_text,
                    evidence_source=detail.evidence_source,
                    found_via="citation",
                    sections=detail.sections,
                )
                if added and feature_id not in found:
                    found.append(feature_id)
        newly = [f for f in found if f not in found_before and f not in claimed]
        claimed.update(newly)
        # With no verified feature evidence, the document can't be called a
        # match however the model labelled it.
        verdict: NoveltyVerdict = doc.verdict if (doc and found) else "not_relevant"
        explanation = (doc.explanation.strip() if doc else "") or (
            "No passage in this document's text could be matched to a feature of your idea."
        )
        followups.append(
            CitationFollowUp(
                id=detail.id,
                title=detail.title,
                link=detail.link,
                referenced_by=discovery.referenced_by,
                reason=discovery.reason,
                evidence_source=detail.evidence_source,
                verdict=verdict,
                features_found=found,
                newly_found=newly,
                explanation=explanation,
            )
        )
        if verdict != "not_relevant":
            assessments.append(
                CandidateAssessment(
                    result_id=detail.id,
                    title=detail.title,
                    link=detail.link,
                    overlapping_elements=[feature_text[f] for f in found],
                    differences=[t for fid, t in feature_text.items() if fid not in found],
                    verdict=verdict,
                    evidence_source=detail.evidence_source,
                    found_via="citation",
                )
            )
    return followups, assessments


def follow_up_citations(
    idea_text: str,
    network: CitationNetwork | None,
    findings: list[FeatureFinding],
    limit: int = 2,
) -> FollowUpOutcome:
    """Never raises: a failed follow-up leaves the report as it was."""
    discoveries = select_discoveries(network, limit)
    if not discoveries or not findings:
        return FollowUpOutcome()

    with ThreadPoolExecutor(max_workers=len(discoveries)) as pool:
        fetched = list(pool.map(_fetch, discoveries))
    pairs = [(d, c) for d, c in zip(discoveries, fetched) if c.summary_text.strip()]
    outcome = FollowUpOutcome(lookups=len(discoveries))
    if not pairs:
        return outcome
    discoveries = [d for d, _ in pairs]
    details = [c for _, c in pairs]

    prompt = PROMPT.format(
        idea=idea_text.strip(),
        features="\n".join(f"- {f.id}: {f.feature}" for f in findings),
        documents="\n\n".join(
            f"[C{i}] {c.title}\n{c.summary_text}" for i, c in enumerate(details, start=1)
        ),
    )
    try:
        raw = _RawFollowUps.model_validate(
            complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.1)
        )
    except (ValueError, ValidationError) as e:
        logger.warning("Citation follow-up assessment failed: %s", e)
        return outcome

    followups, assessments = apply_followups(findings, discoveries, details, raw)
    outcome.followups = followups
    outcome.details = details
    outcome.assessments = assessments
    return outcome
