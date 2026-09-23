"""Tests for the pipeline's pure logic — no network, no API keys required.

Deliberately scoped to the parts that fail *silently*: dedupe/merge rules,
the India tally, LLM-output validation guards, and cache persistence. The
LLM and SerpApi calls themselves aren't tested here; they're exercised by
running the real pipeline.
"""
import asyncio
import json

import pytest

from app.models import ProgressEvent
from app.pipeline.deepdive import _summarize_patent_details, _truncate
from app.pipeline.india_status import compute_india_status
from app.pipeline.novelty import (
    _RawCandidateAssessment,
    _RawCitation,
    _resolve_assessments,
    _resolve_citations,
)
from app.pipeline.rank import RankedResult, _dedupe
from app.pipeline.search import (
    PatentResult,
    ProductResult,
    QueryBundle,
    ScholarResult,
    SearchLayerResult,
    _parse_assignee_stats,
)


def patent(id="patent/US1/en", score=0.5, country_status=None, cpc="A61B5/02"):
    return RankedResult(
        id=id,
        source_type="patent",
        title="A patent",
        snippet="snippet",
        link="https://example.com",
        relevance_score=score,
        cpc_code=cpc,
        country_status=country_status or {},
    )


# --- India patentability signal -------------------------------------------


def test_india_status_counts_active_in_india():
    results = [
        patent(id="a", country_status={"IN": "ACTIVE", "US": "ACTIVE"}),
        patent(id="b", country_status={"US": "ACTIVE"}),
        patent(id="c", country_status={"EP": "ACTIVE", "CN": "ACTIVE"}),
    ]
    status = compute_india_status(results)
    assert status.blocking_in_india == 1
    assert status.active_elsewhere_only == 2


def test_india_status_ignores_inactive_and_unknown():
    """Google Patents reports IN legal status as UNKNOWN far more often than
    ACTIVE — treating UNKNOWN as blocking would badly overstate the signal."""
    results = [
        patent(id="a", country_status={"IN": "UNKNOWN"}),
        patent(id="b", country_status={"IN": "NOT_ACTIVE", "US": "NOT_ACTIVE"}),
        patent(id="c", country_status={}),
    ]
    status = compute_india_status(results)
    assert status.blocking_in_india == 0
    assert status.active_elsewhere_only == 0


def test_india_status_counts_each_patent_once():
    """A patent active in India *and* elsewhere is one blocking result, not
    one in each bucket."""
    results = [patent(id="a", country_status={"IN": "ACTIVE", "US": "ACTIVE", "EP": "ACTIVE"})]
    status = compute_india_status(results)
    assert status.blocking_in_india == 1
    assert status.active_elsewhere_only == 0


def test_india_status_only_considers_closest_matches():
    """Scoped to the same top_n window used for the novelty deep-dive, so a
    barely-related patent 30 results down doesn't inflate the count."""
    results = [patent(id=f"p{i}", country_status={"US": "ACTIVE"}) for i in range(12)]
    assert compute_india_status(results, top_n=5).active_elsewhere_only == 5


def test_india_status_skips_non_patents():
    scholar = RankedResult(
        id="scholar/1",
        source_type="scholar",
        title="Paper",
        snippet="",
        link="https://example.com",
        relevance_score=0.9,
    )
    assert compute_india_status([scholar]).active_elsewhere_only == 0


# --- Dedupe / merge --------------------------------------------------------


def _bundle(query_type, results):
    return QueryBundle(query_type=query_type, query="q", results=results)


def test_dedupe_merges_same_result_across_queries():
    p = PatentResult(id="patent/US1/en", title="T", link="L")
    search = SearchLayerResult(
        query_bundles=[_bundle("major_markets", [p]), _bundle("broad_recall", [p])],
        market_results=[],
    )
    deduped = _dedupe(search)
    assert len(deduped) == 1
    # Which queries surfaced a result is kept — it's what the landscape graph
    # uses and what makes a result traceable back to a query.
    assert deduped[0][1] == ["major_markets", "broad_recall"]


