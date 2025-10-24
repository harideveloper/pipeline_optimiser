import os
import json
from typing import Dict, Any, Optional, List
import anthropic

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.exceptions import CriticError
from app.components.critique.prompt import (
    CRITIC_SYSTEM_PROMPT,
    CRITIC_EXECUTION_PROMPT
)

logger = get_logger(__name__, "Critic")


class Critic(BaseService):
    """
    Critic Agent that evaluates confidence in applied fixes and overall merge readiness.
    """

    def __init__(
        self,
        model: str = None,
        temperature: float = 0,
        seed: int = 42,
        max_tokens: int = 4096
    ):
        super().__init__(agent_name="critic")
        self.model = model or "claude-sonnet-4-20250514"
        self.temperature = temperature
        self.seed = seed
        self.max_tokens = max_tokens

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=api_key)
        logger.info(f"Initialized LLMReviewer with model={self.model}", correlation_id="INIT")

    def run(
        self,
        original_yaml: str,
        optimised_yaml: str,
        issues_detected: List[Dict[str, Any]],
        applied_fixes: List[Dict[str, Any]],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform confidence evaluation using Claude Sonnet."""
        if not optimised_yaml:
            raise ReviewError("optimised_yaml must be a non-empty string")

        user_prompt = CRITIC_EXECUTION_PROMPT.format(
            original_yaml=original_yaml,
            optimised_yaml=optimised_yaml,
            issues_detected=json.dumps(issues_detected, indent=2),
            applied_fixes=json.dumps(applied_fixes, indent=2)
        )

        try:
            raw_output = self._call_llm(CRITIC_SYSTEM_PROMPT, user_prompt, correlation_id)
            review = self._parse_json_response(raw_output, correlation_id)
            review = self._compute_confidence_score(review)

            logger.info(
                f"LLM Review complete -> fix_confidence={review.get('fix_confidence')} "
                f"merge_confidence={review.get('merge_confidence')}",
                correlation_id=correlation_id
            )

            return review

        except anthropic.APIError as e:
            logger.error(
                f"Anthropic API error during LLM review: {str(e)[:200]}",
                correlation_id=correlation_id
            )
            raise CriticError(f"Anthropic API error: {e}") from e
        except Exception as e:
            logger.exception(
                f"LLM review failed unexpectedly: {str(e)[:200]}",
                correlation_id=correlation_id
            )
            raise CriticError(f"LLM review failed: {e}") from e

    def _call_llm(self, system_prompt: str, user_prompt: str, correlation_id: Optional[str] = None) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return message.content[0].text

    def _parse_json_response(self, text_output: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        cleaned = text_output.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}", correlation_id=correlation_id)
            logger.debug(f"Raw LLM output: {text_output[:500]}", correlation_id=correlation_id)
            raise CriticError(f"Invalid JSON output from Claude: {e}") from e

    def _compute_confidence_score(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """Compute heuristic confidence scores from LLM review output."""
        # Use quality_score if provided
        fix_quality = review.get("quality_score", 5)
        review["fix_confidence"] = max(0.0, min(fix_quality / 10, 1.0))

        # Merge confidence heuristic
        regressions = len(review.get("regressions", []))
        unresolved = len(review.get("unresolved_issues", []))
        merge_score = review["fix_confidence"] - 0.1 * regressions - 0.05 * unresolved
        review["merge_confidence"] = max(0.0, min(merge_score, 1.0))

        return review

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute LLM review as a non-blocking stage."""
        correlation_id = state.get("correlation_id")
        try:
            result = self.run(
                original_yaml=state.get("pipeline_yaml", ""),
                optimised_yaml=state.get("optimised_yaml", ""),
                issues_detected=state.get("analysis_result", {}).get("issues_detected", []),
                applied_fixes=state.get("analysis_result", {}).get("suggested_fixes", []),
                correlation_id=correlation_id
            )
            state["llm_review"] = result
        except Exception as e:
            state["llm_review"] = {"error": str(e)}
            logger.error(f"LLM review failed: {str(e)[:200]}", correlation_id=correlation_id)
        return state

    def _get_artifact_key(self) -> Optional[str]:
        return "llm_review"
