"""Ask about this report: follow-up questions answered from the report alone.

A report answers "has this been done?", but the inventor's next questions are
specific — "which patent is the real risk?", "can I sell this in India?",
"what if I used bamboo instead?". This answers them grounded strictly in what
the report's searches actually found: no new searches, no outside knowledge
presented as findings. Every document the answer relies on is cited by a
short key the model is given ([D3]), which the server resolves to the real
title and link — the model never produces a URL itself.

Answers come back in the language the question was asked in, so a Hindi
report can be questioned in Hindi.
"""
import re

from pydantic import BaseModel, Field, ValidationError

from app.llm import complete_json
from app.models import AnalysisResult
from app.pipeline.evidence import headline

MAX_RANKED_IN_CONTEXT = 15
MAX_HISTORY_TURNS = 4
SNIPPET_CHARS = 220

_KEY_PATTERN = re.compile(r"\[(D\d+)\]")
# Models often drop the brackets ("see D3") or group keys ("[D2, D5]");
# both are normalized to "[D3]" form before resolving.
_BARE_KEY = re.compile(r"(?<![\w\[])(D\d+)(?![\w\]])")
_GROUPED_KEYS = re.compile(r"\[(D\d+(?:\s*,\s*D\d+)+)\]")


class AskTurn(BaseModel):
    question: str = Field(max_length=500)
    answer: str = Field(max_length=4000)


class AnswerSource(BaseModel):
    key: str  # "D3", as it appears in the answer text
    id: str
    title: str
    link: str


class ReportAnswer(BaseModel):
    answer: str
    sources: list[AnswerSource]


def _document_table(result: AnalysisResult) -> dict[str, AnswerSource]:
    """Every document the model may cite, keyed D1, D2, ... in the order the
    context lists them. Ranked results first, then citation discoveries."""
    table: dict[str, AnswerSource] = {}
    seen: set[str] = set()

    def add(doc_id: str, title: str, link: str) -> None:
        if doc_id in seen:
            return
        seen.add(doc_id)
        key = f"D{len(table) + 1}"
        table[key] = AnswerSource(key=key, id=doc_id, title=title, link=link)

    for r in result.ranked_results[:MAX_RANKED_IN_CONTEXT]:
        add(r.id, r.title, r.link)
    if result.public_domain:
        for e in result.public_domain.entries:
            add(e.id, e.title, e.link)
    if result.citation_network:
        for d in result.citation_network.discoveries:
            add(d.id, d.title, d.link)
    return table


def build_context(result: AnalysisResult, table: dict[str, AnswerSource]) -> str:
    key_by_id = {s.id: k for k, s in table.items()}
    ranked_by_id = {r.id: r for r in result.ranked_results}
    verdict_by_id = {a.result_id: a for a in result.candidate_assessments}

    lines = [
        f"INVENTION: {result.idea_text}",
        f"MODEL'S OVERALL NOVELTY ESTIMATE: {round(result.overall_novelty_confidence * 100)}% "
        "(an uncalibrated model estimate — prefer the feature evidence below)",
    ]
    summary = headline(result.feature_findings, len(result.examined_documents))
    if summary:
        lines.append(f"FEATURE EVIDENCE: {summary}")
    if result.plain_summary:
        lines.append(f"SUMMARY: {result.plain_summary}")

    lines.append("\nDOCUMENTS FOUND (cite by key):")
    for key, source in table.items():
        r = ranked_by_id.get(source.id)
        parts = [f"[{key}] {source.title}"]
        if r:
            parts.append(f"type={r.source_type}; relevance={round(r.relevance_score * 100)}%")
            if r.assignee:
                parts.append(f"assignee={r.assignee}")
            if r.priority_date:
                parts.append(f"priority={r.priority_date}")
            active = sorted(c for c, s in r.country_status.items() if s == "ACTIVE")
            lapsed = sorted(c for c, s in r.country_status.items() if s == "NOT_ACTIVE")
            if active:
                parts.append(f"in force in {','.join(active)}")
            if lapsed:
                parts.append(f"lapsed in {','.join(lapsed)}")
            if r.snippet:
                parts.append(f"snippet: {r.snippet[:SNIPPET_CHARS]}")
        a = verdict_by_id.get(source.id)
        if a:
            parts.append(
                f"assessment={a.verdict}; overlaps: {'; '.join(a.overlapping_elements) or 'none'}; "
                f"differences: {'; '.join(a.differences) or 'none'}"
            )
        lines.append(" | ".join(parts))

    if result.public_domain and result.public_domain.entries:
        lines.append("\nNO LONGER IN FORCE (free to build on): " + ", ".join(
            f"[{key_by_id[e.id]}] ({'20-year term expired' if e.reason == 'term_expired' else 'lapsed early'})"
            for e in result.public_domain.entries
            if e.id in key_by_id
        ))
    if result.citation_network and result.citation_network.discoveries:
        lines.append("\nFOUND BY CITATION CHASING (not in keyword results): " + ", ".join(
            f"[{key_by_id[d.id]}]" for d in result.citation_network.discoveries if d.id in key_by_id
        ))

    india = result.india_status
    lines.append(
        f"\nINDIA: {india.related_active_in_india} related patents among the closest matches "
        "reported active in India (legal status only — not evidence they overlap the idea); "
        f"{india.active_elsewhere_only} in force elsewhere but not India; "
        f"{india.india_filings_found} Indian filings among results. Google Patents often "
        "reports Indian legal status as unknown."
    )
    if result.top_assignees:
        lines.append(
            "TOP ASSIGNEES (share of matching results): "
            + ", ".join(f"{a.name} {a.percentage:.1f}%" for a in result.top_assignees)
        )
    if result.market_trend:
        t = result.market_trend
        lines.append(
            f"MARKET INTEREST (Google Trends, '{t.keyword}', 5 years): {t.direction}, "
            f"{t.change_pct:+d}% vs prior year"
        )
    if result.differentiation_suggestions:
        lines.append("DIFFERENTIATION SUGGESTIONS: " + " / ".join(result.differentiation_suggestions))
    if result.search_strategy:
        lines.append(
            "SEARCHES RUN: " + " ; ".join(q.query for q in result.search_strategy.queries)
        )
    return "\n".join(lines)


