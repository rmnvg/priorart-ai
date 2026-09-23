"""Indian-language support: describe the idea in your own language, read the
report in it.

Patent search is effectively English-only, and so is every professional tool
built on it — which shuts out exactly the grassroots inventors who most need
a cheap first check. This module sits at both ends of the pipeline:

- In: a non-English idea is translated to precise technical English once, and
  the whole pipeline (queries, ranking embeddings, claim chart) runs on that.
- Out: the parts of the report written for the inventor — the plain-language
  summary, differentiation suggestions, citation notes, and the key UI
  labels — are translated back in one batched call.

Everything aimed at professionals (patent titles, claims, the attorney
brief) deliberately stays in English: that's the language Indian patent
agents and the patent office work in.

Both steps are best-effort. A failed translation falls back to English
rather than failing the analysis.
"""
import json
import logging

from pydantic import BaseModel, ValidationError

from app.llm import complete_json

logger = logging.getLogger(__name__)

# Share of letters that must be ASCII for text to be treated as English
# without spending an LLM call on detection. Indian scripts (Devanagari,
# Tamil, Bengali, ...) are entirely non-ASCII, so real input sits far from
# this line; it only has to tolerate a stray symbol or accented name.
ASCII_LETTER_THRESHOLD = 0.9

# English source strings for the UI labels that get localized alongside the
# report. Keys are shared with the frontend (frontend/lib/i18n.ts).
UI_LABELS: dict[str, str] = {
    "novelty_verdict": "Novelty verdict",
    "looks_novel": "Looks novel",
    "looks_novel_blurb": "No strong blocking prior art surfaced for this idea.",
    "partial_overlap": "Partial overlap",
    "partial_overlap_blurb": "Real prior art shares elements with this idea, but it isn't fully anticipated.",
    "heavy_overlap": "Heavy overlap",
    "heavy_overlap_blurb": "Close matches already exist — differentiation will be essential.",
    "what_this_means": "What this means for you",
    "differentiate_title": "How to differentiate your idea",
    "differentiate_subtitle": "Specific changes that would move this idea away from its closest matches. Apply one to re-run the analysis and watch the verdict move.",
    "apply_recheck": "Apply & re-check →",
    "based_on": "Based on:",
    "free_to_build": "Free to build on",
    "india_signal": "India patentability signal",
    "ask_title": "Ask about this report",
    "ask_subtitle": "Answers come only from what this search found, with sources.",
    "ask_placeholder": "Ask a question about your idea and this report...",
    "ask_button": "Ask",
    "ask_q1": "Which patent is the biggest risk for my idea, and why?",
    "ask_q2": "Can I make and sell this in India?",
    "ask_q3": "What can I build on freely without worrying about patents?",
}


# Names for the report languages the UI offers directly (voice input and
# "Apply & re-check" pass a code, not a name). Anything else detected from
# free text comes with its own name from the LLM.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "ur": "Urdu",
}


def language_name_for(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)


class IdeaLanguage(BaseModel):
    code: str  # ISO 639-1, e.g. "hi"
    name: str  # English name, e.g. "Hindi"
    english_text: str


class LocalizedContent(BaseModel):
    language_code: str
    language_name: str
    plain_summary: str = ""
    differentiation_suggestions: list[str]
    citation_claims: list[str]  # parallel to AnalysisResult.citations
    ui_labels: dict[str, str]


