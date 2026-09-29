"""Constrained redesign: alternative designs that keep what the inventor
won't give up, respect the limits they work within, and step away from a
specific mechanism the closest matches already disclose.

The differentiation suggestions in a report are one-line nudges. An inventor
facing a close match needs more: "I must keep the clay body, it has to work
without electricity, and it has to cost under ₹2,000 — what can I build?"
This module answers that with three alternatives, each tied to evidence:

- The features come from the idea itself (the examination preview's
  elements when it has been run, so both views talk about the same parts).
  The inventor locks the ones that must stay.
- Every alternative names the overlap it moves away from and quotes the
  passage in the matching document that shows it. The quote is verified
  against the document's text in code, exactly as in the re-check and the
  examination preview; an unverifiable quote is dropped, never shown.
- Whether an alternative keeps each locked feature is checked against the
  lock list, and one that doesn't claim to keep them all says so.

What this module does not do is validate the designs. Cost and performance
constraints are design targets the model reasons toward, not measurements,
and a proposed design has not been searched. The UI labels each one a
hypothesis until the inventor re-checks it ("Re-check this design" runs the
full pipeline plus the evidence comparison against the original closest
matches). Groq only — no SerpApi calls.
"""
import hashlib
import json
import re
from typing import Annotated

from pydantic import BaseModel, Field, ValidationError

from app.llm import complete_json
from app.models import AnalysisResult
from app.pipeline.examination import EvidenceBasis, quote_is_verified, select_documents
from app.pipeline.recheck import original_closest

ALTERNATIVES = 3
MIN_FEATURES = 2
MAX_FEATURES = 6
MAX_CONSTRAINTS = 6
MAX_CONSTRAINT_LENGTH = 120
MAX_AVOIDS = 2
MAX_COST_INR = 100_000_000

_DOC_KEY = re.compile(r"\[?\bD(\d+)\b\]?")


class Feature(BaseModel):
    id: str  # "E1"
    text: str


class FeatureList(BaseModel):
    features: list[Feature]


class RedesignBrief(BaseModel):
    """What the inventor asked for. Validated at the API boundary."""
    locked_features: list[Annotated[str, Field(max_length=8)]] = Field(default=[], max_length=MAX_FEATURES)
    constraints: list[Annotated[str, Field(max_length=MAX_CONSTRAINT_LENGTH)]] = Field(
        default=[], max_length=MAX_CONSTRAINTS
    )
    cost_target_inr: int | None = Field(default=None, gt=0, le=MAX_COST_INR)


class MatchRef(BaseModel):
    id: str
    title: str
    link: str


class AvoidedOverlap(BaseModel):
    document_id: str
    title: str
    link: str
    mechanism: str  # what the document does that this design no longer does
    quote: str  # verified against the document text


class ConstraintNote(BaseModel):
    constraint: str
    approach: str  # how the design aims to meet it — a target, not a result


class DesignAlternative(BaseModel):
    title: str
    how_it_works: str
    what_changes: str
    keeps: list[str]  # locked feature ids the design says it keeps
    drops_locked: list[str]  # locked feature ids it doesn't say it keeps
    constraint_notes: list[ConstraintNote]
    avoids: list[AvoidedOverlap]
    # English, for the re-check run: the full revised idea, and the change
    # in one sentence (the re-check's "applied change").
    revised_idea: str
    change_summary: str


class RedesignResult(BaseModel):
    features: list[Feature]
    locked_features: list[str]
    constraints: list[str]
    alternatives: list[DesignAlternative]
    matches_considered: list[MatchRef]
    evidence_basis: EvidenceBasis
    unverified_quotes_dropped: int
    language_name: str = "English"


# --- Features ------------------------------------------------------------------

SYSTEM_PROMPT = """You are a product designer and patent analyst helping an independent \
inventor. You always respond with a single valid JSON object and nothing else."""

FEATURES_PROMPT = """Invention:
---
{idea_text}
---

Split this invention into its {min_f}-{max_f} essential technical features: the parts or \
steps that together define it, each a short phrase in plain English. Do not list benefits \
or purposes, and do not split one feature into several.

Respond with a single JSON object:
{{"features": ["...", "..."]}}
"""


class _RawFeatures(BaseModel):
    features: list[str]


def features_from_texts(texts: list[str]) -> list[Feature]:
    cleaned: list[str] = []
    for t in texts:
        t = " ".join(t.split())
        if t and t.lower() not in {c.lower() for c in cleaned}:
            cleaned.append(t)
    return [Feature(id=f"E{i}", text=t) for i, t in enumerate(cleaned[:MAX_FEATURES], start=1)]


