import pytest
from app.components.classify.classifier import Classifier, ClassifierProfile
from app.constants import (
    WORKFLOW_TYPE_CI,
    WORKFLOW_TYPE_CD,
    WORKFLOW_TYPE_RELEASE,
    WORKFLOW_TYPE_SCHEDULED,
    WORKFLOW_TYPE_MANUAL,
    WORKFLOW_TYPE_UNKNOWN,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    RISK_LEVEL_HIGH,
    CHANGE_SCOPE_CODE,
    CHANGE_SCOPE_DEPLOYMENT,
    CHANGE_SCOPE_DOCS_ONLY,
    TOOL_VALIDATE,
    TOOL_OPTIMISE,
    TOOL_POST_VALIDATE,
    TOOL_CRITIC,
    TOOL_SECURITY_SCAN,
    TOOL_RISK_ASSESSMENT,
    TOOL_RESOLVE
)

@pytest.fixture
def classifier():
    return Classifier()

# Main entry points
def test_run_executes_successfully_with_minimal_state(classifier):
    state = {"pipeline_yaml": "on: [push]\njobs: {build: {steps: []}}", "run_id": "r1"}
    result = classifier.run(state=state)
    assert "workflow_type" in result
    assert "plan" in result
    assert isinstance(result["plan"], list)

def test_execute_handles_invalid_yaml_gracefully(classifier):
    state = {"pipeline_yaml": "!!!not_yaml", "run_id": "r1"}
    result = classifier._execute(state)
    assert result["workflow_type"] == WORKFLOW_TYPE_UNKNOWN
    assert result["risk_level"] == RISK_LEVEL_MEDIUM
    assert isinstance(result["plan"], list)


# Test Workflow type detection Logic
def test_detects_ci_workflow_from_pr_trigger(classifier):
    wf = {"on": {"pull_request": {}}, "jobs": {"test": {"steps": []}}}
    result = classifier._detect_workflow_type(wf)
    assert result == WORKFLOW_TYPE_CI

def test_detects_cd_workflow_from_push_to_main_with_deploy_job(classifier):
    wf = {
        "on": {"push": {"branches": ["main"]}},
        "jobs": {"deploy": {"steps": [{"name": "deploy to prod"}]}}
    }
    result = classifier._detect_workflow_type(wf)
    assert result == WORKFLOW_TYPE_CD

def test_detects_release_workflow(classifier):
    wf = {"on": {"release": {}}, "jobs": {"publish": {"steps": []}}}
    result = classifier._detect_workflow_type(wf)
    assert result == WORKFLOW_TYPE_RELEASE

def test_detects_scheduled_workflow(classifier):
    wf = {"on": {"schedule": {}}, "jobs": {"job": {"steps": []}}}
    result = classifier._detect_workflow_type(wf)
    assert result == WORKFLOW_TYPE_SCHEDULED

def test_detects_manual_workflow(classifier):
    wf = {"on": {"workflow_dispatch": {}}, "jobs": {"job": {"steps": []}}}
    result = classifier._detect_workflow_type(wf)
    assert result == WORKFLOW_TYPE_MANUAL

def test_detects_unknown_workflow_when_no_triggers(classifier):
    wf = {"jobs": {}}
    result = classifier._detect_workflow_type(wf)
    assert result == WORKFLOW_TYPE_UNKNOWN


# Test Risk scoring logic
def test_calculates_high_risk_for_production_deploy(classifier):
    wf = {
        "jobs": {
            "deploy": {
                "steps": [{"name": "Deploy to production with terraform"}],
                "environment": "production"
            }
        }
    }
    result = classifier._calculate_risk_level(wf)
    assert result == RISK_LEVEL_HIGH

def test_calculates_medium_risk_for_security_and_db_ops(classifier):
    wf = {
        "jobs": {
            "build": {
                "steps": [
                    {"run": "python manage.py migrate"},
                    {"run": "aws s3 sync"}
                ]
            }
        }
    }
    result = classifier._calculate_risk_level(wf)
    assert result == RISK_LEVEL_MEDIUM

def test_calculates_low_risk_for_basic_build(classifier):
    wf = {"jobs": {"build": {"steps": [{"run": "echo hello"}]}}}
    result = classifier._calculate_risk_level(wf)
    assert result == RISK_LEVEL_LOW


# Test Change scope detection logic
def test_detects_deployment_scope(classifier):
    wf = {"jobs": {"deploy": {"steps": [{"run": "deploy to prod"}]}}}
    assert classifier._detect_change_scope(wf) == CHANGE_SCOPE_DEPLOYMENT

def test_detects_code_scope(classifier):
    wf = {"jobs": {"test": {"steps": [{"run": "pytest"}]}}}
    assert classifier._detect_change_scope(wf) == CHANGE_SCOPE_CODE

def test_detects_docs_scope(classifier):
    wf = {"jobs": {"docs": {"steps": [{"run": "generate documentation"}]}}}
    assert classifier._detect_change_scope(wf) == CHANGE_SCOPE_DOCS_ONLY



# Test Plan generation logic
def test_generate_plan_for_high_risk_includes_security_and_risk_assessment(classifier):
    plan = classifier._generate_plan(RISK_LEVEL_HIGH, pr_create=False)
    assert TOOL_SECURITY_SCAN in plan
    assert TOOL_RISK_ASSESSMENT in plan

def test_generate_plan_adds_resolve_if_pr_create_true(classifier):
    plan = classifier._generate_plan(RISK_LEVEL_LOW, pr_create=True)
    assert TOOL_RESOLVE in plan
    assert plan[-1] == TOOL_RESOLVE


# Test plan strategy creation
def test_create_strategy_exact_match(classifier):
    strat = classifier._create_strategy(WORKFLOW_TYPE_CI, RISK_LEVEL_LOW, CHANGE_SCOPE_CODE)
    assert "mandatory" in strat and isinstance(strat["mandatory"], list)

def test_create_strategy_fallback(classifier):
    strat = classifier._create_strategy(WORKFLOW_TYPE_CD, RISK_LEVEL_LOW, CHANGE_SCOPE_DOCS_ONLY)
    assert "mandatory" in strat

def test_get_default_profile_returns_safe_defaults(classifier):
    prof = classifier._get_default_profile()
    assert isinstance(prof, ClassifierProfile)
    assert prof.workflow_type == WORKFLOW_TYPE_UNKNOWN
    assert prof.risk_level == RISK_LEVEL_MEDIUM
