"""
LLM Prompts for Pipeline Orchestration
Defines system prompts and context builders for decision-making
"""

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


def build_decision_context(state: Dict[str, Any], next_tool: str) -> str:
    """
    Build context for agent decision-making.
    
    Args:
        state: Current pipeline state
        next_tool: Name of the next tool to execute
        
    Returns:
        Formatted context string for LLM
    """
    completed = state["completed_tools"]
    analysis_summary = ""
    
    # Build analysis summary if analyse was completed
    if "analyse" in completed:
        issues = state.get("analysis_result", {}).get("issues_detected", [])
        analysis_summary = f"\nAnalysis: {len(issues)} issues found"
        if issues:
            analysis_summary += "\n  Issues need to be fixed"
        else:
            analysis_summary += "\n  Workflow is already optimal"
    
    fix_applied = "fix" in completed
    
    context = f"""Decide whether to RUN or SKIP the next tool.

        CURRENT STATE
        ─────────────
        Workflow Type: {state['workflow_type']}
        Risk Level: {state['risk_level']}
        PR Requested: {state['pr_create']}

        EXECUTION PROGRESS
        ──────────────────
        Completed: {completed}
        Next Tool: {next_tool}
        Remaining: {state['plan'][state['plan_index']+1:]}
        {analysis_summary}

        DECISION RULES
        ──────────────
        • validate, analyse: ALWAYS run (mandatory)
        • fix: RUN if issues found, SKIP if no issues
        • review: RUN if fix was applied, SKIP otherwise
        • resolve: RUN if pr_create=true AND fix was applied, SKIP otherwise
        • risk_assessment, security_scan: RUN for HIGH/MEDIUM risk, can SKIP for LOW

        CONTEXT-SPECIFIC HINTS
        ──────────────────────
        Fix applied: {fix_applied}
        Changes to commit: {fix_applied}

        Should you RUN or SKIP '{next_tool}'?
    """
    
    return context