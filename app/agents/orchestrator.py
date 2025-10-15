# """
# CI/CD Pipeline Optimization Orchestrator - LangGraph Version
# Complete working version with correct agent method calls.
# """

# import os
# import logging
# from typing import TypedDict, Optional, Any, Dict
# from typing_extensions import Literal

# from langgraph.graph import StateGraph, END
# from langchain_openai import ChatOpenAI

# logger = logging.getLogger(__name__)


# class PipelineState(TypedDict):
#     """State that flows through the graph."""
#     # Input parameters
#     repo_url: str
#     pipeline_path: str
#     build_log_path: Optional[str]
#     branch: str
#     pr_create: bool

#     # context data
#     pipeline_yaml: str
#     build_log: str
#     validation_result: Dict[str, Any]
#     analysis_result: Dict[str, Any]

#     # Output
#     optimized_yaml: str
#     pr_url: Optional[str]
#     error: Optional[str]


# class PipelineOrchestrator:
#     """
#     Orchestrates CI/CD optimization using LangGraph.

#     Replaces the old LangChain agent-based approach with explicit
#     state management to eliminate data passing issues.
#     """

#     def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0, verbose: bool = False):
#         """
#         Initialize the LangGraph pipeline.

#         Args:
#             model_name: OpenAI model to use (for future use)
#             temperature: Model temperature (for future use)
#             verbose: Enable verbose logging
#         """
#         self.model_name = model_name
#         self.temperature = temperature
#         self.verbose = verbose
#         self.graph = self._build_graph()

#         logger.info("Initialized LangGraph Pipeline: model=%s, verbose=%s", model_name, verbose)

#     def _build_graph(self):
#         """Build the workflow graph with all nodes and edges."""
#         workflow = StateGraph(PipelineState)

#         # Add nodes
#         workflow.add_node("ingest", self._ingest_node)
#         workflow.add_node("validate", self._validate_node)
#         workflow.add_node("analyze", self._analyze_node)
#         workflow.add_node("fix", self._fix_node)
#         workflow.add_node("create_pr", self._create_pr_node)

#         # Define edges
#         workflow.set_entry_point("ingest")
#         workflow.add_edge("ingest", "validate")
#         workflow.add_edge("validate", "analyze")
#         workflow.add_edge("analyze", "fix")

#         # Conditional edge: only create PR if requested and no errors
#         workflow.add_conditional_edges(
#             "fix",
#             self._should_create_pr,
#             {
#                 "create_pr": "create_pr",
#                 "end": END
#             }
#         )
#         workflow.add_edge("create_pr", END)

#         return workflow.compile()

#     def run(
#         self,
#         repo_url: str,
#         pipeline_path: str,
#         build_log_path: Optional[str] = None,
#         branch: str = "main",
#         pr_create: bool = False
#     ) -> Dict[str, Any]:
#         """
#         Execute the pipeline optimization workflow.

#         Args:
#             repo_url: GitHub repository URL
#             pipeline_path: Path to pipeline file in repo
#             build_log_path: Optional path to build log file
#             branch: Git branch to use
#             pr_create: Whether to create a pull request

#         Returns:
#             Dict with keys: analysis, optimized_yaml, pr_url, error
#         """
#         logger.info("Starting LangGraph optimization: repo=%s, path=%s, branch=%s", repo_url, pipeline_path, branch)

#         initial_state: PipelineState = {
#             "repo_url": repo_url,
#             "pipeline_path": pipeline_path,
#             "build_log_path": build_log_path,
#             "branch": branch,
#             "pr_create": pr_create,
#             "pipeline_yaml": "",
#             "build_log": "",
#             "validation_result": {},
#             "analysis_result": {},
#             "optimized_yaml": "",
#             "pr_url": None,
#             "error": None
#         }

#         try:
#             logger.info("Executing LangGraph workflow")
#             final_state = self.graph.invoke(initial_state)

#             # Log final summary
#             self._log_summary(final_state)

