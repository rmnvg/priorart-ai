"""Stage 1.5: Novelty Verdict + Differentiation Suggestions.

One LLM call, richer prompt: for each deep-dived candidate (patent/scholar),
get overlapping elements / differences / a verdict, then in the same
response synthesize an overall novelty confidence and concrete
differentiation suggestions. Top commercial/product results are included as
lightweight market-awareness context (no claims to compare, so no per-item
verdict) so the synthesis can note "this already exists as product X."

The LLM is only asked to name which result_id a claim/assessment refers to —
we resolve the actual link/title server-side from the known candidate list,
rather than trusting the model to copy URLs verbatim.

The same call splits the idea into its essential features and, for each
candidate, quotes the passage that shows each feature it discloses. Those
quotes are verified against the candidate's text in code (see
app.pipeline.evidence); only verified ones become the feature findings the
report leads with. The model's overall confidence number is kept for
compatibility but is no longer the headline: it is an estimate, not a
calibrated probability.
"""
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.llm import complete_json
from app.pipeline.deepdive import CandidateDetail
from app.pipeline.evidence import (
    EvidenceSource,
    FeatureFinding,
    IdeaFeature,
    attach_evidence,
    empty_findings,
)
from app.pipeline.rank import RankedResult

NoveltyVerdict = Literal["blocking", "partially_overlapping", "not_relevant"]


class CandidateAssessment(BaseModel):
    result_id: str
    title: str
    link: str
    overlapping_elements: list[str]
    differences: list[str]
    verdict: NoveltyVerdict
    # What the verdict was judged from; None on reports saved before it was
    # recorded.
    evidence_source: EvidenceSource | None = None
    found_via: Literal["search", "citation"] = "search"


class Citation(BaseModel):
    claim: str
    result_id: str
    title: str
    link: str


class ClaimChartPair(BaseModel):
    concept: str
    idea_span: str
    candidate_span: str


class NoveltyAssessment(BaseModel):
    candidate_assessments: list[CandidateAssessment]
    overall_novelty_confidence: float
    differentiation_suggestions: list[str]
    citations: list[Citation]
    claim_chart_pairs: list[ClaimChartPair]
    plain_summary: str = ""
    feature_findings: list[FeatureFinding] = []


class _RawFeatureQuote(BaseModel):
    feature: str
    quote: str


class _RawCandidateAssessment(BaseModel):
    result_id: str
    overlapping_elements: list[str]
    differences: list[str]
    verdict: NoveltyVerdict
    feature_evidence: list[_RawFeatureQuote] = []


class _RawCitation(BaseModel):
    claim: str
    result_id: str


class _RawNoveltyAssessment(BaseModel):
    candidate_assessments: list[_RawCandidateAssessment]
    overall_novelty_confidence: float
    differentiation_suggestions: list[str]
    citations: list[_RawCitation]
    claim_chart_pairs: list[ClaimChartPair] = []
    plain_summary: str = ""
    idea_features: list[IdeaFeature] = []


MIN_FEATURES = 2
MAX_FEATURES = 6

SYSTEM_PROMPT = """You are a patent analyst assessing the novelty of an inventor's idea \
against real prior art search results. You always respond with a single valid JSON \
object and nothing else. Be specific and technical, not generic — reference actual \
technical elements from the idea and from each candidate's summary."""