def test_dedupe_keeps_distinct_results_and_tags_market():
    search = SearchLayerResult(
        query_bundles=[
            _bundle("major_markets", [PatentResult(id="p1", title="A", link="L")]),
            _bundle("broad_recall", [ScholarResult(id="s1", title="B", link="L")]),
        ],
        market_results=[ProductResult(id="https://shop", title="C", link="https://shop")],
    )
    deduped = _dedupe(search)
    assert {r.id for r, _ in deduped} == {"p1", "s1", "https://shop"}
    tags = {r.id: q for r, q in deduped}
    assert tags["https://shop"] == ["market_availability"]


# --- Assignee stats --------------------------------------------------------


def test_parse_assignee_stats_drops_total_row_and_sorts():
    raw = {
        "summary": {
            "assignee": [
                {"key": "Total", "percentage": 100.0},
                {"key": "Acme", "percentage": 4.6},
                {"key": "Globex", "percentage": 9.3},
            ]
        }
    }
    stats = _parse_assignee_stats(raw)
    assert [s.name for s in stats] == ["Globex", "Acme"]


def test_parse_assignee_stats_caps_and_handles_missing():
    raw = {"summary": {"assignee": [{"key": f"C{i}", "percentage": i} for i in range(20)]}}
    assert len(_parse_assignee_stats(raw, top_n=6)) == 6
    assert _parse_assignee_stats({}) == []
    assert _parse_assignee_stats({"summary": {}}) == []


# --- Claim truncation ------------------------------------------------------


def test_truncate_cuts_on_word_boundary():
    out = _truncate("alpha beta gamma delta", max_chars=12)
    assert out.endswith("...")
    assert "delt" not in out  # never cuts mid-word


def test_truncate_leaves_short_text_alone():
    assert _truncate("short", max_chars=100) == "short"


def test_summarize_patent_falls_back_to_snippet_when_details_unavailable():
    """When google_patents_details fails (quota/network) the deep-dive still
    has to produce usable text rather than an empty comparison."""
    assert _summarize_patent_details({}, "the search snippet") == "the search snippet"


def test_summarize_patent_prefers_abstract_and_claims():
    out = _summarize_patent_details(
        {"abstract": "An abstract.", "claims": ["First claim.", "Second claim."]}, "snippet"
    )
    assert "An abstract." in out
    assert "Claim 1: First claim." in out


# --- LLM output guards -----------------------------------------------------


def test_resolve_citations_drops_hallucinated_ids():
    """The model is told to cite only ids it was given; anything else is an
    invented source and must never reach the UI."""
    lookup = {"patent/US1/en": ("Real Patent", "https://real")}
    raw = [
        _RawCitation(claim="valid", result_id="patent/US1/en"),
        _RawCitation(claim="made up", result_id="patent/DOES_NOT_EXIST/en"),
    ]
    resolved = _resolve_citations(raw, lookup)
    assert len(resolved) == 1
    # Links are resolved server-side, never copied from the model.
    assert resolved[0].link == "https://real"
    assert resolved[0].title == "Real Patent"


def test_resolve_assessments_drops_unknown_ids():
    lookup = {"patent/US1/en": ("Real", "https://real")}
    raw = [
        _RawCandidateAssessment(
            result_id="patent/US1/en", overlapping_elements=[], differences=[], verdict="blocking"
        ),
        _RawCandidateAssessment(
            result_id="ghost", overlapping_elements=[], differences=[], verdict="blocking"
        ),
    ]
    assert [a.result_id for a in _resolve_assessments(raw, lookup)] == ["patent/US1/en"]


# --- Cache -----------------------------------------------------------------


@pytest.fixture
def temp_cache(tmp_path, monkeypatch):
    """Redirect the cache to a temp dir so tests never touch the real one —
    it holds demo runs that cost real API quota to regenerate."""
    from app import cache

    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache, "_memory", {})
    return cache


def test_cache_roundtrips_through_disk(temp_cache):
    events = [ProgressEvent(stage="done", message="Analysis complete.")]
    temp_cache.set_cached("My idea", events)

    # Clearing memory simulates a server restart: the whole point of the disk
    # layer is that a cached analysis outlives the process.
    temp_cache._memory.clear()

    recovered = temp_cache.get_cached("My idea")
    assert recovered is not None
    assert recovered[0].stage == "done"


