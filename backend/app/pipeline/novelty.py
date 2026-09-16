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
"""
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.llm import complete_json
from app.pipeline.deepdive import CandidateDetail
from app.pipeline.rank import RankedResult

NoveltyVerdict = Literal["blocking", "partially_overlapping", "not_relevant"]


class CandidateAssessment(BaseModel):
    result_id: str
    title: str
    link: str
    overlapping_elements: list[str]
    differences: list[str]
    verdict: NoveltyVerdict


class Citation(BaseModel):
    claim: str
    result_id: str
    title: str
    link: str


class NoveltyAssessment(BaseModel):
    candidate_assessments: list[CandidateAssessment]
    overall_novelty_confidence: float
    differentiation_suggestions: list[str]
    citations: list[Citation]


class _RawCandidateAssessment(BaseModel):
    result_id: str
    overlapping_elements: list[str]
    differences: list[str]
    verdict: NoveltyVerdict


class _RawCitation(BaseModel):
    claim: str
    result_id: str


class _RawNoveltyAssessment(BaseModel):
    candidate_assessments: list[_RawCandidateAssessment]
    overall_novelty_confidence: float
    differentiation_suggestions: list[str]
    citations: list[_RawCitation]


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
1. For EVERY prior art candidate listed above, produce an assessment with:
   - "result_id": the exact id string from the candidate list
   - "overlapping_elements": specific technical elements shared with the idea (list of \
short phrases, empty list if none)
   - "differences": specific technical elements where the idea differs (list of short \
phrases, empty list if none)
   - "verdict": one of "blocking" (this prior art likely blocks patentability as-is), \
"partially_overlapping" (shares meaningful elements but idea has distinguishing \
features), or "not_relevant" (not a real technical match)
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

Respond with a single JSON object of this exact shape:
{{
  "candidate_assessments": [
    {{"result_id": "...", "overlapping_elements": ["..."], "differences": ["..."], "verdict": "..."}}
  ],
  "overall_novelty_confidence": 0.0,
  "differentiation_suggestions": ["..."],
  "citations": [
    {{"claim": "...", "result_id": "..."}}
  ]
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
    raw_assessments: list[_RawCandidateAssessment], lookup: dict[str, tuple[str, str]]
) -> list[CandidateAssessment]:
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
            )
        )
    return resolved


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
            raw = complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.2)
            parsed = _RawNoveltyAssessment.model_validate(raw)
            return NoveltyAssessment(
                candidate_assessments=_resolve_assessments(parsed.candidate_assessments, lookup),
                overall_novelty_confidence=max(0.0, min(1.0, parsed.overall_novelty_confidence)),
                differentiation_suggestions=parsed.differentiation_suggestions,
                citations=_resolve_citations(parsed.citations, lookup),
            )
        except (ValueError, ValidationError) as e:
            last_error = e
            continue

    raise ValueError(f"Novelty assessment failed after {max_retries + 1} attempts: {last_error}")