USER_PROMPT_TEMPLATE = """Invention idea:
---
{idea_text}
---

Prior art candidates found (patents and academic papers, with condensed claims/abstract \
or concepts). Refer to each one ONLY by its exact "id" field, never by title:
{candidates_block}

Existing commercial products found in a market search (lighter-weight context, no \
claims — use these to inform overall novelty/market context, not per-candidate \
verdicts):
{market_block}

Do the following:
0. Produce "idea_features": the 3-6 essential technical features of the invention idea, \
each {{"id": "F1", "text": "<short phrase>"}} (ids F1, F2, ...). A feature is one part, \
mechanism or property the idea needs — not a benefit or a goal.
1. For EVERY prior art candidate listed above, produce an assessment with:
   - "result_id": the exact id string from the candidate list
   - "overlapping_elements": specific technical elements shared with the idea (list of \
short phrases, empty list if none)
   - "differences": specific technical elements where the idea differs (list of short \
phrases, empty list if none)
   - "verdict": one of "blocking" (this prior art likely blocks patentability as-is), \
"partially_overlapping" (shares meaningful elements but idea has distinguishing \
features), or "not_relevant" (not a real technical match)
   - "feature_evidence": for each idea feature this candidate's summary text actually \
discloses, {{"feature": "<feature id, e.g. F2>", "quote": "<sentence or clause from \
the candidate's summary, COPIED EXACTLY, 5-40 words>"}}. Quotes are checked against the \
summary text automatically and discarded unless they appear in it word for word, so \
never paraphrase. Omit features this candidate does not disclose.
2. Produce ONE overall "overall_novelty_confidence": a float 0.0-1.0 for how novel the \
idea is overall, synthesized across ALL candidates and the market context (1.0 = highly \
novel/no meaningful prior art found, 0.0 = already fully anticipated).
3. Produce "differentiation_suggestions": a list of concrete, specific changes or \
additions the inventor could make to their idea to distinguish it from the closest \
matches found (reference specific technical elements from the closest candidates, not \
generic advice like "make it more innovative").
4. Produce "citations": ONE citation per candidate assessment (pick its single most \
important overlapping element or difference) plus ONE citation per differentiation \
suggestion that was inspired by a specific candidate — not one per individual bullet \
point. Each entry is {{"claim": "<short paraphrase of the claim>", "result_id": \
"<id it's based on>"}}. Use ids from the candidate or market list only. Keep the total \
citation count roughly equal to the number of candidates plus suggestions, not larger.
5. Produce "claim_chart_pairs": a patent "claim chart" comparing the idea specifically \
against the FIRST candidate listed above (the closest match). Give 3-6 pairs, each \
{{"concept": "<short label for the shared technical concept>", "idea_span": \
"<verbatim excerpt, 3-12 words, COPIED EXACTLY from the invention idea text above>", \
"candidate_span": "<verbatim excerpt, 3-12 words, COPIED EXACTLY from that candidate's \
summary text>"}}. Both spans MUST be exact substrings (same words, same order, same \
casing) of their source text — do not paraphrase or summarize them, they will be \
located and highlighted by exact text match. If you cannot find genuine overlapping \
concepts with real verbatim spans, return an empty list rather than inventing spans \
that don't exist in the source text.
6. Produce "plain_summary": 3-4 short sentences addressed directly to the inventor \
("you"), in plain everyday language with no patent jargon: what already exists that is \
closest to their idea, what about their idea looks genuinely different (if anything), and \
the single most useful next step. Mention a specific closest match by what it does, not \
by its patent number.

Respond with a single JSON object of this exact shape:
{{
  "idea_features": [{{"id": "F1", "text": "..."}}],
  "candidate_assessments": [
    {{"result_id": "...", "overlapping_elements": ["..."], "differences": ["..."], "verdict": "...", \
"feature_evidence": [{{"feature": "F1", "quote": "..."}}]}}
  ],
  "overall_novelty_confidence": 0.0,
  "differentiation_suggestions": ["..."],
  "citations": [
    {{"claim": "...", "result_id": "..."}}
  ],
  "claim_chart_pairs": [
    {{"concept": "...", "idea_span": "...", "candidate_span": "..."}}
  ],
  "plain_summary": "..."
}}
"""


def _format_candidates_block(candidates: list[CandidateDetail]) -> str:
    lines = []
    for c in candidates:
        lines.append(
            f'- id: "{c.id}"\n'
            f'  type: {c.source_type}\n'
            f'  title: {c.title}\n'
            f'  summary: {c.summary_text}\n'
            f'  keywords: {", ".join(c.prior_art_keywords) or "none"}'
        )
    return "\n".join(lines) if lines else "(none found)"


def _format_market_block(products: list[RankedResult]) -> str:
    lines = []
    for p in products:
        lines.append(f'- id: "{p.id}"\n  title: {p.title}\n  snippet: {p.snippet}')
    return "\n".join(lines) if lines else "(none found)"


