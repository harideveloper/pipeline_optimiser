"""
Fixer Agent - Applies suggested optimisations to CI/CD pipeline YAML.
"""

from typing import Dict, Any, Optional, List
import yaml

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.utils.llm_client import LLMClient
from app.config import config
from app.exceptions import FixerError
from app.orchestrator.prompts import FIXER_SYSTEM_PROMPT, build_fixer_prompt

logger = get_logger(__name__, "Fixer")


class Fixer(BaseService):
    """
    Applies suggested fixes to a CI/CD pipeline YAML file.
    
    Uses LLM to apply optimisations while ensuring output is valid YAML.
    """

    def __init__(self, model: str = None, temperature: float = None):
        """
        Initialize Fixer with LLM configuration.
        
        Args:
            model: LLM model name (defaults to config.MODEL_NAME)
            temperature: LLM temperature (defaults to 0 for deterministic fixes)
        """
        super().__init__(agent_name="fix")
        
        self.model = model or config.MODEL_NAME
        self.temperature = temperature if temperature is not None else config.MODEL_TEMPERATURE
        
        self.llm_client = LLMClient(
            model=self.model,
            temperature=self.temperature
        )
        
        logger.debug(
            f"Initialised Fixer: model={self.model}, temperature={self.temperature}",
            correlation_id="INIT"
        )

    def run(
        self,
        pipeline_yaml: str,
        suggested_fixes: List[str],
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Apply suggested fixes to pipeline YAML.
        
        Args:
            pipeline_yaml: Original pipeline YAML
            suggested_fixes: List of fixes to apply
            correlation_id: Request correlation ID
            
        Returns:
            Optimised YAML content (or original if fixing fails)
            
        Raises:
            FixerError: If inputs are invalid
        """
        # Validate inputs
        if not pipeline_yaml or not pipeline_yaml.strip():
            logger.error("Empty pipeline YAML provided", correlation_id=correlation_id)
            raise FixerError("pipeline_yaml must be a non-empty string")

        if not suggested_fixes:
            logger.debug("No fixes to apply, returning original", correlation_id=correlation_id)
            return pipeline_yaml

        logger.debug(f"Applying {len(suggested_fixes)} fixes", correlation_id=correlation_id)

        try:
            # Build prompt using centralized prompt builder
            prompt = build_fixer_prompt(pipeline_yaml, suggested_fixes)
            
            # Call LLM
            raw_result = self._call_llm(prompt, correlation_id)
            
            # Clean and validate output
            optimised_yaml = self._clean_yaml_output(raw_result)
            
            # Validate YAML syntax
            if not self._validate_yaml(optimised_yaml, correlation_id):
                logger.warning("Generated YAML invalid, returning original", correlation_id=correlation_id)
                return pipeline_yaml

            logger.info(f"Applied {len(suggested_fixes)} fixes successfully", correlation_id=correlation_id)
            return optimised_yaml

        except FixerError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate optimised YAML: {e}", correlation_id=correlation_id)
            raise FixerError(f"Failed to generate optimised YAML: {e}") from e

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute fixer within workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with optimised_yaml
        """
        correlation_id = state.get("correlation_id")
        
        # Extract suggested fixes from analysis result
        suggested_fixes = state.get("analysis_result", {}).get("suggested_fixes", [])

        if not suggested_fixes:
            state["error"] = "No fixes to apply"
            logger.warning("No fixes to apply", correlation_id=correlation_id)
            return state

        # Apply fixes
        try:
            optimised = self.run(
                pipeline_yaml=state["pipeline_yaml"],
                suggested_fixes=suggested_fixes,
                correlation_id=correlation_id
            )

            # Validate output
            if optimised and len(optimised) > 50:
                state["optimised_yaml"] = optimised
                logger.debug("Optimised YAML stored in state", correlation_id=correlation_id)
            else:
                state["error"] = "Fixer returned invalid output"
                logger.error("Invalid output from fixer", correlation_id=correlation_id)
                
        except FixerError as e:
            state["error"] = f"Fixer failed: {e}"
            logger.error(f"Fixer execution failed: {e}", correlation_id=correlation_id)
        except Exception as e:
            state["error"] = f"Unexpected fixer error: {e}"
            logger.exception(f"Unexpected fixer error: {e}", correlation_id=correlation_id)

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact saving.
        
        Returns:
            Key name for optimised YAML in state
        """
        return "optimised_yaml"

    def _call_llm(self, prompt: str, correlation_id: Optional[str] = None) -> str:
        """
        Call LLM to generate optimised YAML.
        
        Args:
            prompt: Prompt with original YAML and fixes
            correlation_id: Request correlation ID
            
        Returns:
            Raw LLM response
        """
        return self.llm_client.chat_completion(
            system_prompt=FIXER_SYSTEM_PROMPT,
            user_prompt=prompt,
            correlation_id=correlation_id
        )

    def _clean_yaml_output(self, text: str) -> str:
        """
        Remove markdown formatting from LLM output.
        
        Args:
            text: Raw LLM response
            
        Returns:
            Cleaned YAML content
        """
        cleaned = text.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith("```yaml"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        return cleaned.strip()

    def _validate_yaml(self, yaml_content: str, correlation_id: Optional[str] = None) -> bool:
        """
        Validate YAML syntax.
        
        Args:
            yaml_content: YAML content to validate
            correlation_id: Request correlation ID
            
        Returns:
            True if valid YAML, False otherwise
        """
        try:
            yaml.safe_load(yaml_content)
            logger.debug("Generated YAML is valid", correlation_id=correlation_id)
            return True
        except yaml.YAMLError as e:
            logger.warning(f"Generated YAML is invalid: {e}", correlation_id=correlation_id)
            return False