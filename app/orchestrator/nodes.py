"""
Workflow Node Implementations
"""

from typing import Dict, Any, Literal
from app.orchestrator.state import PipelineState
from app.utils.logger import get_logger

logger = get_logger(__name__, "PipelineNodes")

def plan_node(
    state: PipelineState,
    ingest_tool: Any,
    classifier: Any,
) -> PipelineState:
    """
    Node 1: Plan Workflow
    
    Steps:
    1. Ingest repository and extract pipeline YAML
    2. Classify workflow (type, risk level, scope)
    3. Generate execution plan based on risk profile
    
    Args:
        state: Current pipeline state
        ingest_tool: Ingestor tool instance
        classifier: Classifier instance
        
    Returns:
        Updated state with:
        - pipeline_yaml: Extracted YAML content
        - build_log: Optional build log
        - workflow_type: CI/CD/Release/etc
        - risk_level: HIGH/MEDIUM/LOW
        - plan: List of tool names to execute
    """

    cid = state["correlation_id"]
    logger.debug("Plan Node: Starting ingestion and classification", correlation_id=cid)
    
    # Step 1: Ingest repository
    state.update(ingest_tool.execute_node(state))
    
    if state.get("error"):
        logger.error(
            "Ingestion failed, cannot proceed with classification",
            correlation_id=cid
        )
        return state
    
    # Step 2: Classify and generate plan
    state = classifier.execute_node(state)
    
    logger.info(
        f"Generated Plan ({len(state['plan'])} steps): {' → '.join(state['plan'])}",
        correlation_id=cid
    )
    
    return state


def decision_node(
    state: PipelineState,
    decision_agent: Any,
) -> PipelineState:
    """
    Node 2: Make Decision
    
    Uses Decision Component (LLM) to decide whether to run or skip
    the next tool in the plan.
    
    Args:
        state: Current pipeline state
        decision_agent: DecisionAgent instance
        
    Returns:
        Updated state with:
        - next_action: "run", "skip", or "complete"
        - agent_reasoning: Explanation of decision
        - _current_tool: Name of tool to execute/skip
    """
    cid = state["correlation_id"]
    
    logger.debug("Decision Node: Agent deciding next action", correlation_id=cid)
    
    # Check for errors - stop if error occurred
    if state.get("error"):
        logger.debug("Error detected, stopping workflow", correlation_id=cid)
        state["next_action"] = "complete"
        state["agent_reasoning"] = f"Workflow stopped due to error: {state['error']}"
        return state
    
    # Early Exit: Post-validation failed
    post_validation_result = state.get("post_validation_result", {})
    if post_validation_result and not post_validation_result.get("valid", False):
        logger.info(
            "Post-validation failed - stopping workflow early (skip risk, security, resolve)",
            correlation_id=cid
        )
        state["next_action"] = "complete"
        state["agent_reasoning"] = "Post-validation failed, YAML is structurally broken"
        return state
    
    # EARLY EXIT 2: LLM review detected regressions
    critic_review = state.get("critic_review", {})
    merge_confidence = critic_review.get("merge_confidence", None)

    
    # Check if plan is complete
    if state["plan_index"] >= len(state["plan"]):
        logger.info(
            "Agent plan loop completed, no more tools to execute",
            correlation_id=cid
        )
        state["next_action"] = "complete"
        state["agent_reasoning"] = "All planned tools executed"
        return state
    
    # Get next tool from plan
    next_tool = state["plan"][state["plan_index"]]
    
    logger.debug(
        f"Next in plan: {next_tool} (index {state['plan_index']}/{len(state['plan'])-1})",
        correlation_id=cid
    )
    
    # Ask decision component: run or skip?
    state["_current_tool"] = next_tool
    state = decision_agent._execute(state)
    
    logger.debug(
        f"Decision: {state['next_action']} {next_tool} | Reasoning: {state['agent_reasoning']}",
        correlation_id=cid
    )
    
    return state


def execute_node(
    state: PipelineState,
    tools: Dict[str, Any],
) -> PipelineState:
    """
    Node 3: Execute Tool
    
    Execute or skip the current tool based on the decision made
    by the decision_node.
    
    Args:
        state: Current pipeline state
        tools: Tool registry (dict of tool_name -> tool_instance)
        
    Returns:
        Updated state with:
        - Tool-specific results (varies by tool)
        - completed_tools: List of executed tools
        - execution_log: Log of actions taken
        - plan_index: Incremented index
    """
    cid = state["correlation_id"]
    tool_name = state["_current_tool"]
    action = state["next_action"]
    
    # Skip case
    if action == "skip":
        logger.info(
            f"Skipping: {tool_name} | Reason: {state['agent_reasoning']}",
            correlation_id=cid
        )
        state["execution_log"].append(f"{tool_name}: skipped")
        state["plan_index"] += 1
        return state
    
    # Execute case
    logger.debug(f"Executing: {tool_name}", correlation_id=cid)
    
    try:
        tool = tools[tool_name]
        
        # Call tool's _execute method
        result = tool._execute(state)
        
        # Explicitly update state fields for LangGraph TypedDict
        for key, value in result.items():
            if key in state:
                state[key] = value
        
        if tool_name not in state["completed_tools"]:
            state["completed_tools"].append(tool_name)
        
        # Build log entry with tool-specific details
        log_entry = f"{tool_name}: completed"
        
        if tool_name == "optimise":
            issues = state.get("analysis_result", {}).get("issues_detected", [])
            fixes = len(state.get("optimisation_result", {}).get("applied_fixes", []))
            log_entry += f" ({len(issues)} issues found, {fixes} fixes applied)"
        elif tool_name == "resolve" and state.get("pr_url"):
            log_entry += f" (PR: {state['pr_url']})"
        
        state["execution_log"].append(log_entry)
        logger.debug(f"Completed: {tool_name}", correlation_id=cid)
        
    except Exception as e:
        logger.error(
            f"Tool execution failed: {tool_name} - {e}",
            correlation_id=cid
        )
        state["execution_log"].append(f"{tool_name}: FAILED - {e}")
    
    state["plan_index"] += 1
    return state


def should_continue(state: PipelineState) -> Literal["continue", "end"]:
    """
    Router: Decide whether to continue workflow or end.
    
    This is used as a conditional edge in LangGraph to determine
    whether to loop back to execute another tool or end the workflow.
    
    Args:
        state: Current pipeline state
        
    Returns:
        "continue": Continue to execute node
        "end": End workflow
    """
    if state.get("next_action") == "complete":
        return "end"
    
    return "continue"