def test_cache_key_is_insensitive_to_whitespace_and_case(temp_cache):
    temp_cache.set_cached("A Smart   Bottle", [ProgressEvent(stage="done", message="m")])
    assert temp_cache.get_cached("a smart bottle") is not None


def test_cache_miss_returns_none(temp_cache):
    assert temp_cache.get_cached("never analyzed") is None


def test_cache_treats_corrupt_file_as_miss(temp_cache, tmp_path):
    """A stale file from an older schema must degrade to 're-run it', never
    break the endpoint."""
    key = temp_cache.cache_key("My idea")
    (tmp_path / f"{key}.json").write_text("{not valid json")
    assert temp_cache.get_cached("My idea") is None


# --- Input validation ------------------------------------------------------


def _run(gen):
    async def collect():
        return [e async for e in gen]

    return asyncio.run(collect())


def test_pipeline_rejects_too_short_input_without_calling_apis():
    from app.pipeline.orchestrator import run_pipeline

    events = _run(run_pipeline("bottle"))
    assert len(events) == 1
    assert events[0].type == "error"


def test_pipeline_rejects_blank_input():
    from app.pipeline.orchestrator import run_pipeline

    assert _run(run_pipeline("      "))[0].type == "error"
    assert _run(run_pipeline(""))[0].type == "error"


def test_cache_payload_is_json_serializable(temp_cache, tmp_path):
    """Guards against a model field that pydantic can dump but json can't."""
    temp_cache.set_cached("idea", [ProgressEvent(stage="done", message="m")])
    written = list(tmp_path.glob("*.json"))[0]
    payload = json.loads(written.read_text())
    assert payload["idea_text"] == "idea"
    assert payload["events"][0]["stage"] == "done"


# --- Public domain finder --------------------------------------------------


def test_public_domain_requires_positive_evidence_of_lapse():
    """All-UNKNOWN means we don't know, which is NOT the same as free. Calling
    an unknown-status patent public domain would be actively dangerous advice."""
    from app.pipeline.public_domain import find_public_domain

    unknown_only = patent(id="u", country_status={"IN": "UNKNOWN", "US": "UNKNOWN"})
    assert find_public_domain([unknown_only]).count == 0


def test_public_domain_excludes_anything_still_active():
    from app.pipeline.public_domain import find_public_domain

    mixed = patent(id="m", country_status={"US": "NOT_ACTIVE", "EP": "ACTIVE"})
    assert find_public_domain([mixed]).count == 0


def test_public_domain_includes_fully_lapsed():
    from app.pipeline.public_domain import find_public_domain

    lapsed = patent(id="l", country_status={"US": "NOT_ACTIVE", "WO": "NOT_ACTIVE"})
    summary = find_public_domain([lapsed])
    assert summary.count == 1
    assert summary.entries[0].lapsed_in == ["US", "WO"]


def test_public_domain_separates_term_expiry_from_early_lapse():
    """A patent past its 20-year term is safely dead; one abandoned early can
    sometimes be revived, so the two are labelled differently."""
    from app.pipeline.public_domain import find_public_domain

    old = patent(id="old", country_status={"US": "NOT_ACTIVE"})
    old.priority_date = "1995-01-01"
    recent = patent(id="recent", country_status={"US": "NOT_ACTIVE"})
    recent.priority_date = "2015-01-01"

    by_id = {e.id: e for e in find_public_domain([old, recent]).entries}
    assert by_id["old"].reason == "term_expired"
    assert by_id["recent"].reason == "lapsed_early"


def test_public_domain_handles_missing_or_malformed_dates():
    from app.pipeline.public_domain import find_public_domain

    p = patent(id="nodate", country_status={"US": "NOT_ACTIVE"})
    p.priority_date = None
    q = patent(id="baddate", country_status={"US": "NOT_ACTIVE"})
    q.priority_date = "not-a-date"

    summary = find_public_domain([p, q])
    assert summary.count == 2
    # Unknown age can't be claimed as term-expired.
    assert all(e.reason == "lapsed_early" for e in summary.entries)


