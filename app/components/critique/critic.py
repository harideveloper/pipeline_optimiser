"""
Critic Agent that evaluates confidence in applied fixes and overall merge readiness.
"""

import json
from typing import Dict, Any, Optional, List

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.llm.llm_client import LLMClient
from app.config import config
from app.exceptions import CriticError
from app.components.critique.prompt import (
    CRITIC_SYSTEM_PROMPT,
    CRITIC_EXECUTION_PROMPT
)

logger = get_logger(__name__, "Critic")


class Critic(BaseService):
    """Critic Agent that evaluates confidence in applied fixes and overall merge readiness."""

    def __init__(self, model: str = None, temperature: float = None, max_tokens: int = None):
        super().__init__(agent_name="critic")
        
        cfg = config.get_critic_config()
        self.model = model or cfg["model"]
        self.temperature = temperature if temperature is not None else cfg["temperature"]
        self.max_tokens = max_tokens or cfg["max_tokens"]
        self.default_quality_score = cfg["default_quality_score"]
        self.regression_penalty = cfg["regression_penalty"]
        self.unresolved_penalty = cfg["unresolved_penalty"]
        
        self.llm_client = LLMClient(model=self.model, temperature=self.temperature)
        
        logger.debug(f"Initialized Critic with model={self.model}", correlation_id="INIT")

    def run(
        self,
        original_yaml: str,
        optimised_yaml: str,
        issues_detected: List[Dict[str, Any]],
        applied_fixes: List[Dict[str, Any]],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform llm based confidence evaluation"""
        if not optimised_yaml:
            raise CriticError("optimised_yaml must be a non-empty string")

        user_prompt = CRITIC_EXECUTION_PROMPT.format(
            original_yaml=original_yaml,
            optimised_yaml=optimised_yaml,
            issues_detected=json.dumps(issues_detected, indent=2),
            applied_fixes=json.dumps(applied_fixes, indent=2)
        )

        try:
            raw_output = self.llm_client.chat_completion(
                system_prompt=CRITIC_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=self.max_tokens
            )
            
            review = self.llm_client.parse_json_response(raw_output, correlation_id)
            review = self._compute_confidence_score(review)

            logger.info(
                f"Critic Review complete -> fix_confidence={review.get('fix_confidence')} "
                f"merge_confidence={review.get('merge_confidence')}",
                correlation_id=correlation_id
            )

            return review

        except Exception as e:
            logger.exception(
                f"Critic review failed unexpectedly: {str(e)[:200]}",
                correlation_id=correlation_id
            )
            raise CriticError(f"Critic review failed: {e}") from e

    def _compute_confidence_score(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """Compute heuristic confidence scores from Critic review output."""
        fix_quality = review.get("quality_score", self.default_quality_score)
        review["fix_confidence"] = max(0.0, min(fix_quality / 10, 1.0))

        regressions = len(review.get("regressions", []))
        unresolved = len(review.get("unresolved_issues", []))
        merge_score = (
            review["fix_confidence"] 
            - self.regression_penalty * regressions 
            - self.unresolved_penalty * unresolved
        )
        review["merge_confidence"] = max(0.0, min(merge_score, 1.0))

        return review

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Critic review as a non-blocking stage."""
        correlation_id = state.get("correlation_id")
        try:
            result = self.run(
                original_yaml=state.get("pipeline_yaml", ""),
                optimised_yaml=state.get("optimised_yaml", ""),
                issues_detected=state.get("analysis_result", {}).get("issues_detected", []),
                applied_fixes=state.get("analysis_result", {}).get("suggested_fixes", []),
                correlation_id=correlation_id
            )
            state["critic_review"] = result
            
            # Save to database
            try:
                self.repository.save_review(
                    run_id=state["run_id"],
                    review_type="critic",
                    review_data=result,
                    correlation_id=correlation_id
                )
                logger.debug("Critic review saved to database", correlation_id=correlation_id)
            except Exception as e:
                logger.warning(
                    f"Failed to save critic review to database: {str(e)[:200]}",
                    correlation_id=correlation_id
                )
                
        except Exception as e:
            state["critic_review"] = {"error": str(e)}
            logger.error(
                f"Critic review failed: {str(e)[:200]}",
                correlation_id=correlation_id
            )
        return state

    def _get_artifact_key(self) -> Optional[str]:
        return "critic_review"