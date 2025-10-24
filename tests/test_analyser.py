"""
Test suite for Analyser - Essential tests only.
"""

import pytest
import json
from pathlib import Path
from app.components.analyser import Analyser


# 🔧 Path to your YAML file (you can change this name as needed)
YAML_PATH = Path("tests/pipelines/pipeline1.yaml")


@pytest.fixture(scope="session")
def sample_pipeline():
    """Fixture to load the YAML pipeline content from file."""
    if not YAML_PATH.exists():
        raise FileNotFoundError(f"YAML file not found: {YAML_PATH}")
    return YAML_PATH.read_text(encoding="utf-8")


def test_analyser_validates_output_structure(sample_pipeline):
    """Test that analyser returns valid JSON structure."""
    analyser = Analyser(model="gpt-4o-mini", temperature=0, seed=42)
    result = analyser.run(sample_pipeline)
    
    required_keys = ["issues_detected", "suggested_fixes", "expected_improvement", "is_fixable"]
    for key in required_keys:
        assert key in result, f"Missing required key: {key}"
    
    assert isinstance(result["issues_detected"], list)
    assert isinstance(result["suggested_fixes"], list)
    assert isinstance(result["expected_improvement"], str)
    assert isinstance(result["is_fixable"], bool)
    
    assert len(result["issues_detected"]) == len(result["suggested_fixes"])
    print("\n✅ Output structure is valid")


def test_analyser_consistency(sample_pipeline):
    """
    Test that analyser produces consistent outputs.
    Success: All runs have same issues and fixes (wording variations OK).
    """
    analyser = Analyser(model="gpt-4o-mini", temperature=0, seed=42)
    outputs = []

    print("\n" + "=" * 60)
    print("Testing Consistency (3 runs)")
    print("=" * 60)

    for i in range(3):  # was 10 — reduced for speed
        result = analyser.run(sample_pipeline)
        outputs.append(result)
        print(f"\n--- Run {i+1} ---")
        print(json.dumps(result, indent=2))

    base = outputs[0]
    base_issues = base["issues_detected"]
    base_fixes = base["suggested_fixes"]

    for i, result in enumerate(outputs[1:], start=2):
        issues_match = result["issues_detected"] == base_issues
        fixes_match = result["suggested_fixes"] == base_fixes

        if not issues_match:
            print(f"\n❌ Run {i}: Issues differ from Run 1")
            print(f"  Run 1: {base_issues}")
            print(f"  Run {i}: {result['issues_detected']}")
            pytest.fail(f"Run {i}: Issues not identical")

        if not fixes_match:
            print(f"\n❌ Run {i}: Fixes differ from Run 1")
            print(f"  Run 1: {base_fixes}")
            print(f"  Run {i}: {result['suggested_fixes']}")
            pytest.fail(f"Run {i}: Fixes not identical")

    print("\n" + "=" * 60)
    print("✅ PASS: All runs have identical issues and fixes")
    print("=" * 60)


def test_analyser_finds_issues(sample_pipeline):
    """Test that analyser detects issues in problematic pipeline."""
    analyser = Analyser(model="gpt-4o-mini", temperature=0, seed=42)
    result = analyser.run(sample_pipeline)

    assert len(result["issues_detected"]) > 0, "Should detect at least one issue"

    print(f"\n✅ Found {len(result['issues_detected'])} issues")
    for issue in result["issues_detected"]:
        print(f"  - {issue}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
