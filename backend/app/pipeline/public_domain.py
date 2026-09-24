"""Public-domain finder: prior art that is likely free to build on.

The rest of the pipeline treats prior art as an obstacle. This stage inverts
that: a patent whose protection has ended is not a blocker, it's published
technology released to the public, generally free to use wherever it has
lapsed. For an independent inventor that's often the most actionable thing in
the report.

Runs entirely on `country_status` and `priority_date` already fetched during
the search stage — no extra API calls.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.pipeline.rank import RankedResult

# Patents run 20 years from the priority/filing date in every major
# jurisdiction. Past that the term has simply run out.
PATENT_TERM_YEARS = 20

LapseReason = Literal["term_expired", "lapsed_early"]


class PublicDomainEntry(BaseModel):
    id: str
    title: str
    link: str
    priority_date: str | None = None
    assignee: str | None = None
    relevance_score: float
    lapsed_in: list[str]
    reason: LapseReason
    years_since_filing: int | None = None


class PublicDomainSummary(BaseModel):
    count: int
    patents_considered: int
    entries: list[PublicDomainEntry]


def years_since(priority_date: str | None) -> int | None:
    if not priority_date:
        return None
    try:
        filed = date.fromisoformat(priority_date[:10])
    except ValueError:
        return None
    return (date.today() - filed).days // 365


def find_public_domain(
    ranked_results: list[RankedResult], max_entries: int = 8
) -> PublicDomainSummary:
    """Select patents that appear to be out of force everywhere we have data.

    Deliberately strict: a patent qualifies only with *positive* evidence of
    lapse (at least one NOT_ACTIVE) and no ACTIVE status anywhere. An
    all-UNKNOWN record means we don't know, which is not the same as free —
    Google Patents reports UNKNOWN often enough that treating it as lapsed
    would hand users dangerously wrong advice.
    """
    patents = [r for r in ranked_results if r.source_type == "patent" and r.country_status]

    entries: list[PublicDomainEntry] = []
    for r in patents:
        statuses = r.country_status.values()
        if any(s == "ACTIVE" for s in statuses):
            continue
        if not any(s == "NOT_ACTIVE" for s in statuses):
            continue

        age = years_since(r.priority_date)
        entries.append(
            PublicDomainEntry(
                id=r.id,
                title=r.title,
                link=r.link,
                priority_date=r.priority_date,
                assignee=r.assignee,
                relevance_score=r.relevance_score,
                lapsed_in=sorted(c for c, s in r.country_status.items() if s == "NOT_ACTIVE"),
                # Past the statutory term is a different (and much safer)
                # story than a patent abandoned early for unpaid fees, which
                # can occasionally be revived.
                reason="term_expired"
                if age is not None and age >= PATENT_TERM_YEARS
                else "lapsed_early",
                years_since_filing=age,
            )
        )

    entries.sort(key=lambda e: e.relevance_score, reverse=True)
    return PublicDomainSummary(
        count=len(entries),
        patents_considered=len(patents),
        entries=entries[:max_entries],
    )
