"""A report rendered as compact Markdown — what the MCP server hands to an AI
assistant. Written to be read by a model and relayed to a person: the
verdict first, the evidence as links, nothing decorative.
"""
from app.models import AnalysisResult

VERDICT_LABELS = {
    "blocking": "blocking",
    "partially_overlapping": "partial overlap",
    "not_relevant": "not relevant",
}
MAX_CLOSEST = 5
MAX_LISTED = 3


def _verdict_word(confidence: float) -> str:
    if confidence >= 0.65:
        return "looks novel"
    if confidence >= 0.35:
        return "partial overlap with existing prior art"
    return "heavy overlap with existing prior art"


def report_to_markdown(result: AnalysisResult, report_url: str | None = None) -> str:
    pct = round(result.overall_novelty_confidence * 100)
    lines = [
        f"## Prior-art check: {pct}% novelty confidence ({_verdict_word(result.overall_novelty_confidence)})",
        "",
    ]
    if result.plain_summary:
        lines += [result.plain_summary, ""]

    if result.candidate_assessments:
        lines.append("### Closest prior art")
        for a in result.candidate_assessments[:MAX_CLOSEST]:
            overlap = "; ".join(a.overlapping_elements[:3]) or "no real overlap"
            lines.append(f"- [{a.title}]({a.link}) — {VERDICT_LABELS[a.verdict]}. Overlaps: {overlap}")
        lines.append("")

    discoveries = result.citation_network.discoveries if result.citation_network else []
    if discoveries:
        lines.append("### Found by citation chasing (missed by keyword search)")
        for d in discoveries[:MAX_LISTED]:
            lines.append(f"- [{d.title}]({d.link}) — linked to {len(d.referenced_by)} of the closest matches")
        lines.append("")

    if result.public_domain and result.public_domain.count:
        lines.append(
            f"### Likely free to build on: {result.public_domain.count} related patents reported "
            "as no longer in force (check each one's countries)"
        )
        for e in result.public_domain.entries[:MAX_LISTED]:
            why = "20-year term expired" if e.reason == "term_expired" else "lapsed early"
            lines.append(f"- [{e.title}]({e.link}) — {why}")
        lines.append("")

    india = result.india_status
    lines.append(
        f"**India:** {india.blocking_in_india} of the closest matches are in force in India, "
        f"{india.active_elsewhere_only} only elsewhere."
    )
    lines.append("")

    if result.differentiation_suggestions:
        lines.append("### How to differentiate")
        lines += [f"{i}. {s}" for i, s in enumerate(result.differentiation_suggestions, 1)]
        lines.append("")

    if report_url:
        lines.append(f"Full interactive report (landscape graph, claim chart): {report_url}")
    lines.append("_First-pass search, not legal advice._")
    return "\n".join(lines)


OUTCOME_LINES = {
    "novelty_objection": "Likely objection: **lack of novelty** (s. 2(1)(j)) — one document discloses every element.",
    "inventive_step_objection": "Likely objection: **lack of inventive step** (s. 2(1)(ja)) — two documents together disclose every element.",
    "combination_risk": "Inventive-step risk: every element appears somewhere, but only across three or more documents.",
    "no_objection_found": "No novelty or inventive-step objection from the documents found — at least one element appears in none of them.",
}


def examination_to_markdown(preview) -> str:
    """`preview` is an app.pipeline.examination.ExaminationPreview."""
    docs = {d.key: d for d in preview.documents}
    elements = {e.id: e.text for e in preview.elements}
    lines = ["## Examination preview (simulated — not issued by the Indian Patent Office)", ""]
    lines += [OUTCOME_LINES[preview.outcome], ""]

    if preview.section3_flags:
        lines.append("### Section 3 (not an invention under the Patents Act)")
        for f in preview.section3_flags:
            lines.append(f"- **{f.clause} {f.title}** ({f.risk} risk): {f.reason} → {f.how_to_address}")
        lines.append("")

    for key in preview.novelty_objections:
        lines.append(f"- Anticipated by [{docs[key].title}]({docs[key].link})")
    for obj in preview.inventive_step_objections:
        a, b = (docs[k] for k in obj.documents)
        field = " (same technical field)" if obj.same_field else ""
        lines.append(f"- Obvious over [{a.title}]({a.link}) + [{b.title}]({b.link}){field}")

    if preview.uncovered_elements:
        lines += ["", "### Novelty core — disclosed by none of the documents found"]
        lines += [f"- {elements[e]}" for e in preview.uncovered_elements]

    lines += [
        "",
        f"_Based on {len(preview.documents)} documents "
        f"({'full text' if preview.evidence_basis == 'full_text' else 'search snippets only'}). "
        "A preview, not a legal opinion — a registered patent agent must confirm._",
    ]
    return "\n".join(lines)
