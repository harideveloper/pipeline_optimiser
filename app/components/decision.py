# app/components/decision.py

"""
Decision Agent - Makes intelligent decisions about tool execution.
Uses LLM to decide whether to run or skip tools based on workflow state.
"""

import json
import os
from typing import Dict, Any, Optional
from openai import OpenAI

from app.components.base_service import BaseService
from app.orchestrator.prompts import DECISION_SYSTEM_PROMPT, build_decision_context
from app.utils.logger import get_logger

logger = get_logger(__name__, "Decision")


class Decision(BaseService):
    """
    LLM-powered agent that decides whether to run or skip tools.
    """

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.1):
        super().__init__(agent_name="decide")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature

    def run(self, state: Dict[str, Any], next_tool: str) -> Dict[str, str]:
        """ decision entrypoint."""
        correlation_id = state.get("correlation_id")

        logger.debug(f"Making decision for: {next_tool}", correlation_id=correlation_id)
        context = build_decision_context(state, next_tool)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": DECISION_SYSTEM_PROMPT},
                    {"role": "user", "content": context},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )

            decision = json.loads(response.choices[0].message.content)
            action = decision.get("action", "run")
            reasoning = decision.get("reasoning", "")

            logger.debug(f"Decision: {action} {next_tool} | Reasoning: {reasoning}", correlation_id=correlation_id)
            return {"action": action, "reasoning": reasoning}

        except Exception as e:
            logger.error(f"Decision failed: {e}", correlation_id=correlation_id)
            return {"action": "skip", "reasoning": f"Error making decision: {e}"}

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized executor hook (optional, for LangGraph node use)."""
        next_tool = state.get("_current_tool")
        decision = self.run(state, next_tool)
        state["next_action"] = decision["action"]
        state["agent_reasoning"] = decision["reasoning"]
        return state

    def _get_artifact_key(self) -> Optional[str]:
        return None
