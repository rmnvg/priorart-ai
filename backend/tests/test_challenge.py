"""Challenge safety, retrieval budgets, cache replay, and API contracts (offline)."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import cache, main, service
from app.models import AnalysisResult
from app.pipeline import challenge as mod
from app.pipeline.evidence import FeatureFinding
from app.pipeline.rank import RankedResult
from app.pipeline.search import QueryBundle


@pytest.fixture
def report():
    return AnalysisResult(
        idea_text="A passive dryer with a humidity controlled vent", ranked_results=[],
        candidate_assessments=[], overall_novelty_confidence=0.5,
        differentiation_suggestions=[], citations=[],
        india_status={"related_active_in_india": 0, "active_elsewhere_only": 0},
        feature_findings=[FeatureFinding(id="F1", feature="Humidity controlled vent")],
    )


@pytest.fixture
def setup(monkeypatch):
    calls = []
    plan = {"queries": [
        {"query": "humidity vent", "rationale": "Mechanism"},
        {"query": "moisture responsive aperture", "rationale": "Alternative vocabulary"},
    ]}
    assessment = {"documents": ["p0", "p1", "p2"], "evidence": [
        {"document_id": "p0", "section": "Abstract", "quote": "A humidity sensor controls the vent opening."},
    ]}
    monkeypatch.setattr(mod, "complete_json", Mock(side_effect=[plan, assessment]))
    monkeypatch.setattr(mod, "run_queries", lambda qs: [
        QueryBundle(query_type=q.type, query=q.query, results=[]) for q in qs
    ])
    monkeypatch.setattr(mod, "rank_and_dedupe", lambda *args: [
        RankedResult(id=f"p{i}", source_type="patent", title=f"Patent {i}",
                     link="https://patents.google.com/", snippet="", relevance_score=0.8)
        for i in range(6)
    ])
    def details(**kwargs):
        calls.append(kwargs)
        return {"abstract": "A humidity sensor controls the vent opening.",
                "claims": ["An unrelated claim describing a drying chamber."]}
    monkeypatch.setattr(mod.client, "search", details)
    return assessment, calls


def test_challenge_budget_verified_section_and_original_unchanged(report, setup):
    before = report.model_dump()
    result = mod.challenge_finding(report, "F1")
    assert result.outcome == "found"
    assert len(setup[1]) == 3
    assert result.serpapi_calls == {"google_patents": 2, "google_patents_details": 3}
    assert result.evidence[0].section == "Abstract"
    assert report.model_dump() == before


@pytest.mark.parametrize("change", [
    {"section": "Claim 1"},  # real quotation, wrong section
    {"quote": "The invention uses a completely invented mechanism."},
    {"document_id": "invented"},
])
def test_bad_evidence_never_changes_finding(report, setup, change):
    setup[0]["evidence"][0].update(change)
    result = mod.challenge_finding(report, "F1")
    assert result.outcome == "inconclusive"
    assert not result.evidence
    assert result.warnings


def test_successful_review_without_evidence_is_bounded_not_found(report, setup):
    setup[0]["evidence"] = []
    result = mod.challenge_finding(report, "F1")
    assert result.outcome == "not_found"
    assert len(result.documents) == 3


def test_missing_document_assessment_is_error(report, setup):
    setup[0]["documents"] = ["p0"]
    with pytest.raises(ValueError, match="every document"):
        mod.challenge_finding(report, "F1")


def test_search_failure_is_not_absence(report, setup, monkeypatch):
    monkeypatch.setattr(mod, "run_queries", lambda qs: [
        QueryBundle(query_type=q.type, query=q.query, results=[], search_failed=True) for q in qs
    ])
    with pytest.raises(mod.ChallengeUnavailable):
        mod.challenge_finding(report, "F1")
    assert not setup[1]


def test_failed_details_are_inconclusive(report, setup, monkeypatch):
    monkeypatch.setattr(mod.client, "search", Mock(side_effect=RuntimeError("offline")))
    result = mod.challenge_finding(report, "F1")
    assert result.outcome == "inconclusive"
    assert not result.documents


def test_no_search_matches_does_not_claim_documents_reviewed(report, setup, monkeypatch):
    monkeypatch.setattr(mod, "rank_and_dedupe", lambda *args: [])
    result = mod.challenge_finding(report, "F1")
    assert result.outcome == "not_found"
    assert result.documents == []
    assert result.serpapi_calls["google_patents_details"] == 0


def test_sections_keep_abstract_separate_and_label_excerpts():
    sections = mod.document_sections({"abstract": "a" * 4100, "claims": ["b" * 1600] * 20})
    assert len(sections) == 13
    assert sections[0].source == "abstract"
    assert sections[0].label == "Abstract (excerpt)"
    assert sections[1].label == "Claim 1 (excerpt)"
    assert len(sections[1].text) == 1500


def test_cache_coalesces_requests_and_replays_without_keys(report, setup, monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(service, "LIVE_MODE", True)
    result = mod.challenge_finding(report, "F1")
    runner = Mock(return_value=result)
    monkeypatch.setattr(service, "challenge_finding", runner)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.challenge_for("a" * 16, report, "F1"), range(2)))
    assert results[0] == results[1]
    assert runner.call_count == 1
    monkeypatch.setattr(service, "LIVE_MODE", False)
    assert service.challenge_for("a" * 16, report, "F1") == result
    assert runner.call_count == 1


def test_inconclusive_is_retryable(report, setup, monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(service, "LIVE_MODE", True)
    result = mod.challenge_finding(report, "F1").model_copy(update={"outcome": "inconclusive"})
    monkeypatch.setattr(service, "challenge_finding", lambda *args: result)
    service.challenge_for("a" * 16, report, "F1")
    assert service.saved_challenge("a" * 16, report, "F1") is None


def test_api_read_only_invalid_feature_demo_and_missing_report(report, monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(service, "load_report", lambda key: report if key == "a" * 16 else None)
    monkeypatch.setattr(service, "LIVE_MODE", False)
    runner = Mock()
    monkeypatch.setattr(service, "challenge_finding", runner)
    client = TestClient(main.app)
    path = f"/report/{'a' * 16}/challenge/F1"
    assert client.get(path).json() is None
    assert client.post(path).status_code == 503
    assert client.post(path.replace("F1", "unknown")).status_code == 422
    assert client.post("/report/missing/challenge/F1").status_code == 404
    assert not runner.called


def test_existing_evidence_cannot_be_challenged(report, setup):
    from app.pipeline.evidence import FeatureEvidence
    report.feature_findings[0].evidence = [FeatureEvidence(
        result_id="p0", title="Existing evidence", link="https://example.com",
        quote="A humidity sensor controls the vent opening.", evidence_source="abstract",
    )]
    with pytest.raises(ValueError, match="not found"):
        mod.challenge_finding(report, "F1")
    assert not setup[1]


def test_partial_search_failure_cannot_become_negative_finding(report, setup, monkeypatch):
    setup[0]["evidence"] = []
    monkeypatch.setattr(mod, "run_queries", lambda qs: [
        QueryBundle(query_type=q.type, query=q.query, results=[], search_failed=(i == 0))
        for i, q in enumerate(qs)
    ])
    result = mod.challenge_finding(report, "F1")
    assert result.outcome == "inconclusive"
    assert "coverage is incomplete" in result.warnings[0]


def test_duplicate_query_plan_does_not_spend_searches(report, monkeypatch):
    monkeypatch.setattr(mod, "complete_json", lambda *args, **kwargs: {"queries": [
        {"query": "humidity vent", "rationale": "one"},
        {"query": "  HUMIDITY  vent  ", "rationale": "two"},
    ]})
    search = Mock()
    monkeypatch.setattr(mod, "run_queries", search)
    with pytest.raises(ValueError, match="distinct"):
        mod.challenge_finding(report, "F1")
    assert not search.called


def test_api_returns_new_then_saved_result_in_demo_mode(report, setup, monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(service, "load_report", lambda key: report)
    monkeypatch.setattr(service, "LIVE_MODE", True)
    client = TestClient(main.app)
    path = f"/report/{'b' * 16}/challenge/F1"
    response = client.post(path)
    assert response.status_code == 200
    assert response.json()["outcome"] == "found"
    monkeypatch.setattr(service, "LIVE_MODE", False)
    assert client.get(path).json() == response.json()
    assert client.post(path).json() == response.json()
    assert len(setup[1]) == 3