def extract_features(idea_text: str) -> FeatureList:
    """Raises ValueError if the model can't split the idea."""
    last_error: Exception | None = None
    for _ in range(2):
        try:
            raw = _RawFeatures.model_validate(
                complete_json(
                    FEATURES_PROMPT.format(
                        idea_text=idea_text, min_f=MIN_FEATURES + 1, max_f=MAX_FEATURES
                    ),
                    system=SYSTEM_PROMPT,
                    temperature=0.1,
                )
            )
        except (ValueError, ValidationError) as e:
            last_error = e
            continue
        features = features_from_texts(raw.features)
        if len(features) >= MIN_FEATURES:
            return FeatureList(features=features)
        last_error = ValueError("too few features")
    raise ValueError(f"Feature extraction failed: {last_error}")


# --- Brief ---------------------------------------------------------------------


def normalize_brief(brief: RedesignBrief, features: list[Feature]) -> tuple[list[str], list[str]]:
    """The locked feature ids that exist (in feature order), and the
    constraints as the model and the UI will show them: trimmed, deduped,
    with the cost target written out as one of them."""
    requested = {f.strip().upper() for f in brief.locked_features}
    locked = [f.id for f in features if f.id in requested]

    constraints: list[str] = []
    for c in brief.constraints:
        c = " ".join(c.split())
        if c and c.lower() not in {x.lower() for x in constraints}:
            constraints.append(c)
    if brief.cost_target_inr:
        constraints.append(f"Target cost under ₹{brief.cost_target_inr:,} per unit")
    return locked, constraints[: MAX_CONSTRAINTS + 1]


