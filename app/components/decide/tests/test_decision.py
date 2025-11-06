import pytest
from unittest.mock import MagicMock, patch
from app.components.decide.decision import Decision
from app.constants import ACTION_RUN, ACTION_SKIP
from app.exceptions import DecisionError


@pytest.fixture
def decision_agent():
    with patch("app.components.decide.decision.LLMClient") as MockClient:
        mock_llm = MockClient.return_value
        mock_llm.chat_completion.return_value = '{"action": "run", "reasoning": "Looks safe"}'
        mock_llm.parse_json_response.return_value = {"action": ACTION_RUN, "reasoning": "Looks safe"}
        yield Decision(model="mock-model")


def test_run_returns_valid_action(decision_agent):
    """Should call LLM and return a structured decision."""
    result = decision_agent.run(state={"correlation_id": "c1"}, next_tool="critic")
    assert result["action"] == ACTION_RUN
    assert "reasoning" in result


def test_run_handles_invalid_action(decision_agent):
    """Should default to ACTION_RUN if LLM returns invalid action."""
    decision_agent.llm_client.parse_json_response.return_value = {
        "action": "maybe",
        "reasoning": "unclear"
    }
    result = decision_agent.run(state={}, next_tool="critic")
    assert result["action"] == ACTION_RUN
    assert "unclear" in result["reasoning"]


def test_run_handles_decision_error(decision_agent):
    """Should raise DecisionError when triggered."""
    decision_agent.llm_client.chat_completion.side_effect = DecisionError("Bad LLM call")

    with pytest.raises(DecisionError):
        decision_agent.run(state={}, next_tool="critic")


def test_run_handles_generic_exception_gracefully(decision_agent):
    """Should not crash and should return ACTION_SKIP."""
    decision_agent.llm_client.chat_completion.side_effect = Exception("Boom!")
    result = decision_agent.run(state={}, next_tool="critic")
    assert result["action"] == ACTION_SKIP
    assert "Error" in result["reasoning"]


def test_execute_populates_state_and_saves(decision_agent):
    """Should execute decision and persist to repository."""
    mock_repo = MagicMock()
    decision_agent.repository = mock_repo

    state = {
        "_current_tool": "optimise",
        "run_id": "r123",
        "correlation_id": "c1"
    }
    result = decision_agent._execute(state)

    assert result["next_action"] == ACTION_RUN
    assert "agent_reasoning" in result
    mock_repo.save_decision.assert_called_once()


def test_execute_handles_missing_run_id(decision_agent):
    """Should log a warning but not attempt to save when run_id missing."""
    mock_repo = MagicMock()
    decision_agent.repository = mock_repo

    state = {"_current_tool": "optimise", "correlation_id": "c1"}
    result = decision_agent._execute(state)

    assert result["next_action"] == ACTION_RUN
    mock_repo.save_decision.assert_not_called()


def test_execute_handles_missing_tool(decision_agent):
    """Should skip when _current_tool missing."""
    state = {"run_id": "r1", "correlation_id": "c1"}
    result = decision_agent._execute(state)

    assert result["next_action"] == ACTION_SKIP
    assert "No tool specified" in result["agent_reasoning"]


def test_execute_handles_save_failure_gracefully(decision_agent):
    """Should log warning if saving decision fails."""
    mock_repo = MagicMock()
    mock_repo.save_decision.side_effect = Exception("DB error")
    decision_agent.repository = mock_repo

    state = {"_current_tool": "critic", "run_id": "r1"}
    result = decision_agent._execute(state)

    assert result["next_action"] == ACTION_RUN
    mock_repo.save_decision.assert_called_once()
