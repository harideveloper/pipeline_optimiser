"""
Pipline Optimiser Orchestrator
"""

import os
from typing import Dict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END
from openai import OpenAI

from app.repository.pipeline_repository import PipelineRepository
from app.utils.correlation import generate_correlation_id
from app.utils.logger import get_logger

from app.orchestrator.state import PipelineState
from app.orchestrator.nodes import (
    plan_node,
    decision_node,
    execute_node,
    should_continue,
)

# Import components
from app.components.decision import Decision
from app.components.classifier import Classifier
from app.components.ingestor import Ingestor
from app.components.validator import Validator
from app.components.analyser import Analyser
from app.components.fixer import Fixer
from app.components.resolver import Resolver
from app.components.risk_assessor import RiskAssessor
from app.components.security_scanner import SecurityScanner
from app.components.reviewer import Reviewer

logger = get_logger(__name__, "PipelineOrchestrator")


class PipelineOrchestrator:
    """
    Simplified CI/CD Pipeline Optimization Orchestrator.
    
    """

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.1):
        """Initialize orchestrator with all components."""
        self.model_name = model_name
        self.temperature = temperature
        
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)
        
        # Initialize db delegate
        self.repository = PipelineRepository()
        
        # Initialize classifier
        self.classifier = Classifier()
        
        # Initialize decision agent
        self.decision_agent = Decision(
            model=model_name,
            temperature=temperature
        )
        
        # Initialize tool registry
        self.tools = {
            "ingest": Ingestor(),
            "validate": Validator(),
            "analyse": Analyser(),
            "risk_assessment": RiskAssessor(),
            "security_scan": SecurityScanner(),
            "fix": Fixer(),
            "review": Reviewer(),
            "resolve": Resolver(),
        }
        
        # Build LangGraph workflow
        self.graph = self._build_graph()
        
        logger.debug(
            f"Initialized Orchestrator: model={model_name}, temperature={temperature}",
            correlation_id="INIT"
        )

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow with 3 nodes."""
        workflow = StateGraph(PipelineState)
        
        # Register nodes
        workflow.add_node(
            "plan",
            lambda state: plan_node(state, self.tools["ingest"], self.classifier)
        )
        workflow.add_node(
            "decide",
            lambda state: decision_node(state, self.decision_agent)
        )
        workflow.add_node(
            "execute",
            lambda state: execute_node(state, self.tools)
        )
        
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "decide")
        
        workflow.add_conditional_edges(
            "decide",
            should_continue,
            {
                "continue": "execute",
                "end": END
            }
        )
        
        workflow.add_edge("execute", "decide")
        return workflow.compile()

    def run(
        self,
        repo_url: str,
        pipeline_path: str,
        build_log_path: str = None,
        branch: str = "main",
        pr_create: bool = False
    ) -> Dict[str, Any]:
        """
        Run the pipeline optimization workflow.
        
        NOW: Uses repository instead of direct db calls
        """
        correlation_id = generate_correlation_id()
        
        run_id = self.repository.start_run(
            repo_url=repo_url,
            branch=branch,
            trigger_source="API",
            correlation_id=correlation_id
        )
        
        logger.info(
            f"Starting pipeline optimization (run_id={run_id}, repo={repo_url})",
            correlation_id=correlation_id
        )
        
        # Initialize state
        initial_state: PipelineState = {
            "repo_url": repo_url,
            "pipeline_path": pipeline_path,
            "branch": branch,
            "pr_create": pr_create,
            "run_id": run_id,
            "build_log_path": build_log_path,
            "correlation_id": correlation_id,
            "pipeline_yaml": "",
            "build_log": "",
            "analysis_result": {},
            "optimised_yaml": "",
            "pr_url": None,
            "workflow_type": "UNKNOWN",
            "risk_level": "MEDIUM",
            "plan": [],
            "plan_index": 0,
            "completed_tools": [],
            "execution_log": [],
            "next_action": "",
            "agent_reasoning": "",
            "_current_tool": "",
        }
        
        try:
            # Execute workflow
            start_time = datetime.now()
            final_state = self.graph.invoke(initial_state)
            duration = (datetime.now() - start_time).total_seconds()
            
            # Log summary
            self._log_summary(final_state, duration)
            
            self.repository.complete_run(
                run_id=run_id,
                correlation_id=correlation_id
            )
            
            return {
                "success": True,
                "correlation_id": correlation_id,
                "workflow_type": final_state["workflow_type"],
                "risk_level": final_state["risk_level"],
                "completed_tools": final_state["completed_tools"],
                "pr_url": final_state.get("pr_url"),
                "duration": duration,
            }
            
        except Exception as e:
            logger.exception(f"Workflow failed: {e}", correlation_id=correlation_id)
            
            self.repository.fail_run(
                run_id=run_id,
                error=str(e),
                correlation_id=correlation_id
            )
            
            return {
                "success": False,
                "correlation_id": correlation_id,
                "error": str(e)
            }

    def _log_summary(self, state: PipelineState, duration: float) -> None:
        """Log execution summary."""
        cid = state["correlation_id"]
        
        logger.info(
            f"Workflow Type: {state['workflow_type']} | "
            f"Risk Level: {state['risk_level']} | "
            f"Duration: {duration:.2f}s",
            correlation_id=cid
        )
        
        logger.info(
            f"Planned Steps ({len(state['plan'])}): {' | '.join(state['plan'])}",
            correlation_id=cid
        )
        
        logger.info(
            f"Executed Steps ({len(state['completed_tools'])}): "
            f"{' | '.join(state['completed_tools'])}",
            correlation_id=cid
        )