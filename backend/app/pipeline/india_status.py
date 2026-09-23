"""Stage 1.6: India-Specific Patentability Signal.

Purely computational — no LLM or extra API call. Reads the `country_status`
field already present on patent results (pulled during the Search Layer) and
tallies how many of the closest-matching candidates are active blocking art
in India specifically vs. active only elsewhere. Scoped to the same
closest-match window used for deep-dive/novelty assessment (top_n
patent/scholar candidates), since a patent buried far down the ranking isn't
a meaningful "closest match" signal.
"""
from pydantic import BaseModel

from app.pipeline.rank import RankedResult


class IndiaStatus(BaseModel):
    blocking_in_india: int
    active_elsewhere_only: int
    # Indian Patent Office publications anywhere in the results (not just
    # the closest matches) — surfaced by the country-filtered India query.
    india_filings_found: int = 0


def is_indian_filing(patent_id: str) -> bool:
    # SerpApi patent ids look like "patent/IN202141012345A/en".
    return patent_id.startswith("patent/IN")


def compute_india_status(ranked_results: list[RankedResult], top_n: int = 8) -> IndiaStatus:
    closest_matches = [r for r in ranked_results if r.source_type in ("patent", "scholar")][
        :top_n
    ]

    blocking_in_india = 0
    active_elsewhere_only = 0

    for result in closest_matches:
        if result.source_type != "patent" or not result.country_status:
            continue
        active_countries = {
            country for country, status in result.country_status.items() if status == "ACTIVE"
        }
        if "IN" in active_countries:
            blocking_in_india += 1
        elif active_countries:
            active_elsewhere_only += 1

    return IndiaStatus(
        blocking_in_india=blocking_in_india,
        active_elsewhere_only=active_elsewhere_only,
        india_filings_found=sum(
            1 for r in ranked_results if r.source_type == "patent" and is_indian_filing(r.id)
        ),
    )
