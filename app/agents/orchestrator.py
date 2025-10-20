"""
CI/CD Pipeline Optimisation Orchestrator - Hybrid Plan-Based Pattern
Profile-based planning with intelligent execution
"""

import os
import json
from typing import TypedDict, Optional, Any, Dict, List, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from openai import OpenAI

from app.db import db
from app.agents.components.helper import generate_correlation_id
from app.utils.logger import get_logger
from app.agents.components.classifier import ClassifierAgent
from app.agents.components.ingestor import IngestorAgent
from app.agents.components.validator import ValidatorAgent
from app.agents.components.analyser import AnalyserAgent
from app.agents.components.fixer import FixerAgent
from app.agents.components.resolver import ResolverAgent
from app.agents.components.risk_assessor import RiskAssessorAgent
from app.agents.components.security_scanner import SecurityScannerAgent
from app.agents.components.reviewer import ReviewerAgent

logger = get_logger(__name__, "PipelineOrchestrator")


class PipelineState(TypedDict):
    """State for hybrid plan-based workflow"""
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


class PipelineOrchestrator:
    """
    Hybrid plan-based orchestrator
    
    Features:
    - Profile-based planning (HIGH/MEDIUM/LOW risk)
    - Ordered tool execution
    - Intelligent skipping via LLM
    - Early termination
    """

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.1):
        self.model_name = model_name
        self.temperature = temperature
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)
        
        self.classifier = ClassifierAgent()
        
        # Tool registry
        self.tools = {
            "ingest": IngestorAgent(),
            "validate": ValidatorAgent(),
            "analyse": AnalyserAgent(),
            "risk_assessment": RiskAssessorAgent(),
            "security_scan": SecurityScannerAgent(),
            "fix": FixerAgent(),
            "review": ReviewerAgent(),
            "resolve": ResolverAgent(),
        }
        
        # Build LangGraph
        self.graph = self._build_graph()
        
        logger.debug(f"Initialised Orchestrator: model={model_name}", correlation_id="INIT")

    def _build_graph(self) -> StateGraph:
        """
        pipeline optimiser langGraph workflow
        """
        workflow = StateGraph(PipelineState)
        
        workflow.add_node("classify", self._classify_workflow)
        workflow.add_node("decide", self._agent_decision)
        workflow.add_node("execute", self._execute_tool)
        workflow.set_entry_point("classify")
        workflow.add_edge("classify", "decide")
        workflow.add_conditional_edges(
            "decide",
            self._should_continue,
            {
                "continue": "execute",
                "end": END
            }
        )
        
        # Loop back
        workflow.add_edge("execute", "decide")
        
        return workflow.compile()

    def run(
        self,
        repo_url: str,
        pipeline_path: str,
        build_log_path: Optional[str] = None,
        branch: str = "main",
        pr_create: bool = False
    ) -> Dict[str, Any]:
        """Run the pipeline optimisation workflow"""
        
        # Generate unique correlation id
        correlation_id = generate_correlation_id()

        repo_id = db.get_or_create_repo(repo_url=repo_url, default_branch=branch)
        run_id = db.create_run(repo_id=repo_id, commit_sha=None, trigger_source="API")
        
        logger.info(f"Starting pipeline optimisation (run_id={run_id}, repo={repo_url})", correlation_id=correlation_id)
        
        # Initialisating state
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
   
            start_time = datetime.now()
            final_state = self.graph.invoke(initial_state)
            duration = (datetime.now() - start_time).total_seconds()
            self._log_summary(final_state, duration)
            db.update_run_status(run_id=run_id, status="completed")
            
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
            db.update_run_status(run_id=run_id, status="failed")
            return {"success": False, "correlation_id": correlation_id, "error": str(e)}

 
    # GRAPH NODES
    def _classify_workflow(self, state: PipelineState) -> PipelineState:
        """
        Node 1: Classify workflow and generate plan
        """
        cid = state["correlation_id"]
        ingest_agent = self.tools["ingest"]
        state.update(ingest_agent.execute_node(state))
        if state.get("error"):
            logger.error("Ingestion failed, cannot proceed with classification", correlation_id=cid)
            return state
        state = self.classifier.execute_node(state)
        logger.info(
            f"Generated Plan ({len(state['plan'])} steps): {' → '.join(state['plan'])}",
            correlation_id=cid
        )
        return state

    def _agent_decision(self, state: PipelineState) -> PipelineState:
        """
        Node 2: Agent decides whether to run/skip next tool in plan
        """
        cid = state["correlation_id"]
        logger.debug("Decision Node: Agent deciding next action", correlation_id=cid)
        if state.get("error"):
            logger.debug("Error detected, stopping workflow", correlation_id=cid)
            state["next_action"] = "complete"
            state["agent_reasoning"] = f"Workflow stopped due to error: {state['error']}"
            return state
        if state["plan_index"] >= len(state["plan"]):
            logger.info("Agent plan loop completed, No more Tools to be executed", correlation_id=cid)
            state["next_action"] = "complete"
            state["agent_reasoning"] = "All planned tools executed"
            return state
        next_tool = state["plan"][state["plan_index"]]
        logger.debug(f"Next in plan: {next_tool} (index {state['plan_index']}/{len(state['plan'])-1})", correlation_id=cid)
        
        # Build LLM context
        context = self._build_agent_context(state, next_tool)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": context}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            decision = json.loads(response.choices[0].message.content)
            logger.info(f"decision: {decision}")
            
            state["next_action"] = decision.get("action", "run")
            state["agent_reasoning"] = decision.get("reasoning", "")
            state["_current_tool"] = next_tool
            
            logger.info(f"Decision: {state['next_action']} {next_tool} | Reasoning: {state['agent_reasoning']}", correlation_id=cid)
            
        except Exception as e:
            logger.error(f"Agent decision failed: {e}", correlation_id=cid)
            state["next_action"] = "skip"
            state["agent_reasoning"] = f"Error: {e}"
        
        return state

    def _execute_tool(self, state: PipelineState) -> PipelineState:
        """
        Node 3: Execute or skip the current tool based on agent decision
        """
        cid = state["correlation_id"]
        tool_name = state["_current_tool"]
        next_action = state["next_action"]
        
        if next_action == "skip":
            logger.info(f"Skipping: {tool_name} | Reason: {state['agent_reasoning']}", correlation_id=cid)
            state["execution_log"].append(f"{tool_name}: skipped")
            
        else:
            logger.debug(f"Executing: {tool_name}", correlation_id=cid)
            try:
                agent = self.tools[tool_name]
                if tool_name in ["ingest", "analyse", "risk_assessment", "security_scan", "fix"]:
                    result = agent.execute_node(state)
                else:
                    result = agent._execute(state)
                
                state.update(result)
                if tool_name not in state["completed_tools"]:
                    state["completed_tools"].append(tool_name)
                log_entry = f"{tool_name}: completed"
                if tool_name == "analyse":
                    issues = state.get("analysis_result", {}).get("issues_detected", [])
                    log_entry += f" ({len(issues)} issues found)"
                elif tool_name == "resolve" and state.get("pr_url"):
                    log_entry += f" (PR: {state['pr_url']})"
                state["execution_log"].append(log_entry)
                
            except Exception as e:
                logger.error(f"Tool execution failed: {tool_name} - {e}", correlation_id=cid)
                state["execution_log"].append(f"{tool_name}: FAILED - {e}")
        
        state["plan_index"] += 1
        return state


    # ROUTING LOGIC
    def _should_continue(self, state: PipelineState) -> Literal["continue", "end"]:
        """
        Simplified router: only 2 paths instead of 3
        
        - "continue": Execute or skip the next tool
        - "end": Workflow complete
        """
        if state.get("next_action") == "complete":
            return "end"
        return "continue"


    # PLAN GENERATION
    def _generate_plan(self, risk_level: str, pr_create: bool) -> List[str]:
        """
        Generate ordered tool plan based on risk level
        """
        base_plan = ["validate", "analyse", "fix"]
        
        if risk_level == "HIGH":
            plan = base_plan + ["risk_assessment", "security_scan", "review"]
        elif risk_level == "MEDIUM":
            plan = base_plan + ["security_scan", "review"]
        else:  # LOW
            plan = base_plan + ["review"]
        if pr_create:
            plan.append("resolve")
        
        return plan

    # AGENT PROMPTING
    def _get_system_prompt(self) -> str:
        """System prompt defining agent behavior"""
        return """You are an expert CI/CD pipeline optimization agent.

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

    def _build_agent_context(self, state: PipelineState, next_tool: str) -> str:
        """Build context for agent decision"""
        
        completed = state["completed_tools"]
        analysis_summary = ""
        
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


    # LOGGING
    def _log_summary(self, state: PipelineState, duration: float) -> None:
        """Log execution summary"""
        cid = state["correlation_id"]
        logger.info(
            "Workflow Type: %s | Risk Level: %s | Duration: %.2fs" % (
                state["workflow_type"],
                state["risk_level"],
                duration
            ),
            correlation_id=cid
        )
        logger.info(
            "Planned Steps (%d): %s" % (len(state["plan"]), " | ".join(state["plan"])),
            correlation_id=cid
        )
        logger.info(
            "Executed Steps (%d) [includes preparatory steps]: %s" % (
                len(state["completed_tools"]),
                " | ".join(state["completed_tools"])
            ),
            correlation_id=cid
        )