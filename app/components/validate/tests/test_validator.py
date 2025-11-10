import pytest
from app.components.validate.validator import Validator


# Fixture
@pytest.fixture
def validator():
    return Validator()


# Tests
def test_run_detects_missing_keys(validator):
    """Detects missing required top-level keys."""
    yaml_content = "jobs:\n  build:\n    steps: []"
    result = validator.run(yaml_content, mode="input")
    assert result["valid"] is False
    assert "Missing required keys" in result["reason"]


def test_run_detects_circular_dependency(validator):
    """Detects circular job dependencies."""
    yaml_content = """on: push
jobs:
  build:
    needs: build
    steps:
      - run: echo hi
"""
    result = validator.run(yaml_content, mode="input")
    assert result["valid"] is False
    assert "circular dependency" in result["reason"].lower()


def test_run_detects_best_practices_issues(validator):
    """Reports best practices issues in output mode."""
    yaml_content = """on: push
jobs:
  build:
    steps:
      - run: echo hi
"""
    result = validator.run(yaml_content, mode="output")
    assert result["valid"] is True
    assert "issues" in result
    assert len(result["issues"]) > 0


def test_run_passes_valid_yaml(validator):
    """Passes valid YAML with required keys and dependencies."""
    yaml_content = """on: push
jobs:
  build:
    steps:
      - run: echo hi
    timeout-minutes: 10
"""
    result = validator.run(yaml_content, mode="input")
    assert result["valid"] is True
    assert "reason" in result


def test_execute_stores_result_and_error_on_failure(validator):
    """_execute stores validation results and error key in state on failure."""
    state = {"pipeline_yaml": "jobs:\n  build:\n    steps: []", "correlation_id": "cid"}
    updated = validator._execute(state)
    assert "validation_result" in updated
    assert updated["validation_result"]["valid"] is False
    assert "error" in updated
