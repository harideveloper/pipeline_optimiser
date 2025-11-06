import pytest
from unittest.mock import MagicMock, patch
from app.components.critique.critic import Critic
from app.exceptions import CriticError


@pytest.fixture
def critic():
    """Fixture for creating a Critic instance with mocks."""
    with patch("app.components.critique.critic.config.get_critic_config", return_value={
        "model": "mock-model",
        "temperature": 0.2,
        "max_tokens": 256,
        "default_quality_score": 7,
        "regression_penalty": 0.1,
        "unresolved_penalty": 0.2
    }):
        with patch("app.components.critique.critic.LLMClient") as MockClient:
            mock_llm = MockClient.return_value
            c = Critic()
            c.llm_client = mock_llm
            return c


def test_run_raises_error_for_empty_yaml(critic):
    """Should raise CriticError when optimised_yaml is empty."""
    with pytest.raises(CriticError, match="optimised_yaml must be a non-empty string"):
        critic.run(original_yaml="data", optimised_yaml="", issues_detected=[], applied_fixes=[])


def test_run_success_with_valid_mock_response(critic):
    """Should return review with computed confidence scores."""
    critic.llm_client.chat_completion.return_value = '{"quality_score": 8}'
    critic.llm_client.parse_json_response.return_value = {"quality_score": 8}

    result = critic.run(
        original_yaml="name: test",
        optimised_yaml="name: test-optimised",
        issues_detected=[],
        applied_fixes=[]
    )

    assert "fix_confidence" in result
    assert "merge_confidence" in result
    assert result["fix_confidence"] == 0.8  # 8 / 10
    assert 0 <= result["merge_confidence"] <= 1


def test_compute_confidence_score_penalties(critic):
    """Should apply penalties for regressions and unresolved issues."""
    review = {
        "quality_score": 9,
        "regressions": ["r1"],
        "unresolved_issues": ["u1", "u2"]
    }

    result = critic._compute_confidence_score(review)

    # fix_confidence = 9 / 10 = 0.9
    assert result["fix_confidence"] == pytest.approx(0.9)

    # merge_confidence = 0.9 - (0.1*1) - (0.2*2) = 0.4
    assert result["merge_confidence"] == pytest.approx(0.4, 0.01)



def test_execute_populates_state_and_handles_save(critic):
    """Should populate state with critic_review and save it."""
    critic.run = MagicMock(return_value={"fix_confidence": 0.9, "merge_confidence": 0.8})
    critic.repository.save_review = MagicMock()

    state = {"run_id": "r1", "pipeline_yaml": "y", "optimised_yaml": "y2"}
    result = critic._execute(state)

    assert "critic_review" in result
    critic.repository.save_review.assert_called_once()


def test_execute_handles_save_failure_gracefully(critic):
    """Should log warning but not crash if save_review fails."""
    critic.run = MagicMock(return_value={"fix_confidence": 1.0, "merge_confidence": 0.9})
    critic.repository.save_review = MagicMock(side_effect=Exception("DB error"))

    state = {"run_id": "r2", "pipeline_yaml": "a", "optimised_yaml": "b"}
    result = critic._execute(state)

    assert "critic_review" in result
    assert result["critic_review"]["fix_confidence"] == 1.0
