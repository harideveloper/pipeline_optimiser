import pytest
from unittest.mock import MagicMock, patch
from app.components.optimise.optimiser import Optimiser
from app.exceptions import OptimiserError


@pytest.fixture
def optimiser():
    """Fixture for creating an Optimiser instance with mocks."""
    with patch("app.components.optimise.optimiser.config.get_optimiser_config", return_value={
        "model": "mock-model",
        "temperature": 0.3,
        "max_tokens": 500
    }):
        with patch("app.components.optimise.optimiser.LLMClient") as MockClient:
            mock_llm = MockClient.return_value
            opt = Optimiser()
            opt.llm_client = mock_llm
            return opt


def test_run_invalid_yaml_raises_error(optimiser):
    """Should raise OptimiserError for invalid or empty YAML input."""
    with pytest.raises(OptimiserError, match="pipeline_yaml must be a non-empty string"):
        optimiser.run("")

    with pytest.raises(OptimiserError):
        optimiser.run(None)


def test_analyse_pipeline_valid_response(optimiser):
    """Should correctly parse a valid analysis response."""
    optimiser._call_llm = MagicMock(return_value="mock-response")
    optimiser.llm_client.parse_json_response = MagicMock(return_value={
        "issues": [{"description": "test issue"}],
        "recommended_changes": [{"change": "fix"}]
    })

    result = optimiser._analyse_pipeline("valid: yaml")
    assert "issues" in result
    assert "recommended_changes" in result
    optimiser._call_llm.assert_called_once()


def test_execute_optimisations_missing_applied_fixes_field(optimiser):
    """Should add empty applied_fixes list if missing from execution result."""
    optimiser._call_llm = MagicMock(return_value="mock-response")
    optimiser.llm_client.parse_optimiser_response = MagicMock(return_value={
        "optimised_yaml": "name: test\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest"
    })

    result = optimiser._execute_optimisations("yaml", {"issues": []})
    assert "applied_fixes" in result
    assert isinstance(result["applied_fixes"], list)


def test_validate_yaml_success(optimiser):
    """Should pass valid YAML with required keys."""
    valid_yaml = """
    name: test
    on: push
    jobs:
      build:
        runs-on: ubuntu-latest
    """
    optimiser._validate_yaml(valid_yaml)  # Should not raise


def test_validate_yaml_missing_keys(optimiser):
    """Should raise OptimiserError if required keys are missing."""
    invalid_yaml = "invalid_yaml: true"
    with pytest.raises(OptimiserError, match="missing required top-level key"):
        optimiser._validate_yaml(invalid_yaml)