#             return {
#                 "analysis": final_state.get("analysis_result"),
#                 "optimized_yaml": final_state.get("optimized_yaml"),
#                 "pr_url": final_state.get("pr_url"),
#                 "error": final_state.get("error")
#             }

#         except Exception as e:
#             logger.exception("Graph execution failed: %s", str(e))
#             return {
#                 "error": str(e),
#                 "analysis": None,
#                 "optimized_yaml": None,
#                 "pr_url": None
#             }

#     # ========================================================================
#     # GRAPH NODES
#     # ========================================================================

#     def _ingest_node(self, state: PipelineState) -> PipelineState:
#         """
#         Node: Ingest pipeline and build log from repository.

#         Calls IngestorAgent.run() which returns a tuple: (pipeline_yaml, build_log)
#         """
#         logger.info("Node: ingest - loading pipeline from repository")

#         try:
#             from app.agents.ingestor import IngestorAgent
#             ingestor = IngestorAgent()

#             pipeline_yaml, build_log = ingestor.run(
#                 repo_url=state["repo_url"],
#                 pipeline_path_in_repo=state["pipeline_path"],
#                 build_log_path_in_repo=state["build_log_path"],
#                 branch=state["branch"]
#             )

#             state["pipeline_yaml"] = pipeline_yaml or ""
#             state["build_log"] = build_log or ""

#             yaml_len = len(state["pipeline_yaml"])
#             log_len = len(state["build_log"])

#             if not state["pipeline_yaml"]:
#                 state["error"] = "Ingestor returned empty pipeline_yaml"
#                 logger.error("Ingest failed: empty pipeline_yaml")
#             else:
#                 logger.info("Ingest complete: yaml_length=%d, log_length=%d", yaml_len, log_len)

#         except Exception as e:
#             error_msg = f"Ingest failed: {str(e)}"
#             logger.exception(error_msg)
#             state["error"] = error_msg

#         return state

#     def _validate_node(self, state: PipelineState) -> PipelineState:
#         """
#         Node: Validate pipeline YAML syntax and structure.

#         Calls ValidatorAgent.run() with the pipeline YAML.
#         """
#         logger.info("Node: validate - checking pipeline syntax")

#         if state.get("error"):
#             logger.warning("Skipping validation due to previous error")
#             return state

#         try:
#             from app.agents.validator import ValidatorAgent
#             validator = ValidatorAgent()

#             result = validator.run(pipeline_yaml=state["pipeline_yaml"])

#             if isinstance(result, dict):
#                 state["validation_result"] = result
#                 is_valid = result.get("valid", False)
#             elif isinstance(result, bool):
#                 state["validation_result"] = {"valid": result}
#                 is_valid = result
#             else:
#                 state["validation_result"] = {"result": result, "valid": True}
#                 is_valid = True

#             if is_valid:
#                 logger.info("Validate: pipeline is valid")
#             else:
#                 error = state["validation_result"].get("error", "Unknown validation error")
#                 logger.warning("Validate: %s", error)

#         except Exception as e:
#             error_msg = f"Validation failed: {str(e)}"
#             logger.exception(error_msg)
#             state["error"] = error_msg

#         return state

#     def _analyze_node(self, state: PipelineState) -> PipelineState:
#         """
#         Node: Analyze pipeline for optimization opportunities.

#         Calls AnalyzerAgent.run() with pipeline YAML and build log.
#         """
#         logger.info("Node: analyze - identifying optimization opportunities")

#         if state.get("error"):
#             logger.warning("Skipping analysis due to previous error")
#             return state

#         try:
#             from app.agents.optimiser import AnalyzerAgent
#             analyzer = AnalyzerAgent()

#             result = analyzer.run(
#                 pipeline_yaml=state["pipeline_yaml"],
#                 build_log=state["build_log"]
#             )

#             if isinstance(result, dict):
#                 state["analysis_result"] = result
#             else:
#                 state["analysis_result"] = {
#                     "raw_result": result,
#                     "issues_detected": [],
#                     "suggested_fixes": []
#                 }

