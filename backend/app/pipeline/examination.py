"""Examination preview: a report's evidence read the way an Indian patent
examiner would read it.

The novelty score says how similar an idea is to what exists. An examiner
asks sharper questions, and this module asks them too:

1. Section 3 screen — is this something the Patents Act excludes outright
   (software per se, farming methods, traditional knowledge, ...)? No amount
   of novelty rescues an excluded idea, and Indian inventors routinely pay
   filing fees before finding that out.
2. Element check — split the idea into its essential technical elements and
   check each one against every examined document. A "disclosed" finding
   counts only if it quotes the document, and the quote is verified against
   the document's actual text in code; an unverifiable quote is discarded,
   never shown.
3. Objections, computed rather than generated — lack of novelty (s. 2(1)(j))
   when one document discloses every element; lack of inventive step
   (s. 2(1)(ja)) when two documents together do. The LLM only reads
   documents; the combination logic is deterministic code, so the same
   evidence always gives the same objections.
4. The novelty core — elements no document discloses: what an application
   would have to be built around.

Deliberately not included: drafting claims. That is a patent agent's job,
and a plausible-looking but wrong claim would do more harm than good.

It is a preview, bounded by what the search found (top documents only,
abstracts and leading claims), and is labelled that way everywhere it shows.
Groq only — no SerpApi calls.
"""
import re
from itertools import combinations
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.llm import complete_json
from app.models import AnalysisResult
from app.pipeline.evidence import quote_is_verified

MAX_DOCUMENTS = 8
MIN_ELEMENTS = 2
MAX_ELEMENTS = 6
MAX_COMBINATIONS_SHOWN = 3

# Section 3 of the Patents Act, 1970: "What are not inventions". The plain
# summaries are fixed here rather than generated, so the law shown to the
# user is never an LLM paraphrase. Only clauses a product or process idea
# could plausibly trip are screened.
SECTION_3: dict[str, tuple[str, str]] = {
    "3(d)": (
        "New form or new use of a known substance",
        "The mere discovery of a new form of a known substance that does not enhance its "
        "known efficacy, of a new property or new use for a known substance, or the mere "
        "use of a known process, machine or apparatus unless it results in a new product "
        "or employs at least one new reactant.",
    ),
    "3(e)": (
        "Mere admixture",
        "A substance obtained by a mere admixture resulting only in the aggregation of the "
        "properties of its components, or a process for producing such a substance.",
    ),
    "3(f)": (
        "Mere arrangement of known devices",
        "The mere arrangement, re-arrangement or duplication of known devices, each "
        "functioning independently of one another in a known way.",
    ),
    "3(h)": ("Method of agriculture or horticulture", "A method of agriculture or horticulture."),
    "3(i)": (
        "Method of medical or veterinary treatment",
        "Any process for the medicinal, surgical, curative, prophylactic, diagnostic, "
        "therapeutic or other treatment of human beings, or a similar treatment of animals.",
    ),
    "3(j)": (
        "Plants and animals",
        "Plants and animals in whole or any part (other than micro-organisms), including "
        "seeds, varieties and species, and essentially biological processes for producing "
        "or propagating them.",
    ),
    "3(k)": (
        "Software, business method or algorithm as such",
        "A mathematical or business method, a computer programme per se, or algorithms.",
    ),
    "3(m)": (
        "Mental act, scheme or game",
        "A mere scheme, rule or method of performing a mental act, or a method of playing a game.",
    ),
    "3(p)": (
        "Traditional knowledge",
        "An invention which, in effect, is traditional knowledge, or an aggregation or "
        "duplication of known properties of traditionally known components.",
    ),
}

CoverageStatus = Literal["disclosed", "partial"]
Outcome = Literal[
    "novelty_objection",  # one document discloses every element
    "inventive_step_objection",  # two documents together do
    "combination_risk",  # only three or more documents together do
    "no_objection_found",  # some element is disclosed nowhere
]
EvidenceBasis = Literal["full_text", "snippets"]


class Element(BaseModel):
    id: str  # "E1"
    text: str


class ExaminedDoc(BaseModel):
    key: str  # "D1"
    id: str
    title: str
    link: str
    source_type: str


class Coverage(BaseModel):
    element: str  # element id
    document: str  # document key
    status: CoverageStatus
    quote: str  # verified to occur in the document text


class InventiveStepObjection(BaseModel):
    documents: list[str]  # two document keys
    same_field: bool  # both share a CPC subclass — a stronger combination


class Section3Flag(BaseModel):
    clause: str
    title: str
    law_summary: str
    risk: Literal["high", "possible"]
    reason: str
    how_to_address: str


class ExaminationPreview(BaseModel):
    outcome: Outcome
    elements: list[Element]
    documents: list[ExaminedDoc]
    coverage: list[Coverage]
    novelty_objections: list[str]  # document keys
    inventive_step_objections: list[InventiveStepObjection]
    uncovered_elements: list[str]  # element ids: the novelty core
    section3_flags: list[Section3Flag]
    evidence_basis: EvidenceBasis
    unverified_quotes_dropped: int


# --- Documents -----------------------------------------------------------------


