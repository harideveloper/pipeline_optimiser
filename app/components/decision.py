"""
Decision Agent - Makes intelligent decisions about tool execution.
Uses LLM to decide whether to run or skip tools based on workflow state.
"""

from typing import Dict, Any, Optional

from app.components.base_service import BaseService
from app.orchestrator.prompts import DECISION_SYSTEM_PROMPT, build_decision_context
from app.utils.logger import get_logger
from app.utils.llm_client import LLMClient
from app.config import config
from app.constants import ACTION_RUN, ACTION_SKIP
from app.exceptions import DecisionError

logger = get_logger(__name__, "Decision")


class Decision(BaseService):
    """
    decison service that decides whether to run or skip tools. Uses workflow state and tool context 
    to make intelligent decisions about which tools should be executed or skipped.
    """

    def __init__(self, model: str = None, temperature: float = None):
        """
        Initialize Decision agent with LLM configuration.
        
        Args:
            model: LLM model name (defaults to config.MODEL_NAME)
            temperature: LLM temperature (defaults to 0.1 for deterministic decisions)
        """
        super().__init__(agent_name="decide")
        
        self.model = model or config.MODEL_NAME
        self.temperature = temperature if temperature is not None else 0.1
        
        # Use shared LLM client
        self.llm_client = LLMClient(
            model=self.model,
            temperature=self.temperature
        )
        
        logger.debug(
            f"Initialised Decision agent: model={self.model}, temperature={self.temperature}",
            correlation_id="INIT"
        )

    def run(self, state: Dict[str, Any], next_tool: str) -> Dict[str, str]:
        """
        Make decision about whether to run or skip a tool.
        
        Args:
            state: Current workflow state
            next_tool: Name of the tool to decide about
            
        Returns:
            Dictionary with 'action' (run/skip) and 'reasoning' (explanation)
        """
        correlation_id = state.get("correlation_id")
        
        logger.debug(f"Making decision for: {next_tool}", correlation_id=correlation_id)
        
        try:
            # Build decision context from state
            context = build_decision_context(state, next_tool)
            
            # Get LLM decision
            raw_response = self.llm_client.chat_completion(
                system_prompt=DECISION_SYSTEM_PROMPT,
                user_prompt=context,
                response_format={"type": "json_object"},
                correlation_id=correlation_id
            )
            
            # Parse decision
            decision = self.llm_client.parse_json_response(raw_response, correlation_id)
            
            # Validate and extract decision
            action = decision.get("action", ACTION_RUN)
            reasoning = decision.get("reasoning", "No reasoning provided")
            
            # Validate action is valid
            if action not in [ACTION_RUN, ACTION_SKIP]:
                logger.warning(
                    f"Invalid action '{action}' received, defaulting to '{ACTION_RUN}'",
                    correlation_id=correlation_id
                )
                action = ACTION_RUN
            
            logger.debug(
                f"Decision: {action} {next_tool} | Reasoning: {reasoning}",
                correlation_id=correlation_id
            )
            
            return {
                "action": action,
                "reasoning": reasoning
            }
            
        except Exception as e:
            logger.error(f"Decision failed: {e}", correlation_id=correlation_id)
            # Default to skip on error to be safe
            return {
                "action": ACTION_SKIP,
                "reasoning": f"Error making decision: {e}"
            }

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute decision within workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with next_action and agent_reasoning
        """
        next_tool = state.get("_current_tool")
        
        if not next_tool:
            logger.warning("No current tool specified for decision", correlation_id=state.get("correlation_id"))
            state["next_action"] = ACTION_SKIP
            state["agent_reasoning"] = "No tool specified"
            return state
        
        decision = self.run(state, next_tool)
        
        state["next_action"] = decision["action"]
        state["agent_reasoning"] = decision["reasoning"]
        
        return state

    def _get_artifact_key(self) -> Optional[str]:
        """
        Decision agent doesn't produce artifacts.
        
        Returns:
            None
        """
        return None