def test_public_domain_ignores_non_patents():
    from app.pipeline.public_domain import find_public_domain

    product = RankedResult(
        id="https://shop",
        source_type="product",
        title="A product",
        snippet="",
        link="https://shop",
        relevance_score=0.9,
    )
    assert find_public_domain([product]).count == 0


# --- Citation chasing ------------------------------------------------------

from app.pipeline.citation_chase import chase_citations
from app.pipeline.deepdive import CandidateDetail, CitationRef, _parse_citation_refs


def ref(patent_id, direction="backward", examiner=False, priority_date="2015-01-01"):
    return CitationRef(
        patent_id=patent_id,
        title=f"Title of {patent_id}",
        direction=direction,
        examiner_cited=examiner,
        priority_date=priority_date,
    )


def candidate(id, refs=(), source_type="patent"):
    return CandidateDetail(
        id=id,
        source_type=source_type,
        title="t",
        link="l",
        summary_text="s",
        citation_refs=list(refs),
    )


def test_parse_citation_refs_reads_both_directions_and_examiner_flag():
    raw = {
        "patent_citations": {
            "original": [
                {"patent_id": "patent/US1/en", "title": " Old ", "examiner_cited": "*"},
                {"title": "no id — skipped"},
            ],
            "family_to_family": [{"patent_id": "patent/US9/en"}],
        },
        "cited_by": {"original": [{"patent_id": "patent/US2/en", "assignee_original": "Acme"}]},
    }
    refs = _parse_citation_refs(raw)
    assert [(r.patent_id, r.direction, r.examiner_cited) for r in refs] == [
        ("patent/US1/en", "backward", True),
        ("patent/US2/en", "forward", False),
    ]
    assert refs[0].title == "Old"
    assert refs[1].assignee == "Acme"


def test_parse_citation_refs_handles_missing_blocks():
    assert _parse_citation_refs({}) == []
    assert _parse_citation_refs({"patent_citations": None, "cited_by": {}}) == []


def test_chase_surfaces_documents_shared_by_multiple_candidates():
    candidates = [
        candidate("a", [ref("patent/X/en"), ref("patent/ONLY_A/en")]),
        candidate("b", [ref("patent/X/en", direction="forward")]),
    ]
    network = chase_citations(candidates, [patent(id="a"), patent(id="b")])
    assert [d.id for d in network.discoveries] == ["patent/X/en"]
    found = network.discoveries[0]
    assert found.referenced_by == ["a", "b"]
    assert found.direction == "both"
    assert found.reason == "shared_reference"
    assert found.link == "https://patents.google.com/patent/X/en"
    assert network.references_scanned == 3


def test_chase_never_rediscovers_documents_already_in_results():
    candidates = [candidate("a", [ref("b")]), candidate("c", [ref("b")])]
    network = chase_citations(candidates, [patent(id="a"), patent(id="b"), patent(id="c")])
    assert network.discoveries == []


def test_chase_counts_distinct_candidates_not_raw_references():
    """One patent citing the same document twice (e.g. both directions) is
    still one opinion, not a consensus."""
    candidates = [candidate("a", [ref("patent/X/en"), ref("patent/X/en", direction="forward")])]
    network = chase_citations(candidates, [patent(id="a")])
    assert all(d.reason != "shared_reference" for d in network.discoveries)


def test_chase_falls_back_to_examiner_citations_of_closest_patent():
    candidates = [
        candidate("scholar1", source_type="scholar"),  # closest, but no citation data
        candidate(
            "a",
            [
                ref("patent/E1/en", examiner=True),
                ref("patent/APPLICANT/en", examiner=False),
                ref("patent/LATER/en", direction="forward", examiner=True),
            ],
        ),
    ]
    network = chase_citations(candidates, [patent(id="a")])
    assert [d.id for d in network.discoveries] == ["patent/E1/en"]
    assert network.discoveries[0].reason == "examiner_cited"


def test_chase_flags_likely_expired_references():
    old = ref("patent/OLD/en", priority_date="1990-01-01")
    candidates = [candidate("a", [old]), candidate("b", [old])]
    assert chase_citations(candidates, [patent(id="a"), patent(id="b")]).discoveries[0].likely_expired