class _Doc(BaseModel):
    meta: ExaminedDoc
    text: str
    cpc_code: str | None = None
    relevance: float = 0.0


def select_documents(result: AnalysisResult) -> tuple[list[_Doc], EvidenceBasis]:
    """The deep-dived full texts when the report has them. Reports saved
    before those were kept fall back to search snippets (plus the claim
    chart's full text for the closest match) — weaker evidence, and the
    preview says so."""
    ranked = {r.id: r for r in result.ranked_results}
    docs: list[_Doc] = []

    if result.examined_documents:
        basis: EvidenceBasis = "full_text"
        sources = [(d.id, d.title, d.link, d.source_type, d.text) for d in result.examined_documents]
    else:
        basis = "snippets"
        chart = result.claim_chart
        sources = [
            (
                r.id,
                r.title,
                r.link,
                r.source_type,
                chart.candidate_text if chart and chart.candidate_result_id == r.id else r.snippet,
            )
            for r in result.ranked_results
            if r.source_type in ("patent", "scholar")
        ]

    for doc_id, title, link, source_type, text in sources:
        if not text.strip():
            continue
        r = ranked.get(doc_id)
        docs.append(
            _Doc(
                meta=ExaminedDoc(
                    key=f"D{len(docs) + 1}", id=doc_id, title=title, link=link, source_type=source_type
                ),
                text=text,
                cpc_code=r.cpc_code if r else None,
                relevance=r.relevance_score if r else 0.0,
            )
        )
        if len(docs) == MAX_DOCUMENTS:
            break
    return docs, basis


# Quote verification is shared with every stage that quotes a document.


# --- Objection logic (deterministic) ---------------------------------------------


def _subclass(cpc: str | None) -> str | None:
    match = re.match(r"^[A-H]\d{2}[A-Z]", cpc or "")
    return match.group(0) if match else None


def compute_objections(
    elements: list[Element], docs: list[_Doc], coverage: list[Coverage]
) -> tuple[Outcome, list[str], list[InventiveStepObjection], list[str]]:
    all_elements = {e.id for e in elements}
    disclosed: dict[str, set[str]] = {d.meta.key: set() for d in docs}
    for c in coverage:
        if c.status == "disclosed":
            disclosed[c.document].add(c.element)

    anticipating = [key for key, found in disclosed.items() if found >= all_elements]

    by_key = {d.meta.key: d for d in docs}
    pairs: list[InventiveStepObjection] = []
    candidates = [k for k in disclosed if k not in anticipating and disclosed[k]]
    for a, b in combinations(candidates, 2):
        if disclosed[a] | disclosed[b] >= all_elements:
            field_a, field_b = _subclass(by_key[a].cpc_code), _subclass(by_key[b].cpc_code)
            pairs.append(
                InventiveStepObjection(
                    documents=[a, b], same_field=field_a is not None and field_a == field_b
                )
            )
    # Same-field combinations first (an examiner's easiest argument), then
    # the most relevant documents.
    pairs.sort(
        key=lambda p: (p.same_field, sum(by_key[k].relevance for k in p.documents)), reverse=True
    )

    covered_anywhere = set().union(*disclosed.values()) if disclosed else set()
    uncovered = [e.id for e in elements if e.id not in covered_anywhere]

    if anticipating:
        outcome: Outcome = "novelty_objection"
    elif pairs:
        outcome = "inventive_step_objection"
    elif not uncovered:
        outcome = "combination_risk"
    else:
        outcome = "no_objection_found"
    return outcome, anticipating, pairs[:MAX_COMBINATIONS_SHOWN], uncovered


# --- LLM steps -------------------------------------------------------------------

SCREEN_SYSTEM = """You are an experienced Indian patent examiner. You always respond \
with a single valid JSON object and nothing else."""

SCREEN_PROMPT = """Invention:
---
{idea_text}
---

1. Split the invention into its {min_e}-{max_e} essential technical elements: the \
features that together define it, each a short phrase in plain English. Do not list \
benefits or purposes as elements, and do not split one feature into several.

2. Screen it against Section 3 of the Indian Patents Act, 1970. The clauses to consider:
{clauses}

Flag ONLY clauses that plausibly apply to this invention as described. For each flag give:
- "clause": exactly as written above, e.g. "3(k)"
- "risk": "high" if the invention as described clearly falls within the clause, \
"possible" if it could depending on how it is claimed
- "reason": one sentence, specific to this invention
- "how_to_address": one sentence of practical direction (e.g. for 3(k): a software \
invention can be patentable in India when claimed as producing a technical effect or \
technical contribution, such as controlling hardware)
Most mechanical and electrical devices trip no clause: return an empty list then. \
In particular, flag 3(f) ONLY when the parts keep working independently of each other \
in their usual way, with no new working interaction between them. Nearly every \
invention is built from known parts; that alone is never a 3(f) issue.

Respond with a single JSON object:
{{"elements": ["...", "..."], "section3": [{{"clause": "3(k)", "risk": "possible", \
"reason": "...", "how_to_address": "..."}}]}}
"""

