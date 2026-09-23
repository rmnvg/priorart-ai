"""Agentic search refinement: read the first results, then search again in
the patents' own words.

An inventor says "folding paddle"; the patent that anticipates it says
"sectional propulsion shaft". Keyword search can't bridge that gap on the
first try — it only finds documents sharing the query's vocabulary. A human
searcher's fix is to read the first page of hits, notice the terms the
relevant documents actually use, and search again with those. This stage
does exactly that: one LLM call reads the top results of the first round and
writes follow-up queries in the vocabulary it found.

It also covers the worst first-round outcome: when nothing came back at all,
it's asked for broader queries instead of refined ones.

Cost is bounded by config (REFINEMENT_QUERIES, one SerpApi search each).
Every failure path returns None and the pipeline continues with the first
round's results — refinement can only add to a report, never break one.
"""
import logging

from pydantic import BaseModel, ValidationError

from app.llm import complete_json
from app.pipeline.query_generator import GeneratedQuery, QueryGenerationResult
from app.pipeline.rank import RankedResult

logger = logging.getLogger(__name__)

RESULTS_SHOWN_TO_LLM = 8
MAX_OBSERVATION_CHARS = 240


class RefinementPlan(BaseModel):
    observation: str  # one sentence, shown to the user as the agent's reasoning
    new_terms: list[str]
    queries: list[GeneratedQuery]


SYSTEM_PROMPT = """You are an experienced patent searcher reviewing the first page of \
results for an invention, deciding what to search next. You always respond with a \
single valid JSON object and nothing else.

Google Patents query syntax: (a OR b) groups synonyms, adjacent groups are ANDed, \
2-4 concept groups per query. EVERY multi-word term must be in double quotes — write \
("modular shaft" OR "sectional shaft"), never (modular shaft OR sectional shaft), which \
Google Patents reads as separate words. No country or date filters."""

REFINE_PROMPT = """Invention idea:
---
{idea_text}
---

Queries already run:
{queries_block}

Top results so far (title and snippet):
{results_block}

{task}

Respond with a single JSON object of this exact shape:
{{
  "observation": "<{observation_spec}>",
  "new_terms": ["<terms from the results that the queries above did not use>"],
  "queries": ["<up to {max_queries} new Google Patents queries>"]
}}
"""

TASK_REFINE = """Patent documents often describe the same thing in different words than \
an inventor does. Compare the vocabulary in the relevant results above with the queries \
already run. Identify technical terms the relevant documents use for the idea's key \
elements that the queries did NOT use, and write up to {max_queries} new queries built \
from that vocabulary, aimed at prior art the first round may have missed. Do not repeat \
or lightly reword an existing query. If the results are clearly off-topic, write queries \
that fix the direction instead."""

OBSERVATION_REFINE = """ONE sentence of at most 25 words for the inventor, naming the \
specific terms the patents use, e.g. 'Related patents call this a \\"sectional shaft\\", \
not a folding paddle, so searching again in their terminology.'"""

OBSERVATION_RESCUE = """ONE sentence of at most 25 words for the inventor saying the first \
searches found nothing and which broader terms you are trying instead. Do not claim \
anything about what patents say — none were found."""

TASK_RESCUE = """The queries above returned NOTHING. They were probably too specific or \
used unusual wording. Write up to {max_queries} broader queries: fewer concept groups, \
more common synonyms, and parent terms for the idea's core function."""


class _RawPlan(BaseModel):
    observation: str
    new_terms: list[str] = []
    queries: list[str]


def _format_queries(query_result: QueryGenerationResult) -> str:
    return "\n".join(f"- {q.query}" for q in query_result.queries) or "(none)"


def _format_results(ranked: list[RankedResult]) -> str:
    shown = [r for r in ranked if r.source_type in ("patent", "scholar")][:RESULTS_SHOWN_TO_LLM]
    return (
        "\n".join(f"- {r.title}: {r.snippet[:300]}" for r in shown) if shown else "(no results)"
    )


def plan_refinement(
    idea_text: str,
    query_result: QueryGenerationResult,
    ranked: list[RankedResult],
    max_queries: int,
) -> RefinementPlan | None:
    if max_queries <= 0:
        return None

    has_results = any(r.source_type in ("patent", "scholar") for r in ranked)
    task = (TASK_REFINE if has_results else TASK_RESCUE).format(max_queries=max_queries)
    prompt = REFINE_PROMPT.format(
        observation_spec=OBSERVATION_REFINE if has_results else OBSERVATION_RESCUE,
        idea_text=idea_text.strip(),
        queries_block=_format_queries(query_result),
        results_block=_format_results(ranked),
        task=task,
        max_queries=max_queries,
    )

    try:
        raw = _RawPlan.model_validate(complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.3))
    except (ValueError, ValidationError) as e:
        logger.warning("Refinement planning failed, keeping first-round results: %s", e)
        return None

    existing = {q.query.strip().lower() for q in query_result.queries}
    queries = [
        GeneratedQuery(type="refined", query=q.strip(), rationale=raw.observation.strip())
        for q in raw.queries
        if q.strip() and q.strip().lower() not in existing
    ][:max_queries]
    if not queries:
        return None

    observation = raw.observation.strip()
    if len(observation) > MAX_OBSERVATION_CHARS:
        observation = observation[:MAX_OBSERVATION_CHARS].rsplit(" ", 1)[0] + "…"

    return RefinementPlan(
        observation=observation or "Searching again with terminology from the first results.",
        new_terms=[t.strip() for t in raw.new_terms if t.strip()][:8],
        queries=queries,
    )
