"""
Comprehensive test for Pipeline Optimizer using Claude Sonnet.

Setup:
    pip install anthropic pyyaml pytest
    export ANTHROPIC_API_KEY="sk-ant-your-key-here"

Run:
    pytest test_optimiser.py -v
    OR
    pytest test_optimiser.py -v -s  (to see print output)
"""

import pytest
import yaml
from pathlib import Path
from personal.archive.pipeline_optimiser import PipelineOptimiser


# ============================================
# CHANGE THIS TO TEST DIFFERENT PIPELINES
# ============================================
YAML_PATH = Path("tests/pipelines/multi-step.yaml")
# YAML_PATH = Path("tests/pipelines/pipeline2.yaml")
# YAML_PATH = Path("tests/pipelines/docs-ci.yaml")


@pytest.fixture(scope="session")
def sample_pipeline():
    """Fixture to load the YAML pipeline content from file."""
    if not YAML_PATH.exists():
        raise FileNotFoundError(f"YAML file not found: {YAML_PATH}")
    return YAML_PATH.read_text(encoding="utf-8")


def compare_yamls(original: str, optimized: str) -> dict:
    """Compare original and optimized YAML to detect changes."""
    orig = yaml.safe_load(original)
    opt = yaml.safe_load(optimized)
    
    changes = {
        "jobs_added": [],
        "jobs_removed": [],
        "jobs_modified": [],
        "structure_preserved": True,
        "steps_changed": {}
    }
    
    # Check job changes
    orig_jobs = set(orig.get("jobs", {}).keys())
    opt_jobs = set(opt.get("jobs", {}).keys())
    
    changes["jobs_added"] = list(opt_jobs - orig_jobs)
    changes["jobs_removed"] = list(orig_jobs - opt_jobs)
    changes["jobs_modified"] = list(orig_jobs & opt_jobs)
    
    # Count step changes per job
    for job_name in changes["jobs_modified"]:
        orig_steps = len(orig.get("jobs", {}).get(job_name, {}).get("steps", []))
        opt_steps = len(opt.get("jobs", {}).get(job_name, {}).get("steps", []))
        if orig_steps != opt_steps:
            changes["steps_changed"][job_name] = {
                "original": orig_steps,
                "optimized": opt_steps,
                "delta": opt_steps - orig_steps
            }
    
    # Verify structure - note: 'on' key is parsed as boolean True in YAML
    changes["structure_preserved"] = (
        orig.get("name") == opt.get("name") and
        ("on" in opt or True in opt) and
        "jobs" in opt
    )
    
    return changes


def validate_fixes(result: dict, original_yaml: str) -> dict:
    """Validate that claimed fixes actually exist in the optimized YAML."""
    optimized_yaml = result["optimised_yaml"]
    parsed_yaml = yaml.safe_load(optimized_yaml)
    original_parsed = yaml.safe_load(original_yaml)
    applied_fixes = result["applied_fixes"]
    issues_detected = result["issues_detected"]
    
    validation = {
        "all_valid": True,
        "validations": []
    }
    
    for issue in issues_detected:
        issue_type = issue.get("type", "")
        fix_validated = None
        fix_details = ""
        
        if issue_type == "caching":
            cache_found = False
            for job_name, job_data in parsed_yaml.get("jobs", {}).items():
                for step in job_data.get("steps", []):
                    if "uses" in step and "cache" in step["uses"].lower():
                        cache_found = True
                        fix_details = f"✓ Found cache action: {step['uses']} in job '{job_name}'"
                        break
                if cache_found:
                    break
            
            if cache_found:
                fix_validated = True
            else:
                claimed = any("cach" in str(fix).lower() for fix in applied_fixes)
                if claimed:
                    fix_validated = False
                    fix_details = "❌ Cache action claimed but NOT found in optimized YAML"
                else:
                    fix_validated = None
                    fix_details = "⚠️  Caching issue detected but fix not attempted"
        
        elif issue_type == "parallelization":
            issue_desc = issue.get("description", "").lower()
            jobs = parsed_yaml.get("jobs", {})
            orig_jobs = original_parsed.get("jobs", {})
            
            parallelization_improved = False
            
            if "frontend" in issue_desc and "backend" in issue_desc:
                orig_frontend_needs = orig_jobs.get("frontend", {}).get("needs")
                opt_frontend_needs = jobs.get("frontend", {}).get("needs")
                
                if orig_frontend_needs and not opt_frontend_needs:
                    parallelization_improved = True
                    fix_details = "✓ Frontend no longer depends on backend"
                elif orig_frontend_needs == opt_frontend_needs:
                    fix_details = "❌ Frontend still has same dependencies"
                else:
                    fix_details = "⚠️  Dependency structure changed - manual review needed"
            else:
                orig_deps = sum(1 for j in orig_jobs.values() if "needs" in j)
                opt_deps = sum(1 for j in jobs.values() if "needs" in j)
                
                if opt_deps < orig_deps:
                    parallelization_improved = True
                    fix_details = f"✓ Reduced job dependencies from {orig_deps} to {opt_deps}"
                elif opt_deps == orig_deps:
                    fix_details = f"⚠️  Same number of job dependencies ({opt_deps})"
                else:
                    fix_details = f"❌ More dependencies after optimization ({orig_deps} → {opt_deps})"
            
            claimed = any("parallel" in str(fix).lower() for fix in applied_fixes)
            if claimed and not parallelization_improved:
                fix_validated = False
            elif claimed and parallelization_improved:
                fix_validated = True
            else:
                fix_validated = None
                if not fix_details:
                    fix_details = "⚠️  Parallelization issue detected but fix not attempted"
        
        elif issue_type == "redundant":
            fix_validated = None
            fix_details = "⚠️  Redundancy fixes require manual review"
        
        else:
            fix_validated = None
            fix_details = f"⚠️  Unknown issue type '{issue_type}' - manual review needed"
        
        validation["validations"].append({
            "issue_type": issue_type,
            "description": issue.get("description", "N/A"),
            "validated": fix_validated,
            "details": fix_details
        })
        
        if fix_validated is False:
            validation["all_valid"] = False
    
    return validation


