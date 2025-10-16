"""
CI/CD Pipeline Optimisation Orchestrator - ReAct Pattern
Refactored to be truly agentic with reasoning and decision-making
"""

import os
import json
import logging
from typing import TypedDict, Optional, Any, Dict
from typing_extensions import Literal

from langgraph.graph import StateGraph, END
from openai import OpenAI

from app.db import db

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
    
    # ReAct pattern fields
    next_action: Optional[str]
    reasoning: Optional[str]
    iteration_count: int
    completed_steps: list[str]
    fix_verified: bool
    verification_attempts: int


# ---------------------------
# ORCHESTRATOR
# ---------------------------
class PipelineOrchestrator:
    """
    Orchestrates CI/CD optimisation using LangGraph with ReAct pattern.
    Agent reasons about what to do next based on current state.
    """

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0, verbose: bool = False):
        self.model_name = model_name
        self.temperature = temperature
        self.verbose = verbose
        
        # Initialize OpenAI client for reasoning
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)
        
        self.graph = self._build_graph()
        logger.info("Initialized LangGraph Pipeline with ReAct pattern: model=%s, verbose=%s", model_name, verbose)

    # ---------------------------
    # GRAPH SETUP - ReAct Pattern
    # ---------------------------
    def _build_graph(self):
        workflow = StateGraph(PipelineState)
        
        # Add reasoning node - the "brain" of the agent
        workflow.add_node("reason", self._reasoning_node)
        
        # Add action nodes
        workflow.add_node("ingest", self._ingest_node)
        workflow.add_node("validate", self._validate_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("fix", self._fix_node)
        workflow.add_node("verify_fix", self._verify_fix_node)
        workflow.add_node("create_pr", self._create_pr_node)

        # Start with reasoning
        workflow.set_entry_point("reason")
        
        # Agent decides what to do next after reasoning
        workflow.add_conditional_edges(
            "reason",
            self._decide_next_action,
            {
                "ingest": "ingest",
                "validate": "validate",
                "analyze": "analyze",
                "fix": "fix",
                "verify_fix": "verify_fix",
                "create_pr": "create_pr",
                "end": END
            }
        )
        
        # All action nodes return to reasoning for next decision
        for node in ["ingest", "validate", "analyze", "fix", "verify_fix", "create_pr"]:
            workflow.add_edge(node, "reason")
        
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
            "error": None,
            # ReAct fields
            "next_action": None,
            "reasoning": None,
            "iteration_count": 0,
            "completed_steps": [],
            "fix_verified": False,
            "verification_attempts": 0
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
                "error": final_state.get("error"),
                "reasoning_trace": final_state.get("reasoning")
            }
        except Exception as e:
            logger.exception("Graph execution failed")
            db.update_run_status(run_id=run_id, status="failed")
            return {"analysis": None, "optimised_yaml": None, "pr_url": None, "error": str(e)}

    # ---------------------------
    # REASONING NODE - Heart of ReAct
    # ---------------------------
    def _reasoning_node(self, state: PipelineState) -> PipelineState:
        """
        Agent reasons about current state and decides next action.
        This is the core of the ReAct pattern.
        """
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        
        # Safety check - prevent infinite loops
        if state["iteration_count"] > 20:
            logger.warning("Max iterations reached, ending workflow")
            state["next_action"] = "end"
            state["reasoning"] = "Maximum iteration limit reached"
            return state
        
        # Build context for the reasoning LLM
        prompt = self._build_reasoning_prompt(state)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a CI/CD optimization agent. Analyze the current state and decide the next action. Be strategic and efficient."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            decision = json.loads(response.choices[0].message.content)
            state["next_action"] = decision.get("action", "end")
            state["reasoning"] = decision.get("reasoning", "No reasoning provided")
            
            logger.info(
                "🧠 Agent Decision [Iteration %d]: %s | Reasoning: %s",
                state["iteration_count"],
                state["next_action"],
                state["reasoning"][:100]
            )
            
        except Exception as e:
            logger.error("Reasoning failed: %s", str(e))
            state["next_action"] = "end"
            state["error"] = f"Reasoning failed: {e}"
        
        return state

    def _build_reasoning_prompt(self, state: PipelineState) -> str:
        """Build comprehensive prompt for agent reasoning"""
        
        completed = ", ".join(state.get("completed_steps", [])) or "None"
        
        prompt = f"""
            You are orchestrating a CI/CD pipeline optimization workflow. Analyze the current state and decide the next action.

            **Current State:**
            - Iteration: {state.get('iteration_count', 0)}
            - Completed steps: {completed}
            - Repository: {state['repo_url']}
            - Pipeline path: {state['pipeline_path']}

            **Progress Status:**
            - Pipeline ingested: {bool(state.get('pipeline_yaml'))}
            - Validation complete: {bool(state.get('validation_result'))}
            - Analysis complete: {bool(state.get('analysis_result'))}
            - Fix applied: {bool(state.get('optimised_yaml'))}
            - Fix verified: {state.get('fix_verified', False)}
            - PR requested: {state.get('pr_create', False)}
            - PR created: {bool(state.get('pr_url'))}
            - Errors encountered: {state.get('error') or 'None'}

            **Analysis Results (if available):**
            {self._format_analysis_for_reasoning(state.get('analysis_result', {}))}

            **Validation Status:**
            {self._format_validation_for_reasoning(state.get('validation_result', {}))}

            **Available Actions:**
            1. "ingest" - Fetch pipeline YAML from repository
            2. "validate" - Validate pipeline syntax and structure
            3. "analyze" - Analyze pipeline for optimization opportunities
            4. "fix" - Apply optimizations to the pipeline
            5. "verify_fix" - Verify that the fix is valid and works
            6. "create_pr" - Create a pull request with optimized pipeline
            7. "end" - Complete the workflow

            **Decision Rules:**
            - Only proceed to next step if previous step succeeded
            - Always verify fixes before creating PR
            - If verification fails and attempts < 3, try fixing again
            - If error occurred, decide whether to retry or end
            - Create PR only if fix is verified and PR creation is requested

            **Your Task:**
            Decide the next action based on the current state. Be strategic and efficient.

            Return a JSON object with this exact structure:
            {{
                "action": "one of the available actions",
                "reasoning": "detailed explanation of why this action is needed next"
            }}
        """
        return prompt

    def _format_analysis_for_reasoning(self, analysis: Dict[str, Any]) -> str:
        """Format analysis results for reasoning prompt"""
        if not analysis:
            return "Not yet analyzed"
        
        issues = analysis.get("issues_detected", [])
        fixes = analysis.get("suggested_fixes", [])
        
        return f"""
            - Issues detected: {len(issues)}
            - Suggested fixes: {len(fixes)}
            - Is fixable: {analysis.get('is_fixable', False)}
            - Expected improvement: {analysis.get('expected_improvement', 'N/A')}
        """

    def _format_validation_for_reasoning(self, validation: Dict[str, Any]) -> str:
        """Format validation results for reasoning prompt"""
        if not validation:
            return "Not yet validated"
        
        is_valid = validation.get("valid", False)
        reason = validation.get("reason", "")
        
        return f"Valid: {is_valid}" + (f" | Reason: {reason}" if reason else "")

    # ---------------------------
    # CONDITIONAL EDGE - Route based on agent decision
    # ---------------------------
    def _decide_next_action(self, state: PipelineState) -> Literal["ingest", "validate", "analyze", "fix", "verify_fix", "create_pr", "end"]:
        """Route to next node based on agent's decision"""
        action = state.get("next_action", "end")
        
        # Validate action is allowed
        valid_actions = ["ingest", "validate", "analyze", "fix", "verify_fix", "create_pr", "end"]
        if action not in valid_actions:
            logger.warning("Invalid action '%s', defaulting to 'end'", action)
            return "end"
        
        return action

    # ---------------------------
    # ACTION NODES (Modified to track completion)
    # ---------------------------
    def _ingest_node(self, state: PipelineState) -> PipelineState:
        """Ingest pipeline YAML and build logs"""
        if state.get("error"):
            return state
        
        logger.info("📥 Executing: Ingest")
        
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
            else:
                state["completed_steps"].append("ingest")
                logger.info("✅ Ingest completed: %d bytes", len(pipeline_yaml))

            # Save artifact
            db.insert_artifact(
                run_id=state["run_id"], 
                stage="ingestor",
                content=pipeline_yaml, 
                metadata={"build_log": build_log}
            )
        except Exception as e:
            state["error"] = f"Ingest failed: {e}"
            logger.exception(state["error"])
        
        return state

    def _validate_node(self, state: PipelineState) -> PipelineState:
        """Validate pipeline YAML"""
        if state.get("error"):
            return state
        
        logger.info("✓ Executing: Validate")
        
        try:
            from app.agents.validator import ValidatorAgent
            result = ValidatorAgent().run(pipeline_yaml=state["pipeline_yaml"])
            state["validation_result"] = result if isinstance(result, dict) else {"valid": True}
            
            if not state["validation_result"].get("valid"):
                logger.warning("Validation failed: %s", state["validation_result"].get("reason"))
            else:
                state["completed_steps"].append("validate")
                logger.info("✅ Validation completed")

            # Save artifact
            db.insert_artifact(
                run_id=state["run_id"], 
                stage="validator",
                content=str(state["validation_result"]), 
                metadata={}
            )
        except Exception as e:
            state["error"] = f"Validation failed: {e}"
            logger.exception(state["error"])
        
        return state

    def _analyze_node(self, state: PipelineState) -> PipelineState:
        """Analyze pipeline for optimization opportunities"""
        if state.get("error"):
            return state
        
        logger.info("🔍 Executing: Analyze")
        
        try:
            from app.agents.analyser import AnalyserAgent
            analysis_result = AnalyserAgent().run(
                pipeline_yaml=state["pipeline_yaml"],
                build_log=state["build_log"]
            )

            # Ensure dict structure
            if not isinstance(analysis_result, dict):
                analysis_result = {
                    "issues_detected": [],
                    "suggested_fixes": [],
                    "expected_improvement": "",
                    "is_fixable": False
                }

            state["analysis_result"] = analysis_result
            state["completed_steps"].append("analyze")

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
                "✅ Analysis complete: %d issues, %d fixes, fixable=%s",
                len(issues_detected),
                len(suggested_fixes),
                analysis_result.get("is_fixable", False)
            )

        except Exception as e:
            state["error"] = f"Analysis failed: {e}"
            logger.exception(state["error"])
        
        return state

    def _fix_node(self, state: PipelineState) -> PipelineState:
        """Apply optimizations to pipeline"""
        if state.get("error"):
            return state
        
        logger.info("🔧 Executing: Fix")
        
        try:
            from app.agents.fixer import FixerAgent
            fixer = FixerAgent()
            suggested_fixes = state["analysis_result"].get("suggested_fixes", [])
            optimised = fixer.run(
                pipeline_yaml=state["pipeline_yaml"], 
                suggested_fixes=suggested_fixes
            )
            
            if optimised and len(optimised) > 50:
                state["optimised_yaml"] = optimised
                state["completed_steps"].append("fix")
                state["fix_verified"] = False  # Reset verification status
                logger.info("✅ Fix applied: %d bytes", len(optimised))
            else:
                state["error"] = "Fixer returned invalid output"

            db.insert_artifact(
                run_id=state["run_id"], 
                stage="fixer",
                content=state.get("optimised_yaml", ""), 
                metadata={}
            )
        except Exception as e:
            state["error"] = f"Fixer failed: {e}"
            logger.exception(state["error"])
        
        return state

    def _verify_fix_node(self, state: PipelineState) -> PipelineState:
        """Verify that the optimized pipeline is valid"""
        if state.get("error"):
            return state
        
        logger.info("🔍 Executing: Verify Fix")
        
        state["verification_attempts"] = state.get("verification_attempts", 0) + 1
        
        try:
            from app.agents.validator import ValidatorAgent
            import yaml
            
            # Parse YAML
            yaml.safe_load(state["optimised_yaml"])
            
            # Validate using validator agent
            validation = ValidatorAgent().run(state["optimised_yaml"])
            
            if validation.get("valid"):
                state["fix_verified"] = True
                state["completed_steps"].append("verify_fix")
                logger.info("✅ Fix verification passed")
            else:
                state["fix_verified"] = False
                error_msg = validation.get("reason", "Unknown validation error")
                logger.warning("❌ Fix verification failed: %s", error_msg)
                
                # If max attempts reached, set error
                if state["verification_attempts"] >= 3:
                    state["error"] = f"Fix verification failed after 3 attempts: {error_msg}"
                    
        except Exception as e:
            state["fix_verified"] = False
            logger.warning("❌ Fix verification failed with exception: %s", str(e))
            
            if state["verification_attempts"] >= 3:
                state["error"] = f"Fix verification failed: {e}"
        
        return state

    def _create_pr_node(self, state: PipelineState) -> PipelineState:
        """Create pull request with optimized pipeline"""
        if state.get("error") or not state.get("pr_create") or not state.get("optimised_yaml"):
            return state
        
        logger.info("🚀 Executing: Create PR")
        
        try:
            from app.agents.pr_handler import PRHandlerAgent
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                logger.warning("GITHUB_TOKEN not set, skipping PR creation")
                return state
            
            pr_url = PRHandlerAgent(token).run(
                repo_url=state["repo_url"],
                optimised_yaml=state["optimised_yaml"],
                base_branch=state["branch"],
                pr_create=True
            )
            state["pr_url"] = pr_url if isinstance(pr_url, str) else None
            
            if state["pr_url"]:
                state["completed_steps"].append("create_pr")
                logger.info("✅ PR created: %s", state["pr_url"])

            # Save PR info
            db.insert_pr(
                run_id=state["run_id"], 
                branch_name=state["branch"], 
                pr_url=state["pr_url"]
            )
        except Exception as e:
            logger.warning("PR creation failed: %s", e)
        
        return state

    # ---------------------------
    # HELPER METHODS
    # ---------------------------
    def _log_summary(self, state: PipelineState) -> None:
        """Log workflow summary"""
        logger.info("=" * 60)
        logger.info("WORKFLOW SUMMARY")
        logger.info("=" * 60)
        
        if state.get("error"):
            logger.error("❌ Optimisation failed: %s", state["error"])
        else:
            logger.info("✅ Optimisation completed successfully")
        
        logger.info("Total iterations: %d", state.get("iteration_count", 0))
        logger.info("Completed steps: %s", ", ".join(state.get("completed_steps", [])))
        
        issues = len(state.get("analysis_result", {}).get("issues_detected", []))
        logger.info("Issues detected: %d", issues)
        
        yaml_len = len(state.get("optimised_yaml", ""))
        logger.info("Optimised YAML length: %d bytes", yaml_len)
        
        if state.get("fix_verified"):
            logger.info("✅ Fix verified successfully")
        
        pr_url = state.get("pr_url")
        if pr_url:
            logger.info("🔗 PR created: %s", pr_url)
        
        logger.info("=" * 60)