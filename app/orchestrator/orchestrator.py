"""
Pipeline Optimiser Orchestrator
"""

from typing import Dict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END

from app.utils.correlation import generate_correlation_id
from app.utils.logger import get_logger
from app.components.decide.decision import Decision
from app.components.classify.classifier import Classifier
from app.components.ingest.ingestor import Ingestor
from app.components.validate.validator import Validator
from app.components.optimise.optimiser import Optimiser
from app.components.resolve.resolver import Resolver
from app.components.critique.critic import Critic
from app.components.risk.risk_assessor import RiskAssessor
from app.components.scan.security_scanner import SecurityScanner
from app.repository.pipeline_repository import PipelineRepository
from app.orchestrator.state import PipelineState
from app.orchestrator.nodes import plan_node, decision_node, execute_node, should_continue


logger = get_logger(__name__, "PipelineOrchestrator")


class PipelineOrchestrator:
    """CI/CD Pipeline Optimisation Orchestrator."""

    def __init__(self):
        self.repository = PipelineRepository()
        self.classifier = Classifier()
        self.decision_agent = Decision()
        validator = Validator()
        self.tools = {
            "ingest": Ingestor(),
            "validate": validator,
            "optimise": Optimiser(),
            "post_validate": validator,
            "critic": Critic(),
            "risk_assessment": RiskAssessor(),
            "security_scan": SecurityScanner(),
            "resolve": Resolver(),
        }
        
        self.graph = self._build_graph()
        
        logger.info("Initialised Orchestrator", correlation_id="INIT")

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(PipelineState)
        
        workflow.add_node("plan", lambda state: plan_node(state, self.tools["ingest"], self.classifier))
        workflow.add_node("decide", lambda state: decision_node(state, self.decision_agent))
        workflow.add_node("execute", lambda state: execute_node(state, self.tools))
        
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "decide")
        
        workflow.add_conditional_edges("decide", should_continue, {"continue": "execute", "end": END})
        
        workflow.add_edge("execute", "decide")
        return workflow.compile()

    async def run(self, repo_url: str, pipeline_path: str, build_log_path: str = None, branch: str = "main", pr_create: bool = False) -> Dict[str, Any]:
        correlation_id = generate_correlation_id()
        
        # Start run with pipeline_path (required)
        run_id = self.repository.start_run(
            repo_url=repo_url,
            pipeline_path=pipeline_path,
            branch=branch,
            trigger_source="API",
            correlation_id=correlation_id
        )
        
        logger.info(f"Starting pipeline optimisation (run_id={run_id}, repo={repo_url})", correlation_id=correlation_id)
        
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
            "validation_result": {},
            "post_validation_result": {},
            "optimisation_result": {},
            "critic_review": {},
            "risk_assessment": {},
            "security_scan": {},
            "resolve_result": {},
        }
        
        try:
            start_time = datetime.now()
            final_state = await self.graph.ainvoke(initial_state)  # Changed to ainvoke
            duration = (datetime.now() - start_time).total_seconds()

            self._log_summary(final_state, duration)
            
            # Complete run with duration
            self.repository.complete_run(
                run_id=run_id,
                duration_seconds=duration,
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
            self.repository.fail_run(run_id=run_id, error=str(e), correlation_id=correlation_id)
            return {"success": False, "correlation_id": correlation_id, "error": str(e)}

    def _log_summary(self, state: PipelineState, duration: float) -> None:
        cid = state["correlation_id"]
        logger.info(f"Workflow Type: {state['workflow_type']} | Risk Level: {state['risk_level']} | Duration: {duration:.2f}s", correlation_id=cid)
        logger.info(f"Planned Steps ({len(state['plan'])}): {' | '.join(state['plan'])}", correlation_id=cid)
        logger.info(f"Executed Steps ({len(state['completed_tools'])}): {' | '.join(state['completed_tools'])}", correlation_id=cid)