#             issues_count = len(state["analysis_result"].get("issues_detected", []))
#             fixes_count = len(state["analysis_result"].get("suggested_fixes", []))

#             logger.info("Analyze complete: issues=%d, suggested_fixes=%d", issues_count, fixes_count)

#             if self.verbose and issues_count > 0:
#                 for i, issue in enumerate(state["analysis_result"].get("issues_detected", []), 1):
#                     logger.debug("Issue %d: %s", i, issue)

#         except Exception as e:
#             error_msg = f"Analysis failed: {str(e)}"
#             logger.exception(error_msg)
#             state["error"] = error_msg

#         return state

#     def _fix_node(self, state: PipelineState) -> PipelineState:
#         """
#         Node: Generate optimized pipeline YAML.

#         Calls FixerAgent.run() with the original YAML and suggested fixes.
#         State management ensures the full YAML is always available.
#         """
#         logger.info("Node: fix - generating optimized pipeline")

#         if state.get("error"):
#             logger.warning("Skipping fix due to previous error")
#             return state

#         try:
#             from app.agents.fixer import FixerAgent
#             fixer = FixerAgent()

#             pipeline_yaml = state["pipeline_yaml"]
#             suggested_fixes = state["analysis_result"].get("suggested_fixes", [])

#             logger.info("Fix input: yaml_length=%d, suggested_fixes=%d", len(pipeline_yaml), len(suggested_fixes))

#             optimized = fixer.run(
#                 pipeline_yaml=pipeline_yaml,
#                 suggested_fixes=suggested_fixes
#             )

#             if optimized and len(optimized) > 50:
#                 state["optimized_yaml"] = optimized
#                 logger.info("Fix complete: generated optimized_yaml_length=%d", len(optimized))
#             else:
#                 error_msg = f"Fixer returned invalid output: length={len(optimized) if optimized else 0}"
#                 logger.error(error_msg)
#                 state["error"] = error_msg

#         except Exception as e:
#             error_msg = f"Fixer failed: {str(e)}"
#             logger.exception(error_msg)
#             state["error"] = error_msg

#         return state

#     def _create_pr_node(self, state: PipelineState) -> PipelineState:
#         """
#         Node: Create GitHub pull request with optimized pipeline.

#         Calls PRHandlerAgent.run() with the optimized YAML.
#         """
#         logger.info("Node: create_pr - creating pull request")

#         if state.get("error"):
#             logger.warning("Skipping PR creation due to previous error")
#             return state

#         try:
#             token = os.getenv("GITHUB_TOKEN")
#             if not token:
#                 logger.warning("No GITHUB_TOKEN found - skipping PR creation")
#                 return state

#             from app.agents.pr_handler import PRHandlerAgent
#             pr_handler = PRHandlerAgent(token)

#             optimized_yaml = state["optimized_yaml"]

#             logger.info("CreatePR input: optimized_yaml_length=%d", len(optimized_yaml or ""))

#             result = pr_handler.run(
#                 repo_url=state["repo_url"],
#                 optimized_yaml=optimized_yaml,
#                 base_branch=state["branch"],
#                 pr_create=True
#             )

#             if isinstance(result, str):
#                 pr_url = result
#             elif isinstance(result, dict):
#                 pr_url = result.get("pr_url")
#             else:
#                 pr_url = None

#             if pr_url:
#                 state["pr_url"] = pr_url
#                 logger.info("CreatePR succeeded: %s", pr_url)
#             else:
#                 logger.warning("PR creation returned no URL")

#         except Exception as e:
#             logger.exception("PR creation failed: %s", str(e))
#             # PR failure should not mark whole workflow as failed

#         return state

#     # ========================================================================
#     # CONDITIONAL EDGES
#     # ========================================================================

#     def _should_create_pr(self, state: PipelineState) -> Literal["create_pr", "end"]:
#         """
#         Decide whether to create a PR based on state.
#         """
#         if state.get("error"):
#             logger.debug("Skipping PR creation: error present")
#             return "end"

#         if not state.get("pr_create"):
#             logger.debug("Skipping PR creation: not requested")
#             return "end"

#         if not state.get("optimized_yaml"):
#             logger.debug("Skipping PR creation: no optimized YAML")
#             return "end"

#         logger.debug("Proceeding to PR creation")
#         return "create_pr"

#     # ========================================================================
#     # HELPER METHODS
#     # ========================================================================

#     def _log_summary(self, final_state: PipelineState) -> None:
#         """Log a summary of the execution results."""
#         logger.info("Workflow summary")
#         if final_state.get("error"):
#             logger.error("Optimization failed: %s", final_state["error"])
#         else:
#             logger.info("Optimization completed successfully")

#         analysis = final_state.get("analysis_result", {})
#         issues = len(analysis.get("issues_detected", []))
#         logger.info("Analysis: issues_detected=%d", issues)

#         optimized = final_state.get("optimized_yaml", "")
#         if optimized:
#             logger.info("Optimized YAML length=%d", len(optimized))
#         else:
#             logger.warning("No optimized YAML generated")

#         pr_url = final_state.get("pr_url")
#         if pr_url:
#             logger.info("PR created: %s", pr_url)
#         elif final_state.get("pr_create"):
#             logger.warning("PR creation was requested but not completed")


"""
CI/CD Pipeline Optimisation Orchestrator - LangGraph Version
Refactored for clarity, maintainability, and coding standards.
"""

import os
import logging
from typing import TypedDict, Optional, Any, Dict
from typing_extensions import Literal

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class PipelineState(TypedDict):
    """State that flows through the pipeline workflow."""
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
    error: Optional[str]


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

    def run(
        self,
        repo_url: str,
        pipeline_path: str,
        build_log_path: Optional[str] = None,
        branch: str = "main",
        pr_create: bool = False
    ) -> Dict[str, Any]:
        logger.info("Starting optimisation: repo=%s, path=%s, branch=%s", repo_url, pipeline_path, branch)

        state: PipelineState = {
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
            "error": None
        }

        try:
            final_state = self.graph.invoke(state)
            self._log_summary(final_state)
            return {
                "analysis": final_state.get("analysis_result"),
                "optimised_yaml": final_state.get("optimised_yaml"),
                "pr_url": final_state.get("pr_url"),
                "error": final_state.get("error")
            }
        except Exception as e:
            logger.exception("Graph execution failed")
            return {"analysis": None, "optimised_yaml": None, "pr_url": None, "error": str(e)}

    # ---------------------------
    # GRAPH NODE METHODS
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
            if isinstance(result, dict):
                state["validation_result"] = result
            elif isinstance(result, bool):
                state["validation_result"] = {"valid": result}
            else:
                state["validation_result"] = {"valid": True, "result": result}
        except Exception as e:
            state["error"] = f"Validation failed: {e}"
            logger.exception(state["error"])
        return state

    def _analyze_node(self, state: PipelineState) -> PipelineState:
        if state.get("error"):
            return state
        try:
            from app.agents.analyser import AnalyserAgent
            result = AnalyserAgent().run(
                pipeline_yaml=state["pipeline_yaml"],
                build_log=state["build_log"]
            )
            state["analysis_result"] = result if isinstance(result, dict) else {"raw_result": result, "issues_detected": [], "suggested_fixes": []}
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
        except Exception as e:
            state["error"] = f"Fixer failed: {e}"
            logger.exception(state["error"])
        return state

    def _create_pr_node(self, state: PipelineState) -> PipelineState:
        if state.get("error") or not state.get("pr_create") or not state.get("optimised_yaml"):
            return state
        try:
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return state
            from app.agents.pr_handler import PRHandlerAgent
            pr_url = PRHandlerAgent(token).run(
                repo_url=state["repo_url"],
                optimised_yaml=state["optimised_yaml"],
                base_branch=state["branch"],
                pr_create=True
            )
            state["pr_url"] = pr_url if isinstance(pr_url, str) else pr_url.get("pr_url") if isinstance(pr_url, dict) else None
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