def test_pipeline_optimizer(sample_pipeline):
    """Test optimizer on a single YAML file - uses pytest fixture for loading."""
    print(f"\n{'='*70}")
    print(f"TESTING PIPELINE OPTIMIZER WITH CLAUDE SONNET")
    print(f"{'='*70}")
    
    # Initialize optimizer
    optimizer = PipelineOptimiser()
    
    # YAML content loaded from fixture
    pipeline_yaml = sample_pipeline
    print(f"\n✓ Testing file: {YAML_PATH}")
    print(f"{'='*70}\n")
    
    # Run optimizer
    result = optimizer.optimise_pipeline(pipeline_yaml)
    
    # Validate keys exist
    assert "optimised_yaml" in result, "Missing 'optimised_yaml' key"
    assert "issues_detected" in result, "Missing 'issues_detected' key"
    assert "applied_fixes" in result, "Missing 'applied_fixes' key"
    assert "expected_improvement" in result, "Missing 'expected_improvement' key"
    
    # Validate YAML is parseable
    parsed_yaml = yaml.safe_load(result["optimised_yaml"])
    assert "name" in parsed_yaml, "Optimized YAML missing 'name'"
    assert "on" in parsed_yaml or True in parsed_yaml, "Optimized YAML missing 'on' trigger"
    assert "jobs" in parsed_yaml, "Optimized YAML missing 'jobs'"
    
    # Compare with original
    changes = compare_yamls(pipeline_yaml, result["optimised_yaml"])
    
    # Validate fixes
    validation_report = validate_fixes(result, pipeline_yaml)
    
    # Print results
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    
    print(f"\n📊 Changes Detected:")
    print(f"  • Jobs added: {len(changes['jobs_added'])}")
    print(f"  • Jobs removed: {len(changes['jobs_removed'])}")
    print(f"  • Jobs modified: {len(changes['jobs_modified'])}")
    print(f"  • Steps changed: {len(changes['steps_changed'])} jobs")
    
    if changes['steps_changed']:
        for job, delta in changes['steps_changed'].items():
            print(f"    - {job}: {delta['original']} → {delta['optimized']} steps ({delta['delta']:+d})")
    
    print(f"\n🔍 Issues Detected: {len(result['issues_detected'])}")
    for i, issue in enumerate(result['issues_detected'], 1):
        print(f"  {i}. [{issue['severity'].upper()}] {issue['type']}")
        print(f"     {issue['description']}")
        print(f"     @ {issue['location']}")
    
    print(f"\n✅ Fixes Applied: {len(result['applied_fixes'])}")
    for i, fix in enumerate(result['applied_fixes'], 1):
        print(f"  {i}. {fix['issue']}")
        print(f"     → {fix['fix']}")
        print(f"     @ {fix['location']}")
    
    print(f"\n🔬 Fix Validation:")
    for v in validation_report['validations']:
        status = "✓" if v['validated'] else "✗" if v['validated'] is False else "⚠️"
        print(f"  {status} {v['issue_type']}: {v['description'][:60]}")
        print(f"     {v['details']}")
    
    print(f"\n📈 Expected Improvement:")
    print(f"  • Time saved: {result['expected_improvement']['estimated_time_saved']}")
    print(f"  • Summary: {result['expected_improvement']['summary']}")
    
    # Assertions
    assert changes["structure_preserved"], "❌ Optimizer broke YAML structure"
    assert len(changes["jobs_removed"]) == 0, f"❌ Optimizer removed jobs: {changes['jobs_removed']}"
    
    if not validation_report["all_valid"]:
        print("\n⚠️  WARNING: Some fixes were claimed but not validated in the output")
        print("   This might indicate the optimizer claimed to apply fixes that aren't present")
    
    print(f"\n{'='*70}")
    print("✓ ALL TESTS PASSED")
    print("="*70 + "\n")
    
    return result


if __name__ == "__main__":
    import sys
    
    # When running standalone (not via pytest), manually load and run
    print("Running test standalone (not via pytest)...")
    print("For full pytest features, run: pytest test_optimiser.py -v -s\n")
    
    try:
        # Manually load the pipeline
        if not YAML_PATH.exists():
            raise FileNotFoundError(f"YAML file not found: {YAML_PATH}")
        
        pipeline_content = YAML_PATH.read_text(encoding="utf-8")
        
        # Run the test function manually
        test_pipeline_optimizer(pipeline_content)
        print("\n✓ Test completed successfully!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        sys.exit(1)