COVERAGE_PROMPT = """Invention elements:
{elements_block}

Prior-art documents (key, title, text):
{documents_block}

For every element and every document, decide whether the document's text discloses \
that element:
- "disclosed": the text itself clearly describes this element (not merely something \
in the same field, and not by your inference beyond the text)
- "partial": the text describes something similar but narrower, broader, or different \
in an important way
List ONLY disclosed and partial findings; omit everything else.

Each finding MUST include "quote": the single sentence or clause from that document's \
text that shows it, COPIED EXACTLY, 5-40 words. Findings are checked against the text \
automatically and discarded if the quote does not appear in it word for word, so never \
paraphrase.

Respond with a single JSON object:
{{"coverage": [{{"element": "E1", "document": "D2", "status": "disclosed", "quote": "..."}}]}}
"""


class _RawSection3(BaseModel):
    clause: str
    risk: Literal["high", "possible"]
    reason: str
    how_to_address: str


class _RawScreen(BaseModel):
    elements: list[str]
    section3: list[_RawSection3] = []


class _RawCoverage(BaseModel):
    element: str
    document: str
    status: CoverageStatus
    quote: str


class _RawCoverageList(BaseModel):
    coverage: list[_RawCoverage] = []


def _call(prompt: str, model: type[BaseModel], temperature: float) -> BaseModel:
    last_error: Exception | None = None
    for _ in range(2):
        try:
            return model.model_validate(
                complete_json(prompt, system=SCREEN_SYSTEM, temperature=temperature)
            )
        except (ValueError, ValidationError) as e:
            last_error = e
    raise ValueError(f"Examination preview failed: {last_error}")


def _screen(idea_text: str) -> tuple[list[Element], list[Section3Flag]]:
    clauses = "\n".join(f"- {c}: {summary}" for c, (_, summary) in SECTION_3.items())
    raw = _call(
        SCREEN_PROMPT.format(
            idea_text=idea_text, min_e=MIN_ELEMENTS + 1, max_e=MAX_ELEMENTS, clauses=clauses
        ),
        _RawScreen,
        temperature=0.1,
    )
    texts = [t.strip() for t in raw.elements if t.strip()][:MAX_ELEMENTS]
    if len(texts) < MIN_ELEMENTS:
        raise ValueError("Examination preview: could not identify the invention's elements")
    elements = [Element(id=f"E{i}", text=t) for i, t in enumerate(texts, start=1)]

    flags: list[Section3Flag] = []
    seen: set[str] = set()
    for f in raw.section3:
        clause = f.clause.strip().replace(" ", "")
        if clause not in SECTION_3 or clause in seen:  # unknown clause: never shown
            continue
        seen.add(clause)
        title, summary = SECTION_3[clause]
        flags.append(
            Section3Flag(
                clause=clause,
                title=title,
                law_summary=summary,
                risk=f.risk,
                reason=f.reason.strip(),
                how_to_address=f.how_to_address.strip(),
            )
        )
    flags.sort(key=lambda f: f.risk != "high")
    return elements, flags


def _coverage(elements: list[Element], docs: list[_Doc]) -> tuple[list[Coverage], int]:
    raw = _call(
        COVERAGE_PROMPT.format(
            elements_block="\n".join(f"{e.id}: {e.text}" for e in elements),
            documents_block="\n\n".join(
                f"[{d.meta.key}] {d.meta.title}\n{d.text}" for d in docs
            ),
        ),
        _RawCoverageList,
        temperature=0.1,
    )
    return verify_coverage(raw.coverage, elements, docs)


def verify_coverage(
    raw: list[_RawCoverage], elements: list[Element], docs: list[_Doc]
) -> tuple[list[Coverage], int]:
    """Keep findings whose element and document exist and whose quote is
    really in the document. One finding per element/document pair — a
    'disclosed' beats a 'partial' for the same pair."""
    element_ids = {e.id for e in elements}
    text_by_key = {d.meta.key: d.text for d in docs}
    kept: dict[tuple[str, str], Coverage] = {}
    dropped = 0
    for c in raw:
        element, document = c.element.strip().upper(), c.document.strip().upper()
        if element not in element_ids or document not in text_by_key:
            continue
        if not quote_is_verified(c.quote, text_by_key[document]):
            dropped += 1
            continue
        pair = (element, document)
        if pair in kept and kept[pair].status == "disclosed":
            continue
        kept[pair] = Coverage(
            element=element, document=document, status=c.status, quote=c.quote.strip()
        )
    return list(kept.values()), dropped


def preview_examination(result: AnalysisResult) -> ExaminationPreview:
    """Raises ValueError if the model can't produce usable output."""
    docs, basis = select_documents(result)
    elements, flags = _screen(result.idea_text)
    coverage, dropped = _coverage(elements, docs) if docs else ([], 0)
    outcome, anticipating, pairs, uncovered = compute_objections(elements, docs, coverage)
    return ExaminationPreview(
        outcome=outcome,
        elements=elements,
        documents=[d.meta for d in docs],
        coverage=coverage,
        novelty_objections=anticipating,
        inventive_step_objections=pairs,
        uncovered_elements=uncovered,
        section3_flags=flags,
        evidence_basis=basis,
        unverified_quotes_dropped=dropped,
    )
