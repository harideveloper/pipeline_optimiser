import pytest
from unittest.mock import patch, MagicMock
from app.components.risk.risk_assessor import RiskAssessor, RiskAssessorError


# Fixtures
@pytest.fixture
def assessor():
    with patch("app.components.risk.risk_assessor.LLMClient") as mock_llm:
        mock_llm.return_value.chat_completion.return_value = '{"overall_risk":"medium","risk_score":5,"risks":[],"recommendations":[],"analysis":"ok"}'
        mock_llm.return_value.parse_json_response.side_effect = lambda resp, cid: eval(resp)
        yield RiskAssessor(model="test-model", temperature=0.1, max_tokens=50)


# Tests
def test_calculate_heuristic_risk(assessor):
    """Heuristic risk score increases with severity and risky keywords."""
    issues = [{"severity": "high"}, {"severity": "low"}]
    fixes = [{"fix": "security update"}, {"fix": "minor tweak"}]
    score = assessor._calculate_heuristic_risk(issues, fixes)
    assert 0 < score <= 10

def test_run_returns_assessment(assessor):
    """run() returns a structured assessment dict."""
    state = {"correlation_id": "cid"}
    issues = [{"severity": "medium", "type": "syntax", "description": "Missing step in pipeline"}]
    fixes = [{"fix": "update pipeline"}]
    result = assessor.run(state, issues, fixes, "orig", "optimised")
    assert result["overall_risk"] in ["low", "medium", "high"]
    assert "risk_score" in result
    assert "recommendations" in result
    assert "analysis" in result

def test_execute_handles_no_optimisation(assessor):
    """_execute sets low risk when no optimisation result is present."""
    state = {"run_id": "r1", "correlation_id": "cid"}
    updated = assessor._execute(state)
    ra = updated["risk_assessment"]
    assert ra["overall_risk"] == "low"
    assert ra["risk_score"] == 0
    assert ra["recommendations"][0] == "No changes to assess"

def test_validate_and_enhance_enforces_bounds(assessor):
    """_validate_and_enhance_assessment corrects invalid risk levels and scores."""
    assessment = {"overall_risk": "unknown", "risk_score": 999, "risks": None, "recommendations": None}
    result = assessor._validate_and_enhance_assessment(assessment, heuristic_score=2.5, applied_fixes=[{"fix":"test"}])
    assert result["overall_risk"] in ["low", "medium", "high"]
    assert 0 <= result["risk_score"] <= 10
    assert isinstance(result["risks"], list)
    assert isinstance(result["recommendations"], list)

def test_run_returns_zero_risk_for_no_fixes(assessor):
    """run() returns low risk with proper message if no fixes applied."""
    state = {"correlation_id": "cid"}
    result = assessor.run(state, issues_detected=[], applied_fixes=[], original_yaml="", optimised_yaml="")
    assert result["overall_risk"] == "low"
    assert result["risk_score"] == 0
    assert "No changes were applied" in result["recommendations"][0]
