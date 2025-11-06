"""
Decision Agent - Makes decisions about tool execution.
"""

from typing import Dict, Any, Optional

from app.components.base_service import BaseService
from app.components.decide.prompt import DECISION_SYSTEM_PROMPT, build_decision_context
from app.utils.logger import get_logger
from app.llm.llm_client import LLMClient
from app.config import config
from app.constants import ACTION_RUN, ACTION_SKIP
from app.exceptions import DecisionError
from app.repository.pipeline_repository import PipelineRepository

logger = get_logger(__name__, "Decision")


class Decision(BaseService):
    """Decision service that decides whether to run or skip tools."""

    def __init__(self, model: str = None, temperature: float = None, max_tokens: int = None):
        super().__init__(agent_name="decide")
        
        cfg = config.get_decision_config()
        self.model = model or cfg["model"]
        self.temperature = temperature if temperature is not None else cfg["temperature"]
        self.max_tokens = max_tokens or cfg["max_tokens"]
        
        self.llm_client = LLMClient(model=self.model, temperature=self.temperature)
        self.repository = PipelineRepository()
        
        logger.debug(
            f"Initialised Decision agent: model={self.model}, temperature={self.temperature}, max_tokens={self.max_tokens}",
            correlation_id="INIT"
        )

    def run(self, state: Dict[str, Any], next_tool: str) -> Dict[str, str]:
        correlation_id = state.get("correlation_id")
        logger.debug(f"Making decision for: {next_tool}", correlation_id=correlation_id)
        
        try:
            context = build_decision_context(state, next_tool)
            raw_response = self.llm_client.chat_completion(
                system_prompt=DECISION_SYSTEM_PROMPT,
                user_prompt=context,
                max_tokens=self.max_tokens
            )
            decision = self.llm_client.parse_json_response(raw_response, correlation_id)
            
            action = decision.get("action", ACTION_RUN)
            reasoning = decision.get("reasoning", "No reasoning provided")
            
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
            
            return {"action": action, "reasoning": reasoning}
            
        except DecisionError as e:
            logger.error(f"Decision error for {next_tool}: {e}", correlation_id=correlation_id)
            raise
        except Exception as e:
            logger.error(f"Decision failed for {next_tool}: {e}", correlation_id=correlation_id)
            return {"action": ACTION_SKIP, "reasoning": f"Error making decision: {e}"}

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        next_tool = state.get("_current_tool")
        correlation_id = state.get("correlation_id")
        run_id = state.get("run_id")

        if not next_tool:
            logger.warning("No current tool specified for decision", correlation_id=correlation_id)
            state["next_action"] = ACTION_SKIP
            state["agent_reasoning"] = "No tool specified"
            return state
        
        decision = self.run(state, next_tool)
        state["next_action"] = decision["action"]
        state["agent_reasoning"] = decision["reasoning"]

        # Save decisions in DB
        if run_id:
            try:
                self.repository.save_decision(
                    run_id=run_id,
                    tool_name=next_tool,
                    action=decision["action"],
                    reasoning=decision["reasoning"],
                    correlation_id=correlation_id
                )
                logger.info(
                    f"Decision persisted: run_id={run_id}, tool={next_tool}, action={decision['action']}",
                    correlation_id=correlation_id
                )
            except Exception as e:
                logger.warning(f"Failed to save decision: {e}", correlation_id=correlation_id)
        else:
            logger.warning("run_id missing; decision not saved to DB", correlation_id=correlation_id)

        return state

    def _get_artifact_key(self) -> Optional[str]:
        return None
