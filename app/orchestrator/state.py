"""
Pipeline Orchestration State : Defines the state structure for the workflow
"""

from typing import TypedDict, Optional, Any, Dict, List


class PipelineState(TypedDict):
    """Pipeline optimiser workflow state"""
    
    # Core inputs
    repo_url: str
    pipeline_path: str
    branch: str
    pr_create: bool
    run_id: int
    build_log_path: Optional[str]
    correlation_id: str
    
    # Workflow artifacts
    pipeline_yaml: str
    build_log: str
    analysis_result: Dict[str, Any]
    optimised_yaml: str
    pr_url: Optional[str]
    
    # Classification
    workflow_type: str
    risk_level: str
    
    # Plan-based execution
    plan: List[str]
    plan_index: int
    
    # Execution tracking
    completed_tools: List[str]
    execution_log: List[str]
    
    # Agent decision
    next_action: str  # "run", "skip", or "complete"
    agent_reasoning: str
    _current_tool: str