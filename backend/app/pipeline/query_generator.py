"""Stage 1.1: Query Generator.

Turns a raw invention idea description into a small set of distinct
Google Patents boolean search queries, each covering a different angle
(major markets, India-specific, broader/looser recall), plus an optional
CPC classification guess.
"""
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.llm import complete_json

QueryType = Literal["major_markets", "india_specific", "broad_recall"]


class GeneratedQuery(BaseModel):
    type: QueryType
    query: str
    rationale: str


class QueryGenerationResult(BaseModel):
    core_concepts: list[str]
    suggested_cpc: str | None = None
    trends_keyword: str | None = None
    queries: list[GeneratedQuery]


SYSTEM_PROMPT = """You are a patent search expert who writes precise Google Patents \
search queries. You always respond with a single valid JSON object and nothing else.

Google Patents query syntax you must use correctly:
- Parentheses + OR group synonyms: (battery OR "power cell")
- Adjacent terms/groups are implicitly ANDed: (drone OR UAV) (delivery OR logistics)
- Use quotes for exact multi-word phrases: "autonomous landing"
- Prefix a term with "-" to exclude it: -military
- Keep each query focused: 2-5 core concept groups ANDed together, each with a \
few OR'd synonyms. Do not write a single giant query with every synonym you can \
think of — that returns near-zero results.
"""

USER_PROMPT_TEMPLATE = """Invention idea (plain English, from an inventor):
---
{idea_text}
---

Do the following:
1. Extract 3-6 core technical concepts from this idea (short noun phrases).
2. If you are confident about a relevant CPC (Cooperative Patent Classification) \
code for this idea's technical field, suggest it (e.g. "H01L31/00"). Otherwise use null.
3. Generate exactly 3 distinct Google Patents search queries using the syntax rules \
above, one of each type:
   - "major_markets": a precise query aimed at finding blocking prior art in major \
patent markets (US/EP/CN/WO), using the most specific terms from the idea.
   - "india_specific": a query targeting the same core invention that will be run \
ONLY against Indian Patent Office filings (the country filter is applied for you — do \
not put country terms in the query text). The Indian corpus is much smaller, so use \
2-3 concept groups with generous OR synonyms rather than the most specific terms.
   - "broad_recall": a deliberately looser query using broader/parent terms and \
more OR synonyms, to catch prior art that uses different terminology for the same \
concept, accepting more noise in exchange for recall.

4. Give a "trends_keyword": the 1-3 word phrase an ordinary person would type into \
Google to find a product like this (e.g. "kayak paddle", "smart water bottle"), used to \
measure public interest in the product category. Plain words only, no operators.

Respond with a single JSON object of this exact shape:
{{
  "core_concepts": ["...", "..."],
  "suggested_cpc": "..." or null,
  "trends_keyword": "...",
  "queries": [
    {{"type": "major_markets", "query": "...", "rationale": "..."}},
    {{"type": "india_specific", "query": "...", "rationale": "..."}},
    {{"type": "broad_recall", "query": "...", "rationale": "..."}}
  ]
}}
"""


def generate_queries(idea_text: str, max_retries: int = 1) -> QueryGenerationResult:
    """Call the LLM to turn an idea description into search queries.

    Raises ValueError if the model fails to produce a valid, schema-conforming
    result within max_retries + 1 attempts.
    """
    prompt = USER_PROMPT_TEMPLATE.format(idea_text=idea_text.strip())

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            raw = complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.2)
            return QueryGenerationResult.model_validate(raw)
        except (ValueError, ValidationError) as e:
            last_error = e
            continue

    raise ValueError(
        f"Query generation failed after {max_retries + 1} attempts: {last_error}"
    )