SYSTEM_PROMPT = """You answer an inventor's follow-up questions about a prior-art \
report. You always respond with a single valid JSON object and nothing else.

Rules:
- Use ONLY the report below. If the report doesn't contain the answer, say so plainly \
and say what would answer it (a further search, a registered patent agent). Never \
present outside knowledge as something the search found.
- Cite every document you rely on with its key in square brackets right after the \
claim, e.g. "the closest match is a buoyant paddle shaft [D3]". Always include the \
brackets. Only use keys that appear in the report.
- Answer in the same language the question is written in. Plain words, no jargon; \
explain a patent term if you must use it.
- Be direct and short: 2-5 sentences, or a few bullets for a list.
- On legal questions (infringement, whether a patent would be granted, whether it's \
safe to sell), give what the report indicates, then say a registered patent agent \
must confirm. Never state a legal conclusion as certain."""

USER_PROMPT = """REPORT
------
{context}
------

{history}QUESTION: {question}

Respond with a single JSON object: {{"answer": "..."}}"""


class _RawAnswer(BaseModel):
    answer: str


def _format_history(history: list[AskTurn]) -> str:
    turns = history[-MAX_HISTORY_TURNS:]
    if not turns:
        return ""
    return (
        "EARLIER IN THIS CONVERSATION\n"
        + "\n".join(f"Q: {t.question}\nA: {t.answer}" for t in turns)
        + "\n\n"
    )


def resolve_citations(answer: str, table: dict[str, AnswerSource]) -> ReportAnswer:
    """Keep only keys that exist, in first-cited order; remove any made-up
    keys from the text so the reader never sees a citation that leads
    nowhere."""
    answer = _GROUPED_KEYS.sub(
        lambda m: "".join(f"[{k.strip()}]" for k in m.group(1).split(",")), answer
    )
    answer = _BARE_KEY.sub(r"[\1]", answer)
    cited: list[AnswerSource] = []
    for key in _KEY_PATTERN.findall(answer):
        if key in table and table[key] not in cited:
            cited.append(table[key])
    cleaned = _KEY_PATTERN.sub(lambda m: m.group(0) if m.group(1) in table else "", answer)
    cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return ReportAnswer(answer=cleaned, sources=cited)


def answer_question(
    result: AnalysisResult, question: str, history: list[AskTurn] | None = None
) -> ReportAnswer:
    """Raises ValueError when the model can't produce a usable answer."""
    table = _document_table(result)
    prompt = USER_PROMPT.format(
        context=build_context(result, table),
        history=_format_history(history or []),
        question=question.strip(),
    )
    last_error: Exception | None = None
    for _ in range(2):
        try:
            raw = _RawAnswer.model_validate(
                complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.2, max_tokens=4000)
            )
            if raw.answer.strip():
                return resolve_citations(raw.answer, table)
        except (ValueError, ValidationError) as e:
            last_error = e
    raise ValueError(f"Could not answer the question: {last_error}")
