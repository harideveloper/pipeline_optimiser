"""
CI/CD Pipeline Optimisation Orchestrator - LangGraph Version
Refactored to include DB integration (auto-increment repo_id)
"""

import os
import logging
from typing import TypedDict, Optional, Any, Dict
from typing_extensions import Literal

from langgraph.graph import StateGraph, END

from app.db import db  # DB helper module

logger = logging.getLogger(__name__)

# ---------------------------
# PIPELINE STATE
# ---------------------------
class PipelineState(TypedDict):
    """State that flows through the pipeline workflow."""
    repo_id: int
    repo_url: str
    pipeline_path: str
    build_log_path: Optional[str]
    branch: str
    pr_create: bool

    pipeline_yaml: str
    build_log: str
    validation_result: Dict[str, Any]
    analysis_result: Dict[str, Any]

    optimised_yaml: str
    pr_url: Optional[str]
    run_id: Optional[int]
    error: Optional[str]

# ---------------------------
# ORCHESTRATOR
# ---------------------------
class PipelineOrchestrator:
    """
    Orchestrates CI/CD optimisation using LangGraph.
    """

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0, verbose: bool = False):
        self.model_name = model_name
        self.temperature = temperature
        self.verbose = verbose
        self.graph = self._build_graph()
        logger.info("Initialized LangGraph Pipeline: model=%s, verbose=%s", model_name, verbose)

    # ---------------------------
    # GRAPH SETUP
    # ---------------------------
    def _build_graph(self):
        workflow = StateGraph(PipelineState)
        workflow.add_node("ingest", self._ingest_node)
        workflow.add_node("validate", self._validate_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("fix", self._fix_node)
        workflow.add_node("create_pr", self._create_pr_node)

        workflow.set_entry_point("ingest")
        workflow.add_edge("ingest", "validate")
        workflow.add_edge("validate", "analyze")
        workflow.add_edge("analyze", "fix")
        workflow.add_conditional_edges(
            "fix",
            self._should_create_pr,
            {"create_pr": "create_pr", "end": END}
        )
        workflow.add_edge("create_pr", END)
        return workflow.compile()

    # ---------------------------
    # RUN METHOD
    # ---------------------------
    def run(
        self,
        repo_url: str,
        pipeline_path: str,
        build_log_path: Optional[str] = None,
        branch: str = "main",
        pr_create: bool = False
    ) -> Dict[str, Any]:

        # Fetch or create repo in DB
        repo_id = db.get_or_create_repo(repo_url=repo_url, default_branch=branch)
        logger.info("Using repo_id=%d for repo=%s", repo_id, repo_url)

        # Insert a new run record
        run_id = db.create_run(repo_id=repo_id, commit_sha=None, trigger_source="API")
        logger.info("Created run_id=%d for optimisation run", run_id)

        state: PipelineState = {
            "repo_id": repo_id,
            "repo_url": repo_url,
            "pipeline_path": pipeline_path,
            "build_log_path": build_log_path,
            "branch": branch,
            "pr_create": pr_create,
            "pipeline_yaml": "",
            "build_log": "",
            "validation_result": {},
            "analysis_result": {},
            "optimised_yaml": "",
            "pr_url": None,
            "run_id": run_id,
            "error": None
        }

        try:
            final_state = self.graph.invoke(state)
            self._log_summary(final_state)

            # Update run status
            if final_state.get("error"):
                db.update_run_status(run_id=run_id, status="failed")
            else:
                db.update_run_status(run_id=run_id, status="completed")

            return {
                "analysis": final_state.get("analysis_result"),
                "optimised_yaml": final_state.get("optimised_yaml"),
                "pr_url": final_state.get("pr_url"),
                "error": final_state.get("error")
            }
        except Exception as e:
            logger.exception("Graph execution failed")
            db.update_run_status(run_id=run_id, status="failed")
            return {"analysis": None, "optimised_yaml": None, "pr_url": None, "error": str(e)}

    # ---------------------------
    # GRAPH NODES (unchanged logic)
    # ---------------------------
    def _ingest_node(self, state: PipelineState) -> PipelineState:
        if state.get("error"):
            return state
        try:
            from app.agents.ingestor import IngestorAgent
            pipeline_yaml, build_log = IngestorAgent().run(
                repo_url=state["repo_url"],
                pipeline_path_in_repo=state["pipeline_path"],
                build_log_path_in_repo=state["build_log_path"],
                branch=state["branch"]
            )
            state["pipeline_yaml"] = pipeline_yaml or ""
            state["build_log"] = build_log or ""
            if not pipeline_yaml:
                state["error"] = "Ingestor returned empty pipeline_yaml"

            # Save artifact
            db.insert_artifact(run_id=state["run_id"], stage="ingestor",
                               content=pipeline_yaml, metadata={"build_log": build_log})
        except Exception as e:
            state["error"] = f"Ingest failed: {e}"
            logger.exception(state["error"])
        return state

    def _validate_node(self, state: PipelineState) -> PipelineState:
        if state.get("error"):
            return state
        try:
            from app.agents.validator import ValidatorAgent
            result = ValidatorAgent().run(pipeline_yaml=state["pipeline_yaml"])
            state["validation_result"] = result if isinstance(result, dict) else {"valid": True}

            # Save artifact
            db.insert_artifact(run_id=state["run_id"], stage="validator",
                               content=str(state["validation_result"]), metadata={})
        except Exception as e:
            state["error"] = f"Validation failed: {e}"
            logger.exception(state["error"])
        return state

    def _analyze_node(self, state: PipelineState) -> PipelineState:
        if state.get("error"):
            return state
        try:
            from app.agents.analyser import AnalyserAgent
            analysis_result = AnalyserAgent().run(
                pipeline_yaml=state["pipeline_yaml"],
                build_log=state["build_log"]
            )

            # Ensure a dict structure
            if not isinstance(analysis_result, dict):
                analysis_result = {
                    "issues_detected": [],
                    "suggested_fixes": [],
                    "expected_improvement": "",
                    "is_fixable": False
                }

            state["analysis_result"] = analysis_result

            # Insert issues into DB
            issues_detected = analysis_result.get("issues_detected", [])
            suggested_fixes = analysis_result.get("suggested_fixes", [])

            for i, issue_text in enumerate(issues_detected):
                fix_text = suggested_fixes[i] if i < len(suggested_fixes) else "TBD"
                issue_dict = {
                    "type": "generic",
                    "description": issue_text,
                    "severity": "medium",
                    "suggested_fix": fix_text
                }
                db.insert_issue(run_id=state["run_id"], **issue_dict)

            logger.info(
                "Analysis complete: %d issues, %d suggested fixes, fixable=%s",
                len(issues_detected),
                len(suggested_fixes),
                analysis_result.get("is_fixable", False)
            )

        except Exception as e:
            state["error"] = f"Analysis failed: {e}"
            logger.exception(state["error"])
        return state



    def _fix_node(self, state: PipelineState) -> PipelineState:
        if state.get("error"):
            return state
        try:
            from app.agents.fixer import FixerAgent
            fixer = FixerAgent()
            suggested_fixes = state["analysis_result"].get("suggested_fixes", [])
            optimised = fixer.run(pipeline_yaml=state["pipeline_yaml"], suggested_fixes=suggested_fixes)
            if optimised and len(optimised) > 50:
                state["optimised_yaml"] = optimised
            else:
                state["error"] = "Fixer returned invalid output"

            db.insert_artifact(run_id=state["run_id"], stage="fixer",
                               content=state["optimised_yaml"], metadata={})
        except Exception as e:
            state["error"] = f"Fixer failed: {e}"
            logger.exception(state["error"])
        return state

    def _create_pr_node(self, state: PipelineState) -> PipelineState:
        if state.get("error") or not state.get("pr_create") or not state.get("optimised_yaml"):
            return state
        try:
            from app.agents.pr_handler import PRHandlerAgent
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return state
            pr_url = PRHandlerAgent(token).run(
                repo_url=state["repo_url"],
                optimised_yaml=state["optimised_yaml"],
                base_branch=state["branch"],
                pr_create=True
            )
            state["pr_url"] = pr_url if isinstance(pr_url, str) else None

            # Save PR info
            db.insert_pr(run_id=state["run_id"], branch_name=state["branch"], pr_url=state["pr_url"])
        except Exception as e:
            logger.warning("PR creation failed: %s", e)
        return state

    # ---------------------------
    # CONDITIONAL EDGE
    # ---------------------------
    def _should_create_pr(self, state: PipelineState) -> Literal["create_pr", "end"]:
        if state.get("error") or not state.get("pr_create") or not state.get("optimised_yaml"):
            return "end"
        return "create_pr"

    # ---------------------------
    # HELPER METHODS
    # ---------------------------
    def _log_summary(self, state: PipelineState) -> None:
        if state.get("error"):
            logger.error("Optimisation failed: %s", state["error"])
        else:
            logger.info("Optimisation completed successfully")
        issues = len(state.get("analysis_result", {}).get("issues_detected", []))
        logger.info("Analysis issues detected: %d", issues)
        yaml_len = len(state.get("optimised_yaml", ""))
        logger.info("Optimised YAML length: %d", yaml_len)
        pr_url = state.get("pr_url")
        if pr_url:
            logger.info("PR created: %s", pr_url)