def _resolve_citations(
    raw_citations: list[_RawCitation], lookup: dict[str, tuple[str, str]]
) -> list[Citation]:
    resolved = []
    for rc in raw_citations:
        if rc.result_id not in lookup:
            continue
        title, link = lookup[rc.result_id]
        resolved.append(Citation(claim=rc.claim, result_id=rc.result_id, title=title, link=link))
    return resolved


def _resolve_assessments(
    raw_assessments: list[_RawCandidateAssessment],
    lookup: dict[str, tuple[str, str]],
    sources: dict[str, EvidenceSource] | None = None,
) -> list[CandidateAssessment]:
    sources = sources or {}
    resolved = []
    for ra in raw_assessments:
        if ra.result_id not in lookup:
            continue
        title, link = lookup[ra.result_id]
        resolved.append(
            CandidateAssessment(
                result_id=ra.result_id,
                title=title,
                link=link,
                overlapping_elements=ra.overlapping_elements,
                differences=ra.differences,
                verdict=ra.verdict,
                evidence_source=sources.get(ra.result_id),
            )
        )
    return resolved


def build_feature_findings(
    features: list[IdeaFeature],
    raw_assessments: list[_RawCandidateAssessment],
    candidates: list[CandidateDetail],
) -> list[FeatureFinding]:
    """Each feature with the verified passages that show it, in candidate
    ranking order. Empty when the model gave too few features to be a
    meaningful breakdown — the UI then falls back to the overall verdict."""
    features = [f for f in features if f.text.strip()][:MAX_FEATURES]
    if len(features) < MIN_FEATURES:
        return []
    # Renumber so ids are always F1..Fn, whatever the model used.
    renumber = {f.id.strip().upper(): f"F{i}" for i, f in enumerate(features, start=1)}
    findings = empty_findings(
        [IdeaFeature(id=f"F{i}", text=f.text.strip()) for i, f in enumerate(features, start=1)]
    )
    by_id = {ra.result_id: ra for ra in raw_assessments}
    for c in candidates:
        ra = by_id.get(c.id)
        if ra is None or ra.verdict == "not_relevant":
            continue
        for fe in ra.feature_evidence:
            feature_id = renumber.get(fe.feature.strip().upper())
            if feature_id is None:
                continue
            attach_evidence(
                findings,
                feature_id,
                fe.quote,
                result_id=c.id,
                title=c.title,
                link=c.link,
                document_text=c.summary_text,
                evidence_source=c.evidence_source,
            )
    return findings


def assess_novelty(
    idea_text: str,
    candidates: list[CandidateDetail],
    market_context: list[RankedResult] | None = None,
    max_retries: int = 1,
) -> NoveltyAssessment:
    market_context = market_context or []

    lookup: dict[str, tuple[str, str]] = {c.id: (c.title, c.link) for c in candidates}
    lookup.update({p.id: (p.title, p.link) for p in market_context})

    prompt = USER_PROMPT_TEMPLATE.format(
        idea_text=idea_text.strip(),
        candidates_block=_format_candidates_block(candidates),
        market_block=_format_market_block(market_context),
    )

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        try:
            # Lower than the query-generation stage's temperature: this call
            # also has to copy claim-chart spans verbatim, and lower
            # temperature measurably improves exact-copy fidelity without
            # hurting verdict/suggestion quality.
            raw = complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.1)
            parsed = _RawNoveltyAssessment.model_validate(raw)
            return NoveltyAssessment(
                candidate_assessments=_resolve_assessments(
                    parsed.candidate_assessments,
                    lookup,
                    {c.id: c.evidence_source for c in candidates},
                ),
                overall_novelty_confidence=max(0.0, min(1.0, parsed.overall_novelty_confidence)),
                differentiation_suggestions=parsed.differentiation_suggestions,
                citations=_resolve_citations(parsed.citations, lookup),
                claim_chart_pairs=parsed.claim_chart_pairs,
                plain_summary=parsed.plain_summary.strip(),
                feature_findings=build_feature_findings(
                    parsed.idea_features, parsed.candidate_assessments, candidates
                ),
            )
        except (ValueError, ValidationError) as e:
            last_error = e
            continue

    raise ValueError(f"Novelty assessment failed after {max_retries + 1} attempts: {last_error}")
