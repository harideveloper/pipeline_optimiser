""" LLM Prompts for Pipeline Orchestration """

from typing import Dict, Any


DECISION_SYSTEM_PROMPT = """You are an expert CI/CD pipeline optimization agent.
    Your job: Decide whether to RUN or SKIP the next tool in the plan.

    Key principles:
    1. Follow the plan order - tools are already ordered correctly
    2. SKIP tools that aren't needed based on current state
    3. ALWAYS run mandatory tools (validate, analyse)
    4. Skip fix/review/resolve if no issues found
    5. Skip resolve if pr_create=false

    Return JSON:
    {
    "action": "run" or "skip",
    "reasoning": "Brief explanation of why"
    }
"""


DECISION_CONTEXT_TEMPLATE = """Decide whether to RUN or SKIP the next tool.
    CURRENT STATE
    ─────────────
    Workflow Type: {workflow_type}
    Risk Level: {risk_level}
    PR Requested: {pr_create}

    EXECUTION PROGRESS
    ──────────────────
    Completed: {completed_tools}
    Next Tool: {next_tool}
    Remaining: {remaining_tools}
    {analysis_summary}

    DECISION RULES
    ──────────────
    - validate, analyse: ALWAYS run (mandatory)
    - fix: RUN if issues found, SKIP if no issues
    - review: RUN if fix was applied, SKIP otherwise
    - resolve: RUN if pr_create=true AND fix was applied, SKIP otherwise
    - risk_assessment, security_scan: RUN for HIGH/MEDIUM risk, can SKIP for LOW

    CONTEXT-SPECIFIC HINTS
    ──────────────────────
    Fix applied: {fix_applied}
    Changes to commit: {fix_applied}

    Should you RUN or SKIP '{next_tool}'?
"""

# ANALYSER PROMPTS
ANALYSER_SYSTEM_PROMPT = """You are a DevOps pipeline expert specializing in CI/CD optimisation."""
ANALYSER_USER_PROMPT_TEMPLATE = """You are a CI/CD expert. Analyse this pipeline YAML for optimisation opportunities.

    Pipeline YAML:
    {pipeline_yaml}

    Build Log:
    {build_log}

    Return a JSON object with:
    {{
    "issues_detected": ["list of inefficiencies or problems found"],
    "suggested_fixes": ["concrete recommended changes to address the issues"],
    "expected_improvement": "estimated performance or efficiency gain",
    "is_fixable": true or false
    }}

    Be specific and actionable. Focus on:
    - Performance optimisation (caching, parallelisation)
    - Security improvements
    - Best practices
    - Resource efficiency
    - Maintainability improvements

    Ensure the lists are the same length - one fix per issue
"""

# FIXER PROMPTS
FIXER_SYSTEM_PROMPT = """You are a CI/CD pipeline optimisation expert. Apply fixes to YAML carefully, preserving structure and syntax. Return only valid YAML, no explanations."""
FIXER_USER_PROMPT_TEMPLATE = """You are a CI/CD pipeline optimisation expert.
    Apply the suggested fixes to the following pipeline YAML. Return ONLY the optimised YAML content, with no explanations, comments, or markdown.

    Original Pipeline YAML:
    ```yaml
    Suggested Fixes:
    {suggested_fixes}

    Return optimised YAML:
"""


# RISK ASSESSOR PROMPTS
RISK_ASSESSOR_SYSTEM_PROMPT = """You are a DevOps risk assessment expert specializing in CI/CD pipeline changes.

    Analyze proposed changes for:
    1. Breaking change probability
    2. Production impact severity
    3. Rollback difficulty
    4. Affected services and components

    Be thorough but realistic in your assessment.
"""

RISK_ASSESSOR_USER_PROMPT_TEMPLATE = """Analyze the risk of these proposed pipeline changes:

    Original Pipeline (first 500 chars):
    {pipeline_yaml_preview}

    Proposed Changes:
    {suggested_fixes_json}

    Assess:
    1. Breaking change probability (0-100%)
    2. Production impact severity (low/medium/high/critical)
    3. Rollback difficulty (easy/medium/hard)
    4. Affected services/jobs

    Return JSON:
    {{
        "risk_score": 0-100,
        "severity": "low|medium|high|critical",
        "breaking_changes": ["list of potential breaking changes"],
        "affected_components": ["list of affected components"],
        "rollback_plan": "description of rollback approach",
        "requires_manual_approval": true/false,
        "safe_to_auto_merge": true/false
    }}
"""


# Prompt Builders
def build_decision_context(state: Dict[str, Any], next_tool: str) -> str:
    """
    Build context for agent decision-making.
    
    Args:
        state: Current pipeline state
        next_tool: Name of the next tool to execute
        
    Returns:
        Formatted context string for LLM
    """

    completed = state.get("completed_tools", [])
    workflow_type = state.get("workflow_type", "UNKNOWN")
    risk_level = state.get("risk_level", "MEDIUM")
    pr_create = state.get("pr_create", False)
    plan = state.get("plan", [])
    plan_index = state.get("plan_index", 0)
    remaining_tools = plan[plan_index + 1:] if plan_index + 1 < len(plan) else []
    analysis_summary = ""
    if "analyse" in completed:
        issues = state.get("analysis_result", {}).get("issues_detected", [])
        analysis_summary = f"\nAnalysis: {len(issues)} issues found"
        if issues:
            analysis_summary += "\n  Issues need to be fixed"
        else:
            analysis_summary += "\n  Workflow is already optimal"
    
    fix_applied = "fix" in completed
    
    context = DECISION_CONTEXT_TEMPLATE.format(
        workflow_type=workflow_type,
        risk_level=risk_level,
        pr_create=pr_create,
        completed_tools=completed,
        next_tool=next_tool,
        remaining_tools=remaining_tools,
        analysis_summary=analysis_summary,
        fix_applied=fix_applied
    )
    
    return context


def build_analyser_prompt(pipeline_yaml: str, build_log: str = None) -> str:
    """
    Build analysis prompt for Analyser agent.
    
    Args:
        pipeline_yaml: Pipeline YAML content
        build_log: Optional build log
        
    Returns:
        Formatted prompt string
    """
    return ANALYSER_USER_PROMPT_TEMPLATE.format(
        pipeline_yaml=pipeline_yaml,
        build_log=build_log or "N/A"
    )


def build_fixer_prompt(pipeline_yaml: str, suggested_fixes: list) -> str:
    """
    Build fixer prompt for Fixer agent.
    
    Args:
        pipeline_yaml: Original pipeline YAML
        suggested_fixes: List of fixes to apply
        
    Returns:
        Formatted prompt string
    """
    fixes_text = "\n".join(f"{i+1}. {fix}" for i, fix in enumerate(suggested_fixes))
    
    return FIXER_USER_PROMPT_TEMPLATE.format(
        pipeline_yaml=pipeline_yaml,
        suggested_fixes=fixes_text
    )


def build_risk_assessor_prompt(pipeline_yaml: str, suggested_fixes: list) -> str:
    """
    Build risk assessment prompt for RiskAssessor agent.
    
    Args:
        pipeline_yaml: Original pipeline YAML
        suggested_fixes: List of proposed fixes
        
    Returns:
        Formatted prompt string
    """
    import json

    yaml_preview = pipeline_yaml[:500]   # Truncate YAML for context (first 500 chars) to save cost, should be revisted later 
    fixes_json = json.dumps(suggested_fixes, indent=2)
    
    return RISK_ASSESSOR_USER_PROMPT_TEMPLATE.format(
        pipeline_yaml_preview=yaml_preview,
        suggested_fixes_json=fixes_json
    )