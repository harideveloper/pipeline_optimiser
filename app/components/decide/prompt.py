from typing import Dict, Any

DECISION_SYSTEM_PROMPT = """You are an expert CI/CD pipeline optimisation agent. Your job: Decide whether to RUN or SKIP the next tool in the plan.

Key principles:
1. Follow the plan order - tools are already ordered correctly
2. Apply the decision rules strictly based on current state
3. ALWAYS validate your decision against the rules below
4. Fail fast - skip remaining tools when outcome is already determined

Return JSON only:
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
Validation Status: {validation_status}
Post-Validation Status: {post_validation_status}

EXECUTION PROGRESS
──────────────────
Completed: {completed_tools}
Next Tool: {next_tool}
Remaining: {remaining_tools}

{analysis_summary}

DECISION RULES (APPLY STRICTLY)
────────────────────────────────
CRITICAL: Read these rules carefully for the CURRENT tool '{next_tool}'

1. validate: ALWAYS RUN (first step)
   - If validation fails, STOP WORKFLOW (all subsequent tools SKIPPED)

2. optimise: 
   - RUN if 'validate' passed
   - SKIP if 'validate' failed

3. post_validate: 
   - RUN if 'optimise' completed and Optimised YAML Exists = true
   - SKIP if 'optimise' was skipped
   - SKIP if Optimised YAML Exists = false
   - If post_validate fails, STOP WORKFLOW (all subsequent tools SKIPPED)

4. llm_review:
   - RUN if post_validate passed
   - DO NOT block downstream steps regardless of confidence
   - Record fix_confidence and merge_confidence to state for PR comments

5. risk_assessment:
   - RUN for HIGH/MEDIUM risk workflows if llm_review merge_confidence >= 0.5 or was skipped
   - SKIP for LOW risk workflows
   - SKIP if post_validate failed

6. security_scan:
   - RUN for HIGH/MEDIUM risk workflows if llm_review merge_confidence >= 0.5 or was skipped
   - SKIP for LOW risk workflows
   - SKIP if post_validate failed

7. resolve (final step):
   - SKIP if pr_create = false
   - SKIP if post_validate failed
   - RUN if llm_review completed
   - For llm_review merge_confidence < 0.25: RUN only if risk_score >= 50 AND no major security issues
   - For llm_review merge_confidence >= 0.25: RUN if risk_score >= 50 AND no major security issues

CONTEXT DATA (for reference only)
─────────────────────
Validation Failed: {validation_failed}
Post-Validation Failed: {post_validation_failed}
Optimised YAML Exists: {optimised_yaml_exists}
LLM Review Fix Confidence: {llm_review_fix_confidence}
LLM Review Merge Confidence: {llm_review_merge_confidence}
Risk Score: {risk_score}
Security Major Issues: {security_major_issues}
Changes Applied: {changes_applied}

DECISION FOR: '{next_tool}'
Should you RUN or SKIP this tool?
"""

def build_decision_context(state: Dict[str, Any], next_tool: str) -> str:
    """
    Build decision context from workflow state using numeric LLM review confidences.
    """
    workflow_type = state.get("workflow_type", "UNKNOWN")
    risk_level = state.get("risk_level", "MEDIUM")
    pr_create = state.get("pr_create", False)
    
    completed_tools = state.get("completed_tools", [])
    remaining_tools = state.get("remaining_tools", [])
    
    validation_result = state.get("validation_result", {})
    validation_failed = not validation_result.get("valid", False) if validation_result else False
    validation_status = "FAILED" if validation_failed else ("PASSED" if validation_result else "NOT_RUN")
    
    post_validation_result = state.get("post_validation_result", {})
    post_validation_failed = not post_validation_result.get("valid", False) if post_validation_result else False
    post_validation_status = "FAILED" if post_validation_failed else ("PASSED" if post_validation_result else "NOT_RUN")
    
    risk_assessment = state.get("risk_assessment", {})
    risk_score = risk_assessment.get("overall_score", 100)
    
    security_scan = state.get("security_scan", {})
    security_major_issues = security_scan.get("has_major_issues", False)
    
    optimise_result = state.get("optimise", {})
    analysis_result = state.get("analysis_result", {})
    changes_applied = bool(optimise_result.get("changes_applied", False) or len(analysis_result.get("suggested_fixes", [])) > 0)
    optimised_yaml_exists = bool(state.get("optimised_yaml", "").strip())
    
    llm_review_result = state.get("llm_review", {})
    fix_confidence = llm_review_result.get("fix_confidence", None)
    merge_confidence = llm_review_result.get("merge_confidence", None)
    
    # Build analysis summary
    analysis_summary = ""
    if validation_result:
        issues_count = len(validation_result.get("issues", []))
        analysis_summary += f"Validation: {validation_status}"
        if issues_count:
            analysis_summary += f" ({issues_count} issues)"
        analysis_summary += "\n"
    if post_validation_result:
        issues_count = len(post_validation_result.get("issues", []))
        analysis_summary += f"Post-Validation: {post_validation_status}"
        if issues_count:
            analysis_summary += f" ({issues_count} best practice issues)"
        analysis_summary += "\n"
    if optimise_result or optimised_yaml_exists:
        changes_count = len(analysis_result.get("suggested_fixes", []))
        analysis_summary += f"Optimisations Applied: {changes_count}\n"
    if llm_review_result:
        analysis_summary += (
            f"LLM Review: Fix Confidence={fix_confidence}, Merge Confidence={merge_confidence}\n"
        )
    if risk_assessment:
        analysis_summary += f"Risk Score: {risk_score}/100\n"
    if security_scan:
        vuln_count = len(security_scan.get("vulnerabilities", []))
        analysis_summary += f"Security Issues: {vuln_count} ({'MAJOR' if security_major_issues else 'minor'})\n"
    
    context = DECISION_CONTEXT_TEMPLATE.format(
        workflow_type=workflow_type,
        risk_level=risk_level,
        pr_create=pr_create,
        validation_status=validation_status,
        post_validation_status=post_validation_status,
        completed_tools=", ".join(completed_tools) if completed_tools else "None",
        next_tool=next_tool,
        remaining_tools=", ".join(remaining_tools) if remaining_tools else "None",
        analysis_summary=analysis_summary if analysis_summary else "No analysis data yet",
        validation_failed=validation_failed,
        post_validation_failed=post_validation_failed,
        risk_score=risk_score,
        security_major_issues=security_major_issues,
        changes_applied=changes_applied,
        optimised_yaml_exists=optimised_yaml_exists,
        llm_review_fix_confidence=fix_confidence,
        llm_review_merge_confidence=merge_confidence
    )
    
    return context

