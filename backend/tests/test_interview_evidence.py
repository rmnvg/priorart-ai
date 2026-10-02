"""Regression tests for clarification boundaries and source attribution."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.pipeline import deepdive, interview, citation_followup
from app.pipeline.evidence import FeatureFinding, IdeaFeature, attach_evidence
from app.pipeline.novelty import _RawCandidateAssessment, build_feature_findings
from app.pipeline.citation_chase import CitationDiscovery


def test_interview_allows_no_questions_and_preserves_language(monkeypatch):
    response = {"questions": [{"question": "हवा कैसे चलती है?", "reason": "इससे सही तकनीक खोजने में मदद मिलेगी।"}]}
    llm = Mock(return_value=response)
    monkeypatch.setattr(interview, "complete_json", llm)
    assert interview.plan_interview("बिना बिजली का अनाज सुखाने वाला यंत्र").model_dump() == response
    assert "बिना बिजली" in llm.call_args.args[0]
    llm.return_value = {"questions": []}
    assert interview.plan_interview("A detailed invention").questions == []


def test_sufficient_description_gate_requires_actual_source_passages(monkeypatch):
    idea = "Solar heat dries grain. A chimney connects to trays. A detachable clay sleeve stores heat."
    raw = {"known": {"mechanism": "Solar heat dries grain", "relationships": "A chimney connects to trays",
                     "distinction": "A detachable clay sleeve stores heat"},
           "questions": [{"question": "How thick is the sleeve?", "reason": "Optional engineering detail"}]}
    monkeypatch.setattr(interview, "complete_json", lambda *args, **kwargs: raw)
    assert interview.plan_interview(idea).questions == []
    raw["known"]["mechanism"] = "A motor drives heated air through grain"
    assert len(interview.plan_interview(idea).questions) == 1


@pytest.mark.parametrize("questions", [
    [{"question": "How does air move?", "reason": "Find the mechanism."}] * 4,
    [{"question": "How does air move?", "reason": "Find the mechanism."}] * 2,
    [{"question": "     ", "reason": "Find the mechanism."}],
])
def test_interview_rejects_invalid_model_questions(questions):
    with pytest.raises(ValueError):
        interview.InterviewPlan.model_validate({"questions": questions})


def test_interview_api_no_search_and_recoverable_failures(monkeypatch):
    monkeypatch.setattr(main, "GROQ_API_KEY", "test")
    planner = Mock(return_value=interview.InterviewPlan(questions=[]))
    monkeypatch.setattr(main, "plan_interview", planner)
    # A clarification must never start the billable retrieval pipeline.
    monkeypatch.setattr(main.service, "analyze", Mock(side_effect=AssertionError("Unexpected search")))
    client = TestClient(main.app)
    assert client.post("/interview", json={"idea_text": "A passive crop dryer"}).json() == {"questions": []}
    planner.assert_called_once_with("A passive crop dryer")
    for idea in ("tiny", " " * 12, "a" * 6001):
        assert client.post("/interview", json={"idea_text": idea}).status_code == 422
    planner.side_effect = ValueError("private provider detail")
    failed = client.post("/interview", json={"idea_text": "A passive crop dryer"})
    assert failed.status_code == 502
    assert "private provider" not in failed.text
    monkeypatch.setattr(main, "GROQ_API_KEY", "")
    assert client.post("/interview", json={"idea_text": "A passive crop dryer"}).status_code == 503


@pytest.fixture
def detail(monkeypatch):
    monkeypatch.setattr(deepdive._client, "search", lambda **kwargs: {
        "abstract": "A humidity sensor controls the vent opening.",
        "claims": ["A drying chamber contains several removable trays."] * 8,
    })
    return deepdive.fetch_detail("p1", "patent", "Dryer", "https://example.com/p1")


def test_abstract_quote_is_not_mislabeled_as_claim(detail):
    assessment = _RawCandidateAssessment(
        result_id="p1", overlapping_elements=[], differences=[], verdict="partially_overlapping",
        feature_evidence=[{"feature": "F1", "quote": "A humidity sensor controls the vent opening."}],
    )
    findings = build_feature_findings(
        [IdeaFeature(id="F1", text="Sensor controlled vent"), IdeaFeature(id="F2", text="Trays")],
        [assessment], [detail],
    )
    evidence = findings[0].evidence[0]
    assert evidence.evidence_source == "abstract"
    assert evidence.section.label == "Abstract"
    assert detail.total_claims == 8
    assert len([s for s in detail.sections if s.source == "claims"]) == 6


def test_claims_are_retained_even_when_abstract_is_long():
    sections = deepdive.patent_sections({
        "abstract": "a" * 10000,
        "claims": ["Claim one has a first mechanism.", "Claim two has a second mechanism."],
    })
    assert sections[0].truncated
    assert sections[0].original_chars == 10000
    assert len(sections[0].text) == deepdive.MAX_ABSTRACT_CHARS
    assert sections[2].text == "Claim two has a second mechanism."


def test_quote_must_match_one_reviewed_section(detail):
    findings = [FeatureFinding(id="F1", feature="Vent")]
    kwargs = dict(result_id=detail.id, title=detail.title, link=detail.link,
                  document_text="Invented text that occurs outside the reviewed sections.",
                  evidence_source="claims", sections=detail.sections)
    assert not attach_evidence(findings, "F1", "Invented text that occurs outside", **kwargs)
    assert attach_evidence(findings, "F1", "A drying chamber contains several removable trays.", **kwargs)
    assert findings[0].evidence[0].section.label == "Claim 1"


def test_citation_followup_uses_section_attribution(detail):
    discovery = CitationDiscovery(id=detail.id, title=detail.title, link=detail.link,
                                  referenced_by=["p0"], reason="shared_reference",
                                  direction="backward", examiner_cited=False, likely_expired=False)
    raw = citation_followup._RawFollowUps.model_validate({"documents": [{
        "key": "C1", "verdict": "partially_overlapping", "explanation": "Vent found",
        "feature_evidence": [{"feature": "F1", "quote": "A humidity sensor controls the vent opening."}],
    }]})
    findings = [FeatureFinding(id="F1", feature="Vent")]
    citation_followup.apply_followups(findings, [discovery], [detail], raw)
    assert findings[0].evidence[0].section.label == "Abstract"
    assert findings[0].evidence[0].found_via == "citation"


def test_unavailable_details_remain_snippet_evidence(monkeypatch):
    monkeypatch.setattr(deepdive._client, "search", Mock(side_effect=RuntimeError("offline")))
    detail = deepdive.fetch_detail("p1", "patent", "Dryer", "link", "A search snippet with limited context.")
    assert detail.sections[0].source == "snippet"
    assert detail.total_claims == 0