def test_citation_edges_link_results_once_in_citing_direction():
    candidates = [
        candidate("a", [ref("b", direction="backward")]),
        candidate("b", [ref("a", direction="forward")]),  # same relationship seen from b
        candidate("c", [ref("c")]),  # self-reference ignored
    ]
    results = [patent(id="a"), patent(id="b"), patent(id="c")]
    edges = chase_citations(candidates, results).edges
    assert [(e.source, e.target) for e in edges] == [("a", "b")]


# --- Market trends ---------------------------------------------------------

from app.pipeline.market_trends import parse_trend


def trends_response(values):
    return {
        "interest_over_time": {
            "timeline_data": [
                {"date": f"week {i}", "values": [{"query": "q", "extracted_value": v}]}
                for i, v in enumerate(values)
            ]
        }
    }


def test_trend_direction_compares_last_year_to_year_before():
    rising = parse_trend("q", trends_response([40] * 52 + [60] * 52))
    assert rising.direction == "rising" and rising.change_pct == 50
    declining = parse_trend("q", trends_response([80] * 52 + [40] * 52))
    assert declining.direction == "declining"
    steady = parse_trend("q", trends_response([50] * 52 + [52] * 52))
    assert steady.direction == "steady"


def test_trend_too_niche_for_data_is_omitted_not_shown_as_zero_demand():
    assert parse_trend("q", trends_response([0, 0, 3, 0, 1] * 20)) is None


def test_trend_handles_empty_or_malformed_response():
    assert parse_trend("q", {}) is None
    assert parse_trend("q", {"interest_over_time": {"timeline_data": [{"values": []}]}}) is None


# --- India filings / country-filtered search -------------------------------


def test_india_filings_counted_across_all_results():
    results = [patent(id=f"patent/US{i}/en") for i in range(10)] + [
        patent(id="patent/IN202141000001A/en")
    ]
    assert compute_india_status(results).india_filings_found == 1


def test_india_query_is_country_filtered_and_order_preserved(monkeypatch):
    from app.pipeline import search
    from app.pipeline.query_generator import GeneratedQuery, QueryGenerationResult

    calls = []

    def fake_search(query, country=None):
        calls.append((query, country))
        if query == "boom":
            raise RuntimeError("quota exhausted api_key=secret")
        return [], []

    monkeypatch.setattr(search, "search_patents_for_query", fake_search)
    qr = QueryGenerationResult(
        core_concepts=["x"],
        queries=[
            GeneratedQuery(type="major_markets", query="m", rationale=""),
            GeneratedQuery(type="india_specific", query="i", rationale=""),
            GeneratedQuery(type="broad_recall", query="boom", rationale=""),
        ],
    )
    bundles = search.run_patent_scholar_search(qr)
    assert [b.query_type for b in bundles] == ["major_markets", "india_specific", "broad_recall"]
    assert sorted(calls) == [("boom", None), ("i", "IN"), ("m", None)]
    assert bundles[1].country == "IN"
    assert bundles[2].search_failed and not bundles[0].search_failed


# --- Report permalinks -----------------------------------------------------


@pytest.mark.parametrize("key", ["../../etc/passwd", "0c7be2fd33796d9", "0C7BE2FD33796D9A", ""])
def test_report_keys_reject_anything_but_generated_shape(temp_cache, key):
    assert temp_cache.get_cached_by_key(key) is None


def test_report_endpoint_serves_cached_result_only(temp_cache):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.models import AnalysisResult, ResultEvent
    from app.pipeline.india_status import IndiaStatus

    result = AnalysisResult(
        idea_text="My idea",
        ranked_results=[],
        candidate_assessments=[],
        overall_novelty_confidence=0.5,
        differentiation_suggestions=[],
        citations=[],
        india_status=IndiaStatus(blocking_in_india=0, active_elsewhere_only=0),
    )
    temp_cache.set_cached("My idea", [ResultEvent(data=result)])
    key = temp_cache.cache_key("My idea")

    client = TestClient(app)
    response = client.get(f"/report/{key}")
    assert response.status_code == 200
    assert response.json()["report_id"] == key
    assert client.get("/report/ffffffffffffffff").status_code == 404