def brief_key(locked: list[str], constraints: list[str]) -> str:
    """A stable name for caching this brief's result beside the report."""
    payload = json.dumps(
        {"locked": sorted(locked), "constraints": sorted(c.lower() for c in constraints)},
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


# --- Alternatives ----------------------------------------------------------------

REDESIGN_PROMPT = """Invention:
---
{idea_text}
---

Its essential features (LOCKED = the inventor requires the design to keep it):
{features_block}

The inventor's constraints:
{constraints_block}

The closest existing documents found in a prior-art search (key, title, text):
{documents_block}

Propose {n} genuinely different alternative designs of this invention. Each one must:
- keep every LOCKED feature;
- respect every constraint (treat cost and performance figures as design targets: \
reason about materials and construction, but never claim a measured cost or \
performance number);
- move away from at least one specific mechanism or arrangement that a document above \
discloses and the current invention shares — a different working principle, not a \
cosmetic change.
Make the {n} alternatives differ from each other, not variations on one theme: where the \
documents allow, each should move away from a different overlap, or change a different \
part of the invention (how it works, how it is built, or what it is made of).

For each alternative give:
- "title": a short name (3-8 words)
- "how_it_works": 2-3 plain sentences a non-expert can follow
- "what_changes": one sentence on what is different from the current invention
- "keeps": the ids of the LOCKED features this design keeps, e.g. ["E1"]
- "constraint_notes": for each constraint, {{"constraint": "<as written above>", \
"approach": "<one sentence on how the design aims to meet it>"}}
- "avoids": 1-{max_avoids} overlaps it steps away from, each {{"document": "D1", \
"mechanism": "<what that document does that this design no longer does>", "quote": \
"<the sentence from that document's text that shows the mechanism, COPIED EXACTLY, \
5-40 words>"}}
- "revised_idea": the complete revised invention described in English, as a \
self-contained paragraph (it will be searched for prior art on its own)
- "change_summary": the change in one English sentence, starting with a verb

Write "title", "how_it_works", "what_changes" and each "approach" in {language}. \
Write "revised_idea", "change_summary", "mechanism" and quotes in English. \
Say "the existing design", never a document key, in the text fields.

Quotes are checked against the document text automatically and discarded if they do not \
appear in it word for word — never paraphrase.

Respond with a single JSON object:
{{"alternatives": [{{"title": "...", "how_it_works": "...", "what_changes": "...", \
"keeps": ["E1"], "constraint_notes": [{{"constraint": "...", "approach": "..."}}], \
"avoids": [{{"document": "D1", "mechanism": "...", "quote": "..."}}], \
"revised_idea": "...", "change_summary": "..."}}]}}
"""


class _RawConstraintNote(BaseModel):
    constraint: str = ""
    approach: str = ""


class _RawAvoid(BaseModel):
    document: str = ""
    mechanism: str = ""
    quote: str = ""


class _RawAlternative(BaseModel):
    title: str
    how_it_works: str
    what_changes: str = ""
    keeps: list[str] = []
    constraint_notes: list[_RawConstraintNote] = []
    avoids: list[_RawAvoid] = []
    revised_idea: str
    change_summary: str


class _RawAlternatives(BaseModel):
    alternatives: list[_RawAlternative]


def _clean(text: str) -> str:
    """Models mention document keys despite instructions; rewrite them."""
    cleaned = _DOC_KEY.sub("the existing design", text.strip())
    return re.sub(r"\s{2,}", " ", cleaned)


def build_alternatives(
    raw: _RawAlternatives,
    locked: list[str],
    constraints: list[str],
    documents: list[tuple[str, MatchRef, str]],
) -> tuple[list[DesignAlternative], int]:
    """Turn the model's proposals into alternatives that only assert what
    can be checked: avoided overlaps need a verified quote, kept features
    must be real locked ids, and constraint notes must answer a constraint
    the inventor actually set. Proposals without a usable revised idea
    can't be re-checked, so they're dropped. Returns the alternatives and
    the number of quotes that failed verification."""
    by_key = {key: (ref, text) for key, ref, text in documents}
    constraint_by_lower = {c.lower(): c for c in constraints}
    alternatives: list[DesignAlternative] = []
    dropped = 0

    for a in raw.alternatives:
        revised = " ".join(a.revised_idea.split())
        change = " ".join(a.change_summary.split())
        if len(revised) < 20 or not change or not a.title.strip():
            continue

        keeps = [f for f in locked if f in {k.strip().upper() for k in a.keeps}]

        avoids: list[AvoidedOverlap] = []
        seen_docs: set[str] = set()
        for v in a.avoids:
            key = v.document.strip().strip("[]").upper()
            if key not in by_key or not v.mechanism.strip():
                continue
            ref, text = by_key[key]
            if not quote_is_verified(v.quote, text):
                dropped += 1
                continue
            if ref.id in seen_docs:
                continue
            seen_docs.add(ref.id)
            avoids.append(
                AvoidedOverlap(
                    document_id=ref.id,
                    title=ref.title,
                    link=ref.link,
                    mechanism=v.mechanism.strip(),
                    quote=v.quote.strip(),
                )
            )
            if len(avoids) == MAX_AVOIDS:
                break

        notes: dict[str, ConstraintNote] = {}
        for i, n in enumerate(a.constraint_notes):
            # Matched by text; a note whose wording drifted from the
            # constraint falls back to its position in the list.
            constraint = constraint_by_lower.get(" ".join(n.constraint.split()).lower())
            if constraint is None and i < len(constraints):
                constraint = constraints[i]
            if constraint and n.approach.strip() and constraint not in notes:
                notes[constraint] = ConstraintNote(constraint=constraint, approach=_clean(n.approach))

        alternatives.append(
            DesignAlternative(
                title=_clean(a.title),
                how_it_works=_clean(a.how_it_works),
                what_changes=_clean(a.what_changes),
                keeps=keeps,
                drops_locked=[f for f in locked if f not in keeps],
                constraint_notes=[notes[c] for c in constraints if c in notes],
                avoids=avoids,
                revised_idea=revised,
                change_summary=change,
            )
        )
        if len(alternatives) == ALTERNATIVES:
            break

    return alternatives, dropped


def propose_redesigns(
    report: AnalysisResult,
    features: list[Feature],
    brief: RedesignBrief,
) -> RedesignResult:
    """Raises ValueError if the model can't produce usable alternatives."""
    locked, constraints = normalize_brief(brief, features)

    docs, basis = select_documents(report)
    texts = {d.meta.id: d.text for d in docs}
    originals = [o for o in original_closest(report) if texts.get(o.result_id, "").strip()]
    documents = [
        (f"D{i}", MatchRef(id=o.result_id, title=o.title, link=o.link), texts[o.result_id])
        for i, o in enumerate(originals, start=1)
    ]

    locked_set = set(locked)
    prompt = REDESIGN_PROMPT.format(
        idea_text=report.idea_text,
        features_block="\n".join(
            f"{f.id}: {f.text}{' (LOCKED)' if f.id in locked_set else ''}" for f in features
        ),
        constraints_block="\n".join(f"- {c}" for c in constraints) or "- (none)",
        documents_block="\n\n".join(f"[{key}] {ref.title}\n{text}" for key, ref, text in documents)
        or "(no document texts available)",
        n=ALTERNATIVES,
        max_avoids=MAX_AVOIDS,
        language=report.language_name or "English",
    )

    last_error: Exception | None = None
    for _ in range(2):
        try:
            raw = _RawAlternatives.model_validate(
                complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.5)
            )
        except (ValueError, ValidationError) as e:
            last_error = e
            continue
        alternatives, dropped = build_alternatives(raw, locked, constraints, documents)
        if alternatives:
            return RedesignResult(
                features=features,
                locked_features=locked,
                constraints=constraints,
                alternatives=alternatives,
                matches_considered=[ref for _, ref, _ in documents],
                evidence_basis=basis,
                unverified_quotes_dropped=dropped,
                language_name=report.language_name or "English",
            )
        last_error = ValueError("no usable alternatives")
    raise ValueError(f"Redesign failed: {last_error}")
