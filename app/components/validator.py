"""
Validator Agent - Validates CI/CD pipeline YAML structure and syntax.
"""

import yaml
from typing import Dict, Any, Optional, List

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.exceptions import ValidationError

logger = get_logger(__name__, "Validator")


class Validator(BaseService):
    """
    Validates CI/CD pipeline YAML for structure, syntax, and required keys.
    
    Performs deterministic validation without LLM calls:
    - YAML syntax checking
    - Required key validation
    - Structure verification
    """

    # Required top-level keys for GitHub Actions workflows
    REQUIRED_KEYS = ["on", "jobs"]

    def __init__(self):
        """Initialize Validator."""
        super().__init__(agent_name="validate")
        logger.debug("Initialised Validator", correlation_id="INIT")

    def run(self, pipeline_yaml: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate pipeline YAML content for syntax and structure.
        
        Args:
            pipeline_yaml: YAML content to validate
            correlation_id: Request correlation ID
            
        Returns:
            Dictionary with validation results:
                - valid: Boolean indicating if YAML is valid
                - reason: Error message if invalid, omitted if valid
                
        Raises:
            ValidationError: If input is invalid
        """
        # Input validation
        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            logger.error("Invalid or empty pipeline YAML", correlation_id=correlation_id)
            raise ValidationError("pipeline_yaml must be a non-empty string")

        logger.debug("Starting YAML validation", correlation_id=correlation_id)

        # Preprocess YAML
        preprocessed_yaml = self._preprocess_yaml(pipeline_yaml)
        
        # Parse YAML
        parsed_yaml = self._parse_yaml(preprocessed_yaml, correlation_id)
        if not parsed_yaml:
            return {
                "valid": False,
                "reason": "YAML parsing failed or empty document"
            }

        # Validate required keys
        normalized_keys = self._normalize_keys(list(parsed_yaml.keys()))
        missing_keys = [k for k in self.REQUIRED_KEYS if k not in normalized_keys]
        
        if missing_keys:
            missing_str = ", ".join(missing_keys)
            logger.warning(f"Missing required keys: {missing_str}", correlation_id=correlation_id)
            return {
                "valid": False,
                "reason": f"Missing required keys: {missing_str}"
            }

        logger.info("Validation complete: valid=True", correlation_id=correlation_id)
        return {"valid": True}

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute validation step within the workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with validation_result
        """
        correlation_id = state.get("correlation_id")

        try:
            result = self.run(
                pipeline_yaml=state["pipeline_yaml"],
                correlation_id=correlation_id
            )
        except ValidationError as e:
            result = {"valid": False, "reason": str(e)}
            logger.error(f"Validation error: {e}", correlation_id=correlation_id)
        except Exception as e:
            result = {"valid": False, "reason": f"Unexpected error: {e}"}
            logger.exception(f"Unexpected validation error: {e}", correlation_id=correlation_id)

        state["validation_result"] = result

        if not result.get("valid"):
            # Set error to stop workflow
            state["error"] = result.get("reason")
            logger.error(f"Validation failed: {result.get('reason')}", correlation_id=correlation_id)
        else:
            logger.debug("Validation passed", correlation_id=correlation_id)

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact saving.
        
        Returns:
            Key name for validation results in state
        """
        return "validation_result"

    def _preprocess_yaml(self, yaml_content: str) -> str:
        """        
        pipeline yaml pre processing
        Args:
            yaml_content: Raw YAML content
            
        Returns:
            Preprocessed YAML content
        """
        try:
            return yaml_content.encode("utf-8").decode("utf-8-sig").strip()
        except Exception as e:
            logger.debug(f"Encoding normalization failed, using as-is: {e}")
            return yaml_content.strip()

    def _parse_yaml(
        self,
        yaml_content: str,
        correlation_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        pipeline yaml parsing        
        Args:
            yaml_content: Preprocessed YAML content
            correlation_id: Request correlation ID
            
        Returns:
            Parsed YAML dictionary, or None if parsing fails
        """
        try:
            for doc in yaml.safe_load_all(yaml_content):
                if isinstance(doc, dict) and doc:
                    logger.debug(
                        f"Successfully parsed YAML document with {len(doc)} top-level keys",
                        correlation_id=correlation_id
                    )
                    return doc
            logger.warning("No valid YAML documents found", correlation_id=correlation_id)
            return None
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}", correlation_id=correlation_id)
            return None

    def _normalize_keys(self, keys: List[Any]) -> List[str]:
        """
        Normalize YAML top-level keys.
        
        Handles YAML parser quirks where 'on' may be parsed as boolean True.
        
        Args:
            keys: List of raw keys from parsed YAML
            
        Returns:
            List of normalized string keys
        """
        normalized = []
        for key in keys:
            if key is True:
                normalized.append("on")
            elif key is False:
                normalized.append("off")
            else:
                normalized.append(str(key))
        return normalized