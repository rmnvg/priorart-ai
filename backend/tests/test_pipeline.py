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
    assert status.related_active_in_india == 1
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
    assert status.related_active_in_india == 0
    assert status.active_elsewhere_only == 0


def test_india_status_counts_each_patent_once():
    """A patent active in India *and* elsewhere is one blocking result, not
    one in each bucket."""
    results = [patent(id="a", country_status={"IN": "ACTIVE", "US": "ACTIVE", "EP": "ACTIVE"})]
    status = compute_india_status(results)
    assert status.related_active_in_india == 1
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


def test_patent_queries_exclude_papers_and_papers_get_their_own_search(monkeypatch):
    from app.pipeline import search
    from app.pipeline.query_generator import GeneratedQuery, QueryGenerationResult

    calls = []

    def fake_client_search(**params):
        calls.append(params)
        if params.get("patents") is False:
            return {"organic_results": [{"is_scholar": True, "scholar_id": "1", "title": "Paper"}]}
        return {"organic_results": [{"patent_id": "patent/US1/en", "title": "Patent"}]}

    monkeypatch.setattr(search._client, "search", fake_client_search)
    search.search_patents_for_query("q")
    # Papers crowd patents off a mixed page, so patent queries never ask for them.
    assert "scholar" not in calls[0] and calls[0]["num"] == search.PATENT_RESULTS_PER_QUERY

    qr = QueryGenerationResult(core_concepts=["x"], queries=[
        GeneratedQuery(type="major_markets", query="m", rationale=""),
        GeneratedQuery(type="broad_recall", query="b", rationale=""),
    ])
    bundle = search.run_literature_search(qr)
    assert calls[-1] == {"engine": "google_patents", "q": "b", "scholar": True, "patents": False}
    assert [r.source_type for r in bundle.results] == ["scholar"]
    assert search.run_literature_search(QueryGenerationResult(core_concepts=["x"], queries=[])) is None


def test_failed_paper_search_is_an_empty_failed_bundle(monkeypatch):
    from app.pipeline import search
    from app.pipeline.query_generator import GeneratedQuery, QueryGenerationResult

    def boom(query):
        raise RuntimeError("quota exhausted api_key=secret")

    monkeypatch.setattr(search, "search_literature", boom)
    qr = QueryGenerationResult(core_concepts=["x"], queries=[
        GeneratedQuery(type="broad_recall", query="b", rationale=""),
    ])
    bundle = search.run_literature_search(qr)
    assert bundle.search_failed and bundle.results == []


def test_deep_dive_gives_patents_the_detail_slots_first():
    from app.pipeline.deepdive import select_candidates

    def r(i, kind):
        return RankedResult(id=i, source_type=kind, title=i, snippet="", link="", relevance_score=0)

    ranked = [r("s1", "scholar"), r("p1", "patent"), r("x", "product"), r("s2", "scholar"),
              r("p2", "patent"), r("s3", "scholar")]
    # Patents fill the slots ahead of better-ranked papers; order follows the ranking.
    assert [c.id for c in select_candidates(ranked, 2)] == ["p1", "p2"]
    # Leftover slots go to papers, never to products.
    assert [c.id for c in select_candidates(ranked, 4)] == ["s1", "p1", "s2", "p2"]


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
        india_status=IndiaStatus(related_active_in_india=0, active_elsewhere_only=0),
    )
    temp_cache.set_cached("My idea", [ResultEvent(data=result)])
    key = temp_cache.cache_key("My idea")

    client = TestClient(app)
    response = client.get(f"/report/{key}")
    assert response.status_code == 200
    assert response.json()["report_id"] == key
    assert client.get("/report/ffffffffffffffff").status_code == 404


# --- Language support ------------------------------------------------------

from app.pipeline import language as language_mod


def test_english_detection_needs_no_llm_call():
    assert language_mod.looks_english("A solar-powered crop dryer with a café-style vent")
    assert not language_mod.looks_english("सौर ऊर्जा से चलने वाला फसल सुखाने का यंत्र")
    assert not language_mod.looks_english("சூரிய சக்தியில் இயங்கும் உலர்த்தி")


def test_translation_failure_falls_back_to_original_text(monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("LLM did not return valid JSON")

    monkeypatch.setattr(language_mod, "complete_json", broken)
    result = language_mod.detect_and_translate("सौर ऊर्जा से चलने वाला यंत्र")
    assert result.code == "und"
    assert result.english_text == "सौर ऊर्जा से चलने वाला यंत्र"


def test_localization_discarded_when_lists_change_length(monkeypatch):
    """A dropped suggestion would shift every 'Apply' button onto the wrong
    text — English is better than misaligned."""
    monkeypatch.setattr(
        language_mod,
        "complete_json",
        lambda *a, **k: {
            "plain_summary": "सार",
            "differentiation_suggestions": ["एक"],  # two went in
            "citation_claims": [],
            "ui_labels": {},
        },
    )
    assert language_mod.localize_report("hi", "Hindi", "summary", ["one", "two"], []) is None


def test_localization_fills_missing_labels_with_english(monkeypatch):
    monkeypatch.setattr(
        language_mod,
        "complete_json",
        lambda *a, **k: {
            "plain_summary": "सार",
            "differentiation_suggestions": ["एक"],
            "citation_claims": ["दावा"],
            "ui_labels": {"novelty_verdict": "नवीनता"},
        },
    )
    localized = language_mod.localize_report("hi", "Hindi", "summary", ["one"], ["claim"])
    assert localized.ui_labels["novelty_verdict"] == "नवीनता"
    assert localized.ui_labels["based_on"] == "Based on:"
    assert set(localized.ui_labels) == set(language_mod.UI_LABELS)


# --- Refinement agent ------------------------------------------------------

from app.pipeline import refine as refine_mod
from app.pipeline.query_generator import GeneratedQuery, QueryGenerationResult


def _query_result():
    return QueryGenerationResult(
        core_concepts=["paddle"],
        queries=[GeneratedQuery(type="major_markets", query="(paddle) (folding)", rationale="")],
    )


def test_refinement_drops_repeated_queries_and_caps_count(monkeypatch):
    monkeypatch.setattr(
        refine_mod,
        "complete_json",
        lambda *a, **k: {
            "observation": "Patents call this a sectional shaft.",
            "new_terms": ["sectional shaft"],
            "queries": ["(PADDLE) (folding)", '("sectional shaft")', "(oar) (joint)"],
        },
    )
    plan = refine_mod.plan_refinement("idea text", _query_result(), [patent()], max_queries=1)
    assert [q.query for q in plan.queries] == ['("sectional shaft")']
    assert plan.queries[0].type == "refined"
    assert plan.new_terms == ["sectional shaft"]


def test_refinement_switches_to_broader_queries_when_nothing_found(monkeypatch):
    prompts = []

    def fake(prompt, **kwargs):
        prompts.append(prompt)
        return {"observation": "Broadening.", "queries": ["(paddle)"]}

    monkeypatch.setattr(refine_mod, "complete_json", fake)
    refine_mod.plan_refinement("idea text", _query_result(), [], max_queries=2)
    assert "returned NOTHING" in prompts[0]


def test_refinement_disabled_or_failing_returns_none(monkeypatch):
    assert refine_mod.plan_refinement("idea", _query_result(), [], max_queries=0) is None

    def broken(*a, **k):
        raise ValueError("bad json")

    monkeypatch.setattr(refine_mod, "complete_json", broken)
    assert refine_mod.plan_refinement("idea", _query_result(), [patent()], max_queries=1) is None


# --- Orchestrator, end to end with every external call faked ----------------

from app.pipeline import orchestrator as orch
from app.pipeline.language import IdeaLanguage, LocalizedContent
from app.pipeline.novelty import NoveltyAssessment
from app.pipeline.refine import RefinementPlan


def _fake_pipeline(monkeypatch, *, language_code="en", refinement=True):
    searched: list[list[str]] = []

    def fake_translate(text):
        if language_code == "en":
            return IdeaLanguage(code="en", name="English", english_text=text)
        return IdeaLanguage(code=language_code, name="Hindi", english_text="english version")

    def fake_run_queries(queries):
        searched.append([q.query for q in queries])
        return [QueryBundle(query_type=q.type, query=q.query, results=[]) for q in queries]

    def fake_rank(search_result, idea):
        return [patent(id=f"patent/US{i}/en") for i in range(len(search_result.query_bundles))]

    monkeypatch.setattr(orch, "detect_and_translate", fake_translate)
    monkeypatch.setattr(orch, "generate_queries", lambda idea: _query_result())
    monkeypatch.setattr(orch, "run_queries", fake_run_queries)
    monkeypatch.setattr(orch, "run_market_search", lambda qr: [])
    monkeypatch.setattr(
        orch,
        "run_literature_search",
        lambda qr: QueryBundle(query_type="broad_recall", query="papers", results=[]),
    )
    monkeypatch.setattr(orch, "fetch_market_trend", lambda kw: None)
    monkeypatch.setattr(orch, "rank_and_dedupe", fake_rank)
    monkeypatch.setattr(orch, "deep_dive", lambda ranked, n: [])
    monkeypatch.setattr(
        orch,
        "assess_novelty",
        lambda *a: NoveltyAssessment(
            candidate_assessments=[],
            overall_novelty_confidence=0.6,
            differentiation_suggestions=["add a hinge"],
            citations=[],
            claim_chart_pairs=[],
            plain_summary="Plain summary.",
        ),
    )
    monkeypatch.setattr(
        orch,
        "plan_refinement",
        lambda *a: RefinementPlan(
            observation="Patents say 'sectional shaft'.",
            new_terms=["sectional shaft"],
            queries=[GeneratedQuery(type="refined", query='("sectional shaft")', rationale="r")],
        )
        if refinement
        else None,
    )
    monkeypatch.setattr(
        orch,
        "localize_report",
        lambda code, name, summary, suggestions, claims: LocalizedContent(
            language_code=code,
            language_name=name,
            plain_summary="सार",
            differentiation_suggestions=["कब्ज़ा जोड़ें"],
            citation_claims=[],
            ui_labels={},
        ),
    )
    return searched


def test_pipeline_runs_refinement_round_and_records_it(monkeypatch):
    searched = _fake_pipeline(monkeypatch)
    events = _run(orch.run_pipeline("A folding kayak paddle idea"))

    messages = [e.message for e in events if e.type == "progress"]
    assert "Patents say 'sectional shaft'." in messages
    assert searched == [["(paddle) (folding)"], ['("sectional shaft")']]

    result = events[-1].data
    strategy = result.search_strategy
    assert [q.type for q in strategy.queries] == ["major_markets", "refined"]
    assert strategy.refinement_terms == ["sectional shaft"]
    # Two patent queries plus the separate papers search.
    assert strategy.serpapi_calls["google_patents"] == 3
    # Re-ranked over both rounds, with the papers bundle included.
    assert len(result.ranked_results) == 3
    assert result.plain_summary == "Plain summary."
    assert result.language_code == "en" and result.localized is None


def test_pipeline_translates_idea_and_localizes_report(monkeypatch):
    _fake_pipeline(monkeypatch, language_code="hi", refinement=False)
    events = _run(orch.run_pipeline("सौर ऊर्जा से चलने वाला फसल सुखाने का यंत्र"))

    result = events[-1].data
    assert result.idea_text == "english version"  # pipeline ran on English
    assert result.original_idea_text == "सौर ऊर्जा से चलने वाला फसल सुखाने का यंत्र"
    assert result.language_code == "hi"
    assert result.localized.differentiation_suggestions == ["कब्ज़ा जोड़ें"]
    assert any("Hindi" in e.message for e in events if e.type == "progress")


def test_pipeline_forced_language_localizes_english_idea(monkeypatch):
    """'Apply & re-check' on a Hindi report sends English text plus
    language=hi — the re-checked report must still come back in Hindi."""
    _fake_pipeline(monkeypatch, refinement=False)
    result = _run(orch.run_pipeline("A folding kayak paddle idea", language="hi"))[-1].data
    assert result.language_code == "hi"
    assert result.language_name == "Hindi"
    assert result.original_idea_text is None


# --- Demo mode and examples gallery ----------------------------------------


def _result_event(idea="My idea"):
    from app.models import AnalysisResult, ResultEvent
    from app.pipeline.india_status import IndiaStatus

    return ResultEvent(
        data=AnalysisResult(
            idea_text=idea,
            ranked_results=[],
            candidate_assessments=[],
            overall_novelty_confidence=0.5,
            differentiation_suggestions=[],
            citations=[],
            india_status=IndiaStatus(related_active_in_india=0, active_elsewhere_only=0),
        )
    )


def test_demo_mode_refuses_new_analyses_but_serves_cached(temp_cache, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main, service

    monkeypatch.setattr(service, "LIVE_MODE", False)
    temp_cache.set_cached("Cached idea here", [_result_event("Cached idea here")])
    client = TestClient(main.app)

    fresh = client.post("/analyze", json={"idea_text": "A never analyzed idea"})
    assert "demo mode" in fresh.text
    cached = client.post("/analyze", json={"idea_text": "Cached idea here"})
    assert '"type":"result"' in cached.text


def test_examples_gallery_skips_rechecks(temp_cache):
    from fastapi.testclient import TestClient

    from app.main import app

    temp_cache.set_cached("Original idea", [_result_event("Original idea")])
    temp_cache.set_cached(
        "Original idea. Additionally, x",
        [_result_event("Original idea. Additionally, x")],
        parent_report_id=temp_cache.cache_key("Original idea"),
    )
    examples = TestClient(app).get("/examples").json()
    assert [e["idea_text"] for e in examples] == ["Original idea"]


def test_report_language_is_part_of_the_cache_identity():
    from app.service import report_id_for

    assert report_id_for("Idea", None) != report_id_for("Idea", "hi")
    assert report_id_for("Idea", "HI") == report_id_for("Idea", "hi")


def test_queries_are_cleaned_of_typographic_punctuation():
    from app.pipeline.search import clean_query

    assert clean_query("(“modular shaft” OR foam‑filled)  (paddle)") == '("modular shaft" OR foam-filled) (paddle)'


# --- MCP report rendering --------------------------------------------------


def test_mcp_markdown_leads_with_verdict_and_links_report():
    from app.report_markdown import report_to_markdown

    result = _result_event().data
    result.overall_novelty_confidence = 0.2
    result.plain_summary = "Close matches exist."
    result.differentiation_suggestions = ["Add a hinge"]
    md = report_to_markdown(result, "http://localhost:3000/?report=abc")
    # Older reports without feature findings: the model's verdict, labelled as
    # an estimate, never a bare percentage.
    assert md.startswith("## Prior-art check: heavy overlap with existing prior art (model estimate)")
    assert "20%" not in md
    assert "Close matches exist." in md
    assert "1. Add a hinge" in md
    assert md.rstrip().endswith("not legal advice._")
    assert "http://localhost:3000/?report=abc" in md


# --- Benchmark scoring -----------------------------------------------------

from benchmark.run import Case, CaseResult, find_rank, summarize


def _case():
    return Case(
        id="coffee-pod",
        patent="US5325765A",
        patent_title="Beverage filter cartridge",
        priority_date="1992-09-16",
        idea="A coffee pod",
    )


def test_benchmark_matches_any_kind_code_but_not_longer_numbers():
    ranked = [
        patent(id="patent/US53257650A/en"),  # longer number: not a match
        patent(id="patent/US5325765B1/en"),  # same number, different kind code
    ]
    assert find_rank(ranked, _case()) == (2, "exact")


def test_benchmark_matches_same_titled_family_member_and_skips_products():
    product = RankedResult(
        id="https://shop.example/pod", source_type="product", title="Pods",
        snippet="", link="", relevance_score=0.9,
    )
    family = patent(id="patent/EP0659057A1/en")
    family.title = "Beverage Filter Cartridge"
    assert find_rank([product, family], _case()) == (1, "family")
    assert find_rank([product], _case()) == (None, None)
    # An exact match lower down beats a same-title lookalike above it.
    assert find_rank([family, patent(id="patent/US5325765A/en")], _case()) == (2, "exact")


def test_benchmark_summary_excludes_errored_cases():
    results = [
        CaseResult(id="a", patent="p", rank_before=3, rank_after=1, match_before="family",
                   match_after="exact", results_before=5, results_after=6, searches_used=4),
        CaseResult(id="b", patent="p", rank_before=2, rank_after=12, match_before="exact",
                   match_after="exact", results_before=5, results_after=6, searches_used=4),
        CaseResult(id="c", patent="p", rank_before=None, rank_after=None, results_before=0,
                   results_after=0, searches_used=3, error="all searches failed"),
    ]
    s = summarize(results)
    assert s["cases"] == 2 and s["errors"] == 1
    assert s["top10_before"] == 1.0 and s["top10_after"] == 0.5
    assert s["top10_exact_before"] == 0.5 and s["top10_exact_after"] == 0.5
    assert s["top1_after"] == 0.5 and s["found_after"] == 1.0
    assert s["refinement_improved"] == 1 and s["refinement_worsened"] == 1
    assert s["searches_used"] == 11


# --- Sample ideas stay pre-cached --------------------------------------------


def test_frontend_samples_match_the_warmed_examples():
    """The home page's sample buttons must send text the warm-up script
    caches, byte for byte — otherwise they silently become slow, billable
    live runs in the middle of a demo."""
    import re
    from pathlib import Path

    from scripts.warm_examples import EXAMPLES

    ts = (Path(__file__).resolve().parents[2] / "frontend/lib/sampleIdea.ts").read_text()
    # Each export is string literals joined with "+", ending at ";".
    samples = [
        "".join(re.findall(r'"(.*?)"', body))
        for body in re.findall(r"export const \w+ =(.*?);", ts, flags=re.S)
    ]
    assert len(samples) == 2
    assert samples[0] == EXAMPLES["kayak"]
    assert samples[1] == EXAMPLES["solar-dryer-hindi"]


def test_evict_removes_memory_and_disk(temp_cache, tmp_path):
    temp_cache.set_cached("Idea to forget", [ProgressEvent(stage="done", message="m")])
    key = temp_cache.cache_key("Idea to forget")
    temp_cache.evict(key)
    assert temp_cache.get_cached("Idea to forget") is None
    assert not (tmp_path / f"{key}.json").exists()


# --- Ask about this report ---------------------------------------------------

from app.pipeline import ask as ask_mod


def _report_for_ask():
    result = _result_event("A folding paddle").data
    result.ranked_results = [
        patent(id="patent/US1/en", country_status={"US": "ACTIVE"}),
        patent(id="patent/US2/en", country_status={"US": "NOT_ACTIVE"}),
    ]
    return result


def test_ask_context_lists_documents_with_keys_and_legal_status():
    result = _report_for_ask()
    table = ask_mod._document_table(result)
    context = ask_mod.build_context(result, table)
    assert list(table) == ["D1", "D2"]
    assert "[D1] A patent" in context and "in force in US" in context
    assert "[D2] A patent" in context and "lapsed in US" in context


def test_ask_citations_normalize_bare_and_grouped_keys_and_drop_invented_ones():
    table = ask_mod._document_table(_report_for_ask())
    answer = ask_mod.resolve_citations("Closest is D2, see [D1, D2] and [D9] .", table)
    assert answer.answer == "Closest is [D2], see [D1][D2] and."
    assert [s.key for s in answer.sources] == ["D2", "D1"]
    assert answer.sources[0].link == "https://example.com"


def test_ask_sends_only_recent_history(monkeypatch):
    prompts = []

    def fake(prompt, **kwargs):
        prompts.append(prompt)
        return {"answer": "It lapsed [D2]."}

    monkeypatch.setattr(ask_mod, "complete_json", fake)
    history = [ask_mod.AskTurn(question=f"q{i}", answer=f"a{i}") for i in range(6)]
    answer = ask_mod.answer_question(_report_for_ask(), "and in India?", history)
    assert answer.sources[0].key == "D2"
    assert "Q: q5" in prompts[0] and "Q: q1" not in prompts[0]
    assert "QUESTION: and in India?" in prompts[0]


def test_ask_endpoint_needs_llm_key_and_a_real_report(temp_cache, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main

    client = TestClient(main.app)
    monkeypatch.setattr(main, "GROQ_API_KEY", "")
    assert client.post("/report/ffffffffffffffff/ask", json={"question": "Why?"}).status_code == 503

    monkeypatch.setattr(main, "GROQ_API_KEY", "key")
    assert client.post("/report/ffffffffffffffff/ask", json={"question": "Why?"}).status_code == 404
    assert client.post("/report/ffffffffffffffff/ask", json={"question": ""}).status_code == 422

    temp_cache.set_cached("Folding paddle idea", [_result_event("Folding paddle idea")])
    key = temp_cache.cache_key("Folding paddle idea")
    monkeypatch.setattr(
        main, "answer_question", lambda r, q, h: ask_mod.ReportAnswer(answer="Yes.", sources=[])
    )
    response = client.post(f"/report/{key}/ask", json={"question": "Can I sell it?"})
    assert response.status_code == 200 and response.json()["answer"] == "Yes."


def test_ui_labels_match_frontend_english_labels():
    """Localized labels are keyed by these strings on both sides; a key or
    wording that drifts means a label silently never translates."""
    import re
    from pathlib import Path

    ts = (Path(__file__).resolve().parents[2] / "frontend/lib/i18n.ts").read_text()
    block = re.search(r"const ENGLISH_LABELS = \{(.*?)\} as const", ts, re.S).group(1)
    frontend = {}
    for key, value in re.findall(r'(\w+):\s*\n?\s*"((?:[^"\\]|\\.)*)"', block):
        frontend[key] = value
    assert frontend == language_mod.UI_LABELS


# --- Examination preview -------------------------------------------------------

from app.pipeline import examination as exam


def _exam_docs(*texts, cpcs=None):
    cpcs = cpcs or [None] * len(texts)
    return [
        exam._Doc(
            meta=exam.ExaminedDoc(key=f"D{i}", id=f"patent/US{i}/en", title=f"Doc {i}", link="l", source_type="patent"),
            text=t,
            cpc_code=cpcs[i - 1],
            relevance=0.5,
        )
        for i, t in enumerate(texts, start=1)
    ]


def _elements(n):
    return [exam.Element(id=f"E{i}", text=f"element {i}") for i in range(1, n + 1)]


def _cov(element, document, status="disclosed"):
    return exam.Coverage(element=element, document=document, status=status, quote="q q q q")


def test_quotes_must_really_occur_in_the_document():
    text = "A paddle shaft comprising four hollow segments that interlock, each sealed and buoyant."
    assert exam.quote_is_verified("four hollow segments that interlock", text)
    assert exam.quote_is_verified("FOUR HOLLOW  segments that interlock…", text)  # case, spacing, ellipsis
    assert exam.quote_is_verified("each sealed and buoyant.", text)
    assert not exam.quote_is_verified("four hollow segments that snap together", text)  # paraphrase
    assert not exam.quote_is_verified("hollow segments", text)  # too short to be evidence


def test_verify_coverage_drops_unverifiable_and_unknown_findings():
    docs = _exam_docs("The shaft has four hollow segments that interlock tightly.")
    raw = [
        exam._RawCoverage(element="e1", document="d1", status="partial", quote="four hollow segments that interlock"),
        exam._RawCoverage(element="E1", document="D1", status="disclosed", quote="four hollow segments that interlock tightly"),
        exam._RawCoverage(element="E2", document="D1", status="disclosed", quote="made entirely of bamboo fibre sheets"),
        exam._RawCoverage(element="E9", document="D1", status="disclosed", quote="four hollow segments that interlock"),
        exam._RawCoverage(element="E1", document="D7", status="disclosed", quote="four hollow segments that interlock"),
    ]
    coverage, dropped = exam.verify_coverage(raw, _elements(2), docs)
    assert [(c.element, c.document, c.status) for c in coverage] == [("E1", "D1", "disclosed")]
    assert dropped == 1  # the invented bamboo quote


def test_single_document_disclosing_everything_is_a_novelty_objection():
    docs = _exam_docs("a", "b")
    coverage = [_cov("E1", "D1"), _cov("E2", "D1"), _cov("E1", "D2")]
    outcome, anticipating, pairs, uncovered = exam.compute_objections(_elements(2), docs, coverage)
    assert outcome == "novelty_objection"
    assert anticipating == ["D1"] and pairs == [] and uncovered == []


def test_two_documents_together_raise_inventive_step_same_field_first():
    docs = _exam_docs("a", "b", "c", cpcs=["B63H16/04", "A01B1/00", "B63H16/08"])
    coverage = [_cov("E1", "D1"), _cov("E2", "D2"), _cov("E2", "D3")]
    outcome, anticipating, pairs, uncovered = exam.compute_objections(_elements(2), docs, coverage)
    assert outcome == "inventive_step_objection" and anticipating == []
    assert [p.documents for p in pairs] == [["D1", "D3"], ["D1", "D2"]]
    assert pairs[0].same_field and not pairs[1].same_field


def test_partial_findings_never_ground_an_objection():
    docs = _exam_docs("a")
    coverage = [_cov("E1", "D1"), _cov("E2", "D1", status="partial")]
    outcome, _, _, uncovered = exam.compute_objections(_elements(2), docs, coverage)
    assert outcome == "no_objection_found"
    assert uncovered == ["E2"]


def test_everything_covered_only_across_three_documents_is_a_combination_risk():
    docs = _exam_docs("a", "b", "c")
    coverage = [_cov("E1", "D1"), _cov("E2", "D2"), _cov("E3", "D3")]
    outcome, anticipating, pairs, uncovered = exam.compute_objections(_elements(3), docs, coverage)
    assert outcome == "combination_risk" and not anticipating and not pairs and not uncovered


def test_section3_screen_keeps_fixed_law_text_and_drops_unknown_clauses(monkeypatch):
    monkeypatch.setattr(
        exam,
        "complete_json",
        lambda *a, **k: {
            "elements": ["a paste of turmeric and neem", "applied to wounds"],
            "section3": [
                {"clause": "3(p)", "risk": "possible", "reason": "r1", "how_to_address": "h1"},
                {"clause": "3 (e)", "risk": "high", "reason": "r2", "how_to_address": "h2"},
                {"clause": "3(z)", "risk": "high", "reason": "invented", "how_to_address": "x"},
            ],
        },
    )
    elements, flags = exam._screen("A turmeric and neem wound paste")
    assert [e.id for e in elements] == ["E1", "E2"]
    assert [f.clause for f in flags] == ["3(e)", "3(p)"]  # high risk first; 3(z) dropped
    assert flags[1].law_summary == exam.SECTION_3["3(p)"][1]


def test_documents_fall_back_to_snippets_for_older_reports():
    from app.models import ExaminedDocument

    result = _result_event().data
    result.ranked_results = [patent(id="patent/US1/en"), patent(id="patent/US2/en")]
    docs, basis = exam.select_documents(result)
    assert basis == "snippets" and [d.meta.key for d in docs] == ["D1", "D2"]

    result.examined_documents = [
        ExaminedDocument(id="patent/US2/en", source_type="patent", title="T", link="l", text="full text")
    ]
    docs, basis = exam.select_documents(result)
    assert basis == "full_text" and docs[0].text == "full text"


def test_examination_endpoint_computes_once_then_serves_cache(temp_cache, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main, service

    temp_cache.set_cached("Folding paddle idea", [_result_event("Folding paddle idea")])
    key = temp_cache.cache_key("Folding paddle idea")
    client = TestClient(main.app)

    monkeypatch.setattr(service, "GROQ_API_KEY", "")
    assert client.post(f"/report/{key}/examination").status_code == 503
    assert client.post("/report/ffffffffffffffff/examination").status_code == 404

    calls = []

    def fake_preview(report):
        calls.append(report.idea_text)
        return exam.ExaminationPreview(
            outcome="no_objection_found", elements=_elements(2), documents=[], coverage=[],
            novelty_objections=[], inventive_step_objections=[], uncovered_elements=["E1", "E2"],
            section3_flags=[], evidence_basis="snippets", unverified_quotes_dropped=0,
        )

    monkeypatch.setattr(service, "GROQ_API_KEY", "key")
    monkeypatch.setattr(service, "preview_examination", fake_preview)
    first = client.post(f"/report/{key}/examination")
    second = client.post(f"/report/{key}/examination")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(calls) == 1  # second request came from the cache

    # The attachment isn't mistaken for a report, and goes when the report does.
    assert [e["report_id"] for e in client.get("/examples").json()] == [key]
    temp_cache.evict(key)
    assert temp_cache.get_attachment(key, "examination") is None


def test_examination_markdown_is_labelled_a_simulation():
    from app.report_markdown import examination_to_markdown

    preview = exam.ExaminationPreview(
        outcome="novelty_objection", elements=_elements(1),
        documents=[exam.ExaminedDoc(key="D1", id="x", title="Paddle", link="https://x", source_type="patent")],
        coverage=[], novelty_objections=["D1"], inventive_step_objections=[], uncovered_elements=[],
        section3_flags=[], evidence_basis="full_text", unverified_quotes_dropped=0,
    )
    md = examination_to_markdown(preview)
    assert "simulated — not issued by the Indian Patent Office" in md
    assert "lack of novelty" in md and "[Paddle](https://x)" in md


def test_replayed_runs_are_marked_as_replays(temp_cache, monkeypatch):
    from app import service

    monkeypatch.setattr(service, "REPLAY_STEP_SECONDS", 0)
    temp_cache.set_cached(
        "Saved idea text", [ProgressEvent(stage="done", message="m"), _result_event("Saved idea text")]
    )
    events = _run(service.analyze("Saved idea text"))
    assert events[0].type == "progress" and events[0].replayed is True
    assert events[1].type == "result"
    # The cached copy itself stays unmarked, so a later live run isn't confused.
    assert temp_cache.get_cached("Saved idea text")[0].replayed is False


# --- Evidence-backed re-check ----------------------------------------------

from app.pipeline import recheck as recheck_mod
from app.pipeline.novelty import CandidateAssessment


def _assessment(result_id, verdict):
    return CandidateAssessment(
        result_id=result_id, title=f"T {result_id}", link="l",
        overlapping_elements=[], differences=[], verdict=verdict,
    )


def _recheck_pair():
    from app.models import ExaminedDocument

    parent = _result_event("A folding paddle").data
    parent.ranked_results = [patent(id="a", score=0.9), patent(id="b", score=0.8), patent(id="c", score=0.7)]
    parent.candidate_assessments = [
        _assessment("c", "not_relevant"), _assessment("b", "partially_overlapping"), _assessment("a", "blocking"),
    ]
    parent.examined_documents = [
        ExaminedDocument(id="a", source_type="patent", title="T a", link="l",
                         text="A paddle with four hollow segments that interlock and float on water."),
        ExaminedDocument(id="b", source_type="patent", title="T b", link="l",
                         text="An oar that has an inflatable bladder inside the shaft for extra buoyancy."),
    ]
    revised = _result_event("A folding paddle. Additionally, add a bladder").data
    revised.ranked_results = [patent(id="a"), patent(id="new1"), patent(id="new2")]
    revised.candidate_assessments = [
        _assessment("new2", "partially_overlapping"), _assessment("new1", "blocking"),
        _assessment("a", "blocking"),  # already in the original search: not "new"
    ]
    return parent, revised


def test_recheck_keeps_original_matches_and_trusts_only_verified_quotes(monkeypatch):
    parent, revised = _recheck_pair()
    monkeypatch.setattr(
        recheck_mod,
        "complete_json",
        lambda *a, **k: {
            "documents": [
                {"key": "D1", "change_quote": "", "explanation": "No bladder here.",
                 "still_shared": [
                     {"feature": "hollow segments", "quote": "four hollow segments that interlock"},
                     {"feature": "invented", "quote": "a bladder made of bamboo fibre"},
                 ]},
                {"key": "D2", "change_quote": "an inflatable bladder inside the shaft", "explanation": "Has it."},
            ]
        },
    )
    comparison = recheck_mod.compare_recheck(parent, "abc", revised, "add a bladder")
    first, second = comparison.original_matches
    assert (first.id, second.id) == ("a", "b")  # blocking first; the irrelevant one left out
    assert not first.change_found_in_document and first.change_quote is None
    assert [s.feature for s in first.still_shared] == ["hollow segments"]  # invented quote dropped
    assert second.change_found_in_document and second.change_quote
    assert [m.id for m in comparison.new_matches] == ["new1", "new2"]
    assert comparison.confidence_before == parent.overall_novelty_confidence
    assert comparison.evidence_basis == "full_text"


def test_recheck_unverifiable_change_quote_means_not_found(monkeypatch):
    parent, revised = _recheck_pair()
    monkeypatch.setattr(
        recheck_mod,
        "complete_json",
        lambda *a, **k: {"documents": [{"key": "D1", "change_quote": "a bladder in every segment of it"}]},
    )
    comparison = recheck_mod.compare_recheck(parent, "abc", revised, "add a bladder")
    assert comparison.original_matches[0].change_found_in_document is False
    # D2 was skipped by the model: still reported, with no evidence claimed.
    assert comparison.original_matches[1].still_shared == []


def test_recheck_model_failure_falls_back_to_none(monkeypatch):
    parent, revised = _recheck_pair()

    def broken(*a, **k):
        raise ValueError("bad json")

    monkeypatch.setattr(recheck_mod, "complete_json", broken)
    assert recheck_mod.compare_recheck(parent, "abc", revised, "add a bladder") is None


def test_pipeline_attaches_recheck_only_for_rechecks(monkeypatch):
    _fake_pipeline(monkeypatch, refinement=False)
    calls = []
    monkeypatch.setattr(
        orch, "compare_recheck",
        lambda parent, pid, result, change: calls.append((pid, change)) or None,
    )
    _run(orch.run_pipeline("A folding kayak paddle idea"))
    assert calls == []
    parent = _result_event("A folding kayak paddle idea").data
    _run(orch.run_pipeline("A folding kayak paddle idea. Additionally, x", parent=parent,
                           parent_report_id="abc", applied_change="x"))
    assert calls == [("abc", "x")]


def test_recheck_explanations_never_show_internal_document_keys():
    assert recheck_mod._without_keys("so the change distinguishes the invention from D1.") == (
        "so the change distinguishes the invention from this document."
    )
    assert recheck_mod._without_keys("D2 does not describe it") == "this document does not describe it"
    assert recheck_mod._without_keys("Uses DC motors and D-rings") == "Uses DC motors and D-rings"


# --- Sketch input ----------------------------------------------------------

import base64

from app.pipeline import sketch as sketch_mod

_PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()


@pytest.mark.parametrize(
    "data_url",
    [
        "not a data url",
        "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
        "data:image/png;base64,",
        "data:text/plain;base64,aGVsbG8=",
    ],
)
def test_sketch_rejects_anything_but_a_supported_image(data_url):
    with pytest.raises(sketch_mod.SketchUnreadable):
        sketch_mod.decode_image(data_url)


def test_sketch_rejects_oversized_images(monkeypatch):
    monkeypatch.setattr(sketch_mod, "MAX_IMAGE_BYTES", 10)
    with pytest.raises(sketch_mod.SketchUnreadable, match="too large"):
        sketch_mod.decode_image(_PNG)


def test_sketch_reading_keeps_only_connections_between_real_parts():
    raw = sketch_mod._RawReading(
        purpose="  Keeps  vegetables cool ",
        components=[
            sketch_mod._RawComponent(id="C1", name="Outer clay pot", description="Unglazed."),
            sketch_mod._RawComponent(id="C2", name="", description="unnamed: dropped"),
            sketch_mod._RawComponent(id="C3", name="Wet sand", description="Fills the gap."),
            sketch_mod._RawComponent(id="C4", name="outer clay pot", description="duplicate"),
        ],
        relationships=[
            sketch_mod._RawRelationship(source="C3", target="C1", relation="fills"),
            sketch_mod._RawRelationship(source="C3", target="C1", relation="fills"),  # repeat
            sketch_mod._RawRelationship(source="C1", target="C1", relation="touches"),  # self
            sketch_mod._RawRelationship(source="C1", target="C9", relation="feeds"),  # unknown
            sketch_mod._RawRelationship(source="C1", target="C2", relation="holds"),  # dropped part
        ],
        uncertain=["Is the pot glazed?", "  "],
    )
    reading = sketch_mod.build_reading(raw)
    assert reading.purpose == "Keeps vegetables cool"
    # Renumbered after the unnamed part was dropped, and connections follow.
    assert [(c.id, c.name) for c in reading.components] == [("C1", "Outer clay pot"), ("C2", "Wet sand")]
    assert [(r.source, r.target, r.relation) for r in reading.relationships] == [("C2", "C1", "fills")]
    assert reading.uncertain == ["Is the pot glazed?"]


def test_sketch_relations_name_parts_instead_of_ids():
    raw = sketch_mod._RawReading(
        components=[
            sketch_mod._RawComponent(id="C1", name="Outer pot"),
            sketch_mod._RawComponent(id="C2", name="Inner pot"),
            sketch_mod._RawComponent(id="C3", name="Wet sand"),
        ],
        relationships=[
            sketch_mod._RawRelationship(source="C3", target="C1", relation="fills the gap between C2 and"),
        ],
    )
    (relation,) = sketch_mod.build_reading(raw).relationships
    assert relation.relation == "fills the gap between Inner pot and"


def test_sketch_with_no_parts_is_refused_with_advice():
    with pytest.raises(sketch_mod.SketchUnreadable, match="clearer photo"):
        sketch_mod.build_reading(sketch_mod._RawReading(components=[]))


def test_sketch_endpoint_reads_once_then_serves_cache(temp_cache, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main, service

    client = TestClient(main.app)
    monkeypatch.setattr(service, "GROQ_API_KEY", "")
    assert client.post("/sketch", json={"image": _PNG}).status_code == 503
    bad = client.post("/sketch", json={"image": "data:image/gif;base64,R0lGODlhAQABAAAAACw="})
    assert bad.status_code == 422 and "PNG" in bad.json()["detail"]

    calls = []

    def fake_read(image, note):
        calls.append(note)
        return sketch_mod.SketchReading(
            purpose="p", components=[sketch_mod.SketchComponent(id="C1", name="pot", description="")],
            relationships=[], uncertain=[],
        )

    monkeypatch.setattr(service, "GROQ_API_KEY", "key")
    monkeypatch.setattr(service, "read_sketch", fake_read)
    first = client.post("/sketch", json={"image": _PNG, "note": "a cooler"})
    second = client.post("/sketch", json={"image": _PNG, "note": "a cooler"})
    assert first.status_code == second.status_code == 200
    assert first.json()["components"][0]["name"] == "pot"
    assert calls == ["a cooler"]  # the repeat came from the cache
    client.post("/sketch", json={"image": _PNG, "note": "something else"})
    assert len(calls) == 2  # a different note is a different reading
    # Sketch readings never show up as reports.
    assert client.get("/examples").json() == []


# --- Constrained redesign --------------------------------------------------

from app.pipeline import redesign as redesign_mod


def _redesign_parent():
    parent, _ = _recheck_pair()
    return parent


def _features():
    return redesign_mod.features_from_texts(["Hollow segments", "Interlocking joints", "hollow  segments", "Blade"])


def test_features_are_deduped_and_numbered():
    assert [(f.id, f.text) for f in _features()] == [
        ("E1", "Hollow segments"), ("E2", "Interlocking joints"), ("E3", "Blade"),
    ]


def test_brief_keeps_only_real_features_and_writes_out_the_cost():
    brief = redesign_mod.RedesignBrief(
        locked_features=["e3", "E9", "E1"],
        constraints=["No electricity", " no  electricity ", "Hand-operated", ""],
        cost_target_inr=2000,
    )
    locked, constraints = redesign_mod.normalize_brief(brief, _features())
    assert locked == ["E1", "E3"]  # feature order; unknown id dropped
    assert constraints == ["No electricity", "Hand-operated", "Target cost under ₹2,000 per unit"]
    # The cache name doesn't depend on the order things were picked in.
    assert redesign_mod.brief_key(locked, constraints) == redesign_mod.brief_key(
        ["E3", "E1"], list(reversed(constraints))
    )


def test_redesign_trusts_only_verified_evidence_and_flags_dropped_locks(monkeypatch):
    parent = _redesign_parent()
    monkeypatch.setattr(
        redesign_mod,
        "complete_json",
        lambda *a, **k: {
            "alternatives": [
                {
                    "title": "Foam-core paddle",
                    "how_it_works": "Unlike D1, the shaft is solid foam.",
                    "what_changes": "Solid foam replaces hollow segments.",
                    "keeps": ["E2", "E7"],
                    "constraint_notes": [
                        {"constraint": "no electricity", "approach": "Nothing powered."},
                        {"constraint": "Cheap to build (reworded)", "approach": "Uses offcuts."},
                    ],
                    "avoids": [
                        {"document": "[D1]", "mechanism": "hollow buoyant segments",
                         "quote": "four hollow segments that interlock and float on water"},
                        {"document": "D2", "mechanism": "made up", "quote": "a titanium blade with sensors"},
                        {"document": "D5", "mechanism": "unknown doc", "quote": "anything at all here"},
                    ],
                    "revised_idea": "A collapsible kayak paddle whose segments are solid closed-cell foam.",
                    "change_summary": "Replace the hollow segments with solid foam segments.",
                },
                {"title": "No idea", "how_it_works": "x", "revised_idea": "too short", "change_summary": "x"},
            ]
        },
    )
    brief = redesign_mod.RedesignBrief(
        locked_features=["E1", "E2"], constraints=["No electricity", "Cheap to build"]
    )
    result = redesign_mod.propose_redesigns(parent, _features(), brief)

    assert [m.id for m in result.matches_considered] == ["a", "b"]  # the original closest
    (alt,) = result.alternatives  # the one without a usable revised idea is dropped
    assert alt.keeps == ["E2"] and alt.drops_locked == ["E1"]
    assert [(v.document_id, v.mechanism) for v in alt.avoids] == [("a", "hollow buoyant segments")]
    assert result.unverified_quotes_dropped == 1  # the invented quote; the unknown doc isn't evidence
    assert [(n.constraint, n.approach) for n in alt.constraint_notes] == [
        ("No electricity", "Nothing powered."), ("Cheap to build", "Uses offcuts."),
    ]
    assert "D1" not in alt.how_it_works and "the existing design" in alt.how_it_works


def test_redesign_with_no_usable_alternatives_raises(monkeypatch):
    monkeypatch.setattr(redesign_mod, "complete_json", lambda *a, **k: {"alternatives": []})
    with pytest.raises(ValueError):
        redesign_mod.propose_redesigns(_redesign_parent(), _features(), redesign_mod.RedesignBrief())


def test_redesign_endpoints_reuse_examination_elements_and_cache_per_brief(temp_cache, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main, service

    temp_cache.set_cached("Folding paddle idea", [_result_event("Folding paddle idea")])
    key = temp_cache.cache_key("Folding paddle idea")
    client = TestClient(main.app)

    monkeypatch.setattr(service, "GROQ_API_KEY", "")
    assert client.post(f"/report/{key}/features").status_code == 503
    assert client.post("/report/ffffffffffffffff/features").status_code == 404
    too_many = {"constraints": ["c"] * (redesign_mod.MAX_CONSTRAINTS + 1)}
    assert client.post(f"/report/{key}/redesign", json=too_many).status_code == 422

    # With the examination preview already computed, its elements are the
    # features — no LLM call needed, even without a key.
    temp_cache.set_attachment(key, "examination", exam.ExaminationPreview(
        outcome="no_objection_found", elements=_elements(3), documents=[], coverage=[],
        novelty_objections=[], inventive_step_objections=[], uncovered_elements=[],
        section3_flags=[], evidence_basis="snippets", unverified_quotes_dropped=0,
    ).model_dump(mode="json"))
    features = client.post(f"/report/{key}/features")
    assert features.status_code == 200
    assert [f["text"] for f in features.json()["features"]] == ["element 1", "element 2", "element 3"]

    calls = []

    def fake_propose(report, features, brief):
        calls.append(brief)
        locked, constraints = redesign_mod.normalize_brief(brief, features)
        return redesign_mod.RedesignResult(
            features=features, locked_features=locked, constraints=constraints, alternatives=[],
            matches_considered=[], evidence_basis="snippets", unverified_quotes_dropped=0,
        )

    monkeypatch.setattr(service, "GROQ_API_KEY", "key")
    monkeypatch.setattr(service, "propose_redesigns", fake_propose)
    body = {"locked_features": ["E1"], "constraints": ["No electricity"], "cost_target_inr": 2000}
    first = client.post(f"/report/{key}/redesign", json=body)
    second = client.post(f"/report/{key}/redesign", json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["constraints"][-1] == "Target cost under ₹2,000 per unit"
    assert len(calls) == 1  # the same brief is served from the cache
    client.post(f"/report/{key}/redesign", json={**body, "cost_target_inr": 1500})
    assert len(calls) == 2

    # Redesigns are attachments: never listed as reports, gone with the report.
    assert [e["report_id"] for e in client.get("/examples").json()] == [key]
    temp_cache.evict(key)
    assert list(temp_cache.CACHE_DIR.glob(f"{key}.*.json")) == []


# --- Feature evidence ---------------------------------------------------------

from app.pipeline import citation_followup as followup_mod
from app.pipeline.citation_chase import CitationDiscovery, CitationNetwork
from app.pipeline.evidence import FeatureFinding, attach_evidence, headline, quote_is_verified
from app.pipeline.india_status import IndiaStatus
from app.pipeline.novelty import IdeaFeature, _RawCandidateAssessment, build_feature_findings

DOC_TEXT = (
    "A drying chamber heated by a solar collector, with a chimney that draws air "
    "upward through stacked mesh trays holding the grain."
)


def _detail(id="patent/US1A/en", text=DOC_TEXT, source="claims"):
    return CandidateDetail(
        id=id,
        source_type="patent",
        title=f"Doc {id}",
        link=f"https://patents.google.com/{id}",
        summary_text=text,
        evidence_source=source,
    )


def _raw_assessment(id, verdict="partially_overlapping", quotes=()):
    return _RawCandidateAssessment.model_validate(
        {
            "result_id": id,
            "overlapping_elements": [],
            "differences": [],
            "verdict": verdict,
            "feature_evidence": [{"feature": f, "quote": q} for f, q in quotes],
        }
    )


FEATURES = [
    IdeaFeature(id="F1", text="solar-heated drying chamber"),
    IdeaFeature(id="F2", text="chimney-driven airflow"),
    IdeaFeature(id="F3", text="clay body that stores heat"),
]


def test_quote_verification_tolerates_case_and_typography_only():
    assert quote_is_verified("A DRYING chamber heated by a solar collector…", DOC_TEXT)
    assert not quote_is_verified("a drying chamber warmed by a solar collector", DOC_TEXT)
    assert not quote_is_verified("solar collector", DOC_TEXT)  # too short to be evidence


def test_feature_findings_keep_only_verified_quotes():
    raw = [
        _raw_assessment(
            "patent/US1A/en",
            quotes=[
                ("F1", "A drying chamber heated by a solar collector"),
                ("F2", "a chimney that pulls air through the trays"),  # paraphrase
            ],
        )
    ]
    findings = build_feature_findings(FEATURES, raw, [_detail()])
    by_id = {f.id: f for f in findings}
    assert [e.result_id for e in by_id["F1"].evidence] == ["patent/US1A/en"]
    assert by_id["F1"].evidence[0].evidence_source == "claims"
    assert by_id["F2"].evidence == []
    assert by_id["F3"].evidence == []


def test_feature_findings_ignore_not_relevant_candidates_and_unknown_features():
    raw = [
        _raw_assessment(
            "patent/US1A/en",
            verdict="not_relevant",
            quotes=[("F1", "A drying chamber heated by a solar collector")],
        ),
    ]
    findings = build_feature_findings(FEATURES, raw, [_detail()])
    assert all(not f.evidence for f in findings)
    raw = [_raw_assessment("patent/US1A/en", quotes=[("F9", "A drying chamber heated by a solar collector")])]
    assert all(not f.evidence for f in build_feature_findings(FEATURES, raw, [_detail()]))


def test_feature_findings_need_at_least_two_features():
    assert build_feature_findings(FEATURES[:1], [], [_detail()]) == []


def test_attach_evidence_one_quote_per_document_per_feature():
    findings = [FeatureFinding(id="F1", feature="x")]
    kwargs = dict(
        result_id="d", title="t", link="l", document_text=DOC_TEXT, evidence_source="abstract"
    )
    assert attach_evidence(findings, "f1", "A drying chamber heated by a solar collector", **kwargs)
    assert not attach_evidence(findings, "F1", "a chimney that draws air upward", **kwargs)
    assert len(findings[0].evidence) == 1


def test_headline_says_not_found_in_evidence_reviewed_never_novel():
    findings = [
        FeatureFinding(id="F1", feature="solar chamber"),
        FeatureFinding(id="F2", feature="clay body"),
    ]
    attach_evidence(
        findings, "F1", "A drying chamber heated by a solar collector",
        result_id="d", title="t", link="l", document_text=DOC_TEXT, evidence_source="claims",
    )
    text = headline(findings, 8)
    assert text == (
        "Overlap found in 1 of 2 features: solar chamber. "
        "Not found in the 8 documents reviewed: clay body."
    )
    assert headline([], 8) is None


def _discovery(id):
    return CitationDiscovery(
        id=id,
        title=f"Doc {id}",
        link=f"https://patents.google.com/{id}",
        referenced_by=["patent/US1A/en", "patent/US2A/en"],
        direction="backward",
        examiner_cited=True,
        reason="shared_reference",
        likely_expired=False,
    )


def test_followup_records_which_discovery_changed_the_conclusion():
    findings = [
        FeatureFinding(id="F1", feature="solar-heated drying chamber"),
        FeatureFinding(id="F2", feature="chimney-driven airflow"),
    ]
    # F1 was already shown by a searched document.
    attach_evidence(
        findings, "F1", "A drying chamber heated by a solar collector",
        result_id="patent/US1A/en", title="t", link="l", document_text=DOC_TEXT,
        evidence_source="claims",
    )
    discoveries = [_discovery("patent/US9A/en"), _discovery("patent/US8A/en")]
    details = [_detail("patent/US9A/en"), _detail("patent/US8A/en")]
    raw = followup_mod._RawFollowUps.model_validate(
        {
            "documents": [
                {
                    "key": "C1",
                    "verdict": "partially_overlapping",
                    "feature_evidence": [
                        {"feature": "F1", "quote": "A drying chamber heated by a solar collector"},
                        {"feature": "F2", "quote": "a chimney that draws air upward"},
                    ],
                    "explanation": "Shows the chimney.",
                },
                # Same feature again: must not also claim the change.
                {
                    "key": "C2",
                    "verdict": "blocking",
                    "feature_evidence": [{"feature": "F2", "quote": "a chimney that draws air upward"}],
                },
            ]
        }
    )
    followups, assessments = followup_mod.apply_followups(findings, discoveries, details, raw)

    assert followups[0].features_found == ["F1", "F2"]
    assert followups[0].newly_found == ["F2"]
    assert followups[0].changed_conclusion
    assert followups[1].newly_found == [] and not followups[1].changed_conclusion
    assert [e.found_via for e in findings[1].evidence] == ["citation", "citation"]
    assert all(a.found_via == "citation" for a in assessments)
    assert followups[0].model_dump()["changed_conclusion"] is True


def test_followup_without_verified_evidence_is_not_a_match():
    findings = [FeatureFinding(id="F1", feature="x"), FeatureFinding(id="F2", feature="y")]
    raw = followup_mod._RawFollowUps.model_validate(
        {"documents": [{"key": "C1", "verdict": "blocking", "feature_evidence": [
            {"feature": "F1", "quote": "words that are not in the document at all"}
        ]}]}
    )
    followups, assessments = followup_mod.apply_followups(
        findings, [_discovery("patent/US9A/en")], [_detail("patent/US9A/en")], raw
    )
    assert followups[0].verdict == "not_relevant"
    assert assessments == []


def test_followup_is_skipped_without_findings_or_discoveries(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no lookups expected")

    monkeypatch.setattr(followup_mod, "fetch_detail", boom)
    network = CitationNetwork(discoveries=[_discovery("patent/US9A/en")])
    assert followup_mod.follow_up_citations("idea", network, [], 2).lookups == 0
    findings = [FeatureFinding(id="F1", feature="x")]
    assert followup_mod.follow_up_citations("idea", CitationNetwork(), findings, 2).lookups == 0
    assert followup_mod.follow_up_citations("idea", network, findings, 0).lookups == 0


def test_followup_llm_failure_leaves_report_unchanged(monkeypatch):
    monkeypatch.setattr(followup_mod, "fetch_detail", lambda *a, **k: _detail("patent/US9A/en"))

    def broken(*a, **k):
        raise ValueError("bad json")

    monkeypatch.setattr(followup_mod, "complete_json", broken)
    findings = [FeatureFinding(id="F1", feature="x"), FeatureFinding(id="F2", feature="y")]
    network = CitationNetwork(discoveries=[_discovery("patent/US9A/en")])
    outcome = followup_mod.follow_up_citations("idea", network, findings, 2)
    assert outcome.lookups == 1  # the details call was still made and counted
    assert outcome.followups == [] and all(not f.evidence for f in findings)


def test_india_status_reads_reports_saved_before_rename():
    old = IndiaStatus.model_validate({"blocking_in_india": 2, "active_elsewhere_only": 1})
    assert old.related_active_in_india == 2
    assert "blocking_in_india" not in old.model_dump()


def test_pipeline_counts_followup_lookups_and_records_evidence(monkeypatch):
    _fake_pipeline(monkeypatch, refinement=False)
    findings = [FeatureFinding(id="F1", feature="x"), FeatureFinding(id="F2", feature="y")]
    monkeypatch.setattr(
        orch,
        "assess_novelty",
        lambda *a: NoveltyAssessment(
            candidate_assessments=[],
            overall_novelty_confidence=0.6,
            differentiation_suggestions=[],
            citations=[],
            claim_chart_pairs=[],
            feature_findings=findings,
        ),
    )
    monkeypatch.setattr(
        orch,
        "chase_citations",
        lambda c, r: CitationNetwork(discoveries=[_discovery("patent/US9A/en")]),
    )
    follow = followup_mod.CitationFollowUp(
        id="patent/US9A/en", title="Doc", link="l", referenced_by=[], reason="shared_reference",
        evidence_source="claims", verdict="partially_overlapping", features_found=["F2"],
        newly_found=["F2"], explanation="e",
    )
    monkeypatch.setattr(
        orch,
        "follow_up_citations",
        lambda *a: followup_mod.FollowUpOutcome(
            followups=[follow], details=[_detail("patent/US9A/en")], lookups=1
        ),
    )
    events = _run(orch.run_pipeline("A folding kayak paddle idea"))
    result = events[-1].data
    assert result.search_strategy.serpapi_calls["google_patents_details"] == 1
    assert result.citation_followups[0].changed_conclusion
    assert result.examined_documents[-1].found_via == "citation"
    assert any("changed the conclusion" in e.message for e in events if e.type == "progress")


# --- Model-written document ids ----------------------------------------------


def test_mangled_document_ids_resolve_to_the_ids_the_model_was_given():
    from app.pipeline.evidence import resolve_document_id

    known = ["patent/CN205448635U/en", "patent/US4099338A/en", "scholar/123"]
    assert resolve_document_id("patent/CN205448635U/en", known) == "patent/CN205448635U/en"
    # Observed from the model: the slash before the language code became a space.
    assert resolve_document_id("patent/CN205448635U en", known) == "patent/CN205448635U/en"
    assert resolve_document_id("US4099338A", known) == "patent/US4099338A/en"
    assert resolve_document_id("patent/EP1/en", known) is None
    assert resolve_document_id("", known) is None
    # A fragment matching more than one id is ambiguous, never guessed.
    assert resolve_document_id("patent", known) is None


def test_novelty_keeps_evidence_when_the_model_mangles_an_id(monkeypatch):
    from app.pipeline import novelty as novelty_mod
    from app.pipeline.deepdive import CandidateDetail

    text = "A solar air heat collector feeds hot air through a duct into the drying shed."
    candidate = CandidateDetail(id="patent/CN1/en", source_type="patent", title="Dryer",
                                link="", summary_text=text, evidence_source="abstract")
    monkeypatch.setattr(novelty_mod, "complete_json", lambda *a, **k: {
        "idea_features": [{"id": "F1", "text": "solar air heater"}, {"id": "F2", "text": "tray"}],
        "candidate_assessments": [{
            "result_id": "patent/CN1 en", "overlapping_elements": [], "differences": [],
            "verdict": "partially_overlapping",
            "feature_evidence": [{"feature": "F1", "quote": "solar air heat collector feeds hot air through a duct"}],
        }],
        "overall_novelty_confidence": 0.4, "differentiation_suggestions": [],
        "citations": [{"claim": "c", "result_id": "CN1"}], "claim_chart_pairs": [], "plain_summary": "s",
    })
    out = novelty_mod.assess_novelty("idea", [candidate])
    assert [a.result_id for a in out.candidate_assessments] == ["patent/CN1/en"]
    assert [c.result_id for c in out.citations] == ["patent/CN1/en"]
    assert out.feature_findings[0].evidence[0].result_id == "patent/CN1/en"


def test_elided_quote_resolves_to_the_continuous_source_passage():
    from app.pipeline.evidence import locate_quote

    text = ("The utility model relates to a Solar drying system. The first draught fan (5) "
            "sends the hot-air of the tuber pipe   into the drying shed (3).")
    assert locate_quote("first draught fan (5) ... into the drying shed", text) == (
        "first draught fan (5) sends the hot-air of the tuber pipe   into the drying shed"
    )
    # Plain quotes come back with the document's own casing and typography.
    assert locate_quote("relates to a solar drying system", text) == "relates to a Solar drying system"
    assert locate_quote("into the drying shed ... first draught fan", text) is None  # out of order
    assert locate_quote("fan ... drying shed", text) is None  # single-word fragment
    assert locate_quote("first draught fan (5) ... a missing clause here", text) is None
    assert locate_quote("blower fan", text) is None


def test_stored_evidence_is_the_source_passage_not_the_models_quote():
    from app.pipeline.evidence import EvidenceSection, IdeaFeature, attach_evidence, empty_findings

    claim = "1. A dryer wherein a first draught fan (5) sends hot air into the drying shed (3)."
    findings = empty_findings([IdeaFeature(id="F1", text="fan moves hot air")])
    added = attach_evidence(
        findings, "F1", "first draught fan (5) … into the drying shed", result_id="d", title="t",
        link="", document_text=claim, evidence_source="claims",
        sections=[EvidenceSection(label="Claim 1", source="claims", text=claim, original_chars=len(claim))],
    )
    assert added
    assert findings[0].evidence[0].quote == "first draught fan (5) sends hot air into the drying shed"
    assert findings[0].evidence[0].section.label == "Claim 1"


def test_benchmark_counts_citation_discoveries_only_where_measured():
    from types import SimpleNamespace

    from benchmark.run import find_discovery_rank

    discoveries = [SimpleNamespace(id="patent/US1/en"), SimpleNamespace(id="patent/US5325765B1/en")]
    assert find_discovery_rank(discoveries, _case()) == 2  # any kind code
    assert find_discovery_rank(discoveries[:1], _case()) is None

    base = dict(patent="p", rank_before=None, match_before=None, results_before=1,
                results_after=1, searches_used=9)
    results = [
        CaseResult(id="a", rank_after=None, rank_citations=3, citation_depth=5, **base),
        CaseResult(id="b", rank_after=4, match_after="exact", citation_depth=5, **base),
        CaseResult(id="c", rank_after=None, citation_depth=5, **base),
        CaseResult(id="d", rank_after=None, **base),  # citation chasing not measured
    ]
    s = summarize(results)
    assert s["citation_cases"] == 3
    assert s["top10_or_citations"] == 2 / 3