def looks_english(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    ascii_letters = sum(1 for c in letters if c.isascii())
    return ascii_letters / len(letters) >= ASCII_LETTER_THRESHOLD


TRANSLATE_IN_SYSTEM = """You translate invention descriptions written by inventors \
into precise technical English for a patent search. You always respond with a single \
valid JSON object and nothing else."""

TRANSLATE_IN_PROMPT = """Invention description:
---
{idea_text}
---

1. Identify the language it is written in (it may mix in English words).
2. Translate it into clear, technically precise English. Keep every technical detail \
(materials, dimensions, mechanisms, how parts interact); don't add anything that isn't \
there. Translate local names of crops, tools or materials into their standard English \
terms.

Respond with a single JSON object of this exact shape:
{{"language_code": "<ISO 639-1 code, e.g. hi>", "language_name": "<English name, e.g. Hindi>", \
"english_text": "..."}}
"""


class _RawIdeaLanguage(BaseModel):
    language_code: str
    language_name: str
    english_text: str


def detect_and_translate(idea_text: str) -> IdeaLanguage:
    """English input passes through without an LLM call. Anything else is
    translated; if that fails, the original text goes through unchanged —
    the query generator can still work from it, just less precisely."""
    if looks_english(idea_text):
        return IdeaLanguage(code="en", name="English", english_text=idea_text)
    try:
        raw = complete_json(
            TRANSLATE_IN_PROMPT.format(idea_text=idea_text),
            system=TRANSLATE_IN_SYSTEM,
            temperature=0.1,
        )
        parsed = _RawIdeaLanguage.model_validate(raw)
    except (ValueError, ValidationError) as e:
        logger.warning("Idea translation failed, using original text: %s", e)
        return IdeaLanguage(code="und", name="the original language", english_text=idea_text)
    code = parsed.language_code.strip().lower()[:8] or "und"
    return IdeaLanguage(
        code=code,
        name=parsed.language_name.strip() or code,
        english_text=parsed.english_text.strip() or idea_text,
    )


TRANSLATE_OUT_SYSTEM = """You translate a patent novelty report for an independent \
inventor who reads {language_name} best. You always respond with a single valid JSON \
object and nothing else."""

TRANSLATE_OUT_PROMPT = """Translate every string value in this JSON object into \
{language_name}. Rules:
- Write naturally, the way you'd explain it to a smart person who isn't a patent expert.
- Keep patent numbers, company names, product names, and measurements exactly as they are.
- Where a technical term has no everyday {language_name} equivalent, keep the English \
term (you may add a short explanation in brackets).
- Keep exactly the same keys, the same list lengths, and the same order.

{payload}
"""


class _RawLocalized(BaseModel):
    plain_summary: str = ""
    differentiation_suggestions: list[str]
    citation_claims: list[str]
    ui_labels: dict[str, str]


def localize_report(
    language_code: str,
    language_name: str,
    plain_summary: str,
    differentiation_suggestions: list[str],
    citation_claims: list[str],
) -> LocalizedContent | None:
    payload = {
        "plain_summary": plain_summary,
        "differentiation_suggestions": differentiation_suggestions,
        "citation_claims": citation_claims,
        "ui_labels": UI_LABELS,
    }
    try:
        raw = complete_json(
            TRANSLATE_OUT_PROMPT.format(
                language_name=language_name, payload=json.dumps(payload, ensure_ascii=False)
            ),
            system=TRANSLATE_OUT_SYSTEM.format(language_name=language_name),
            temperature=0.2,
        )
        parsed = _RawLocalized.model_validate(raw)
    except (ValueError, ValidationError) as e:
        logger.warning("Report localization to %s failed: %s", language_name, e)
        return None

    # A translation that dropped or merged items would silently misalign
    # suggestions with their "Apply" buttons and claims with their sources.
    # Better to show English than to show the wrong thing.
    if len(parsed.differentiation_suggestions) != len(differentiation_suggestions) or len(
        parsed.citation_claims
    ) != len(citation_claims):
        logger.warning("Report localization to %s changed list lengths; discarding", language_name)
        return None

    return LocalizedContent(
        language_code=language_code,
        language_name=language_name,
        plain_summary=parsed.plain_summary,
        differentiation_suggestions=parsed.differentiation_suggestions,
        citation_claims=parsed.citation_claims,
        # Missing labels fall back to English per key rather than failing.
        ui_labels={k: parsed.ui_labels.get(k) or v for k, v in UI_LABELS.items()},
    )
