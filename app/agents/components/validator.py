"""
Validator Agent - Validates CI/CD pipeline YAML structure and syntax.
"""

import yaml
from typing import Dict, Any, Optional, List

from app.agents.components.base_agent import BaseAgent
from app.utils.logger import get_logger

logger = get_logger(__name__, "ValidatorAgent")


class ValidatorAgent(BaseAgent):
    """
    Validates CI/CD pipeline YAML for structure, syntax, and required keys.
    """
    REQUIRED_KEYS = ["on", "jobs"]

    def __init__(self):
        super().__init__(agent_name="validate")
        logger.debug("Initialised ValidatorAgent", correlation_id="INIT")

    def run(self, pipeline_yaml: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate pipeline YAML content for syntax and structure.
        """
        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            logger.error("Invalid or empty pipeline YAML", correlation_id=correlation_id)
            raise ValueError("pipeline_yaml must be a non-empty string")

        preprocessed_yaml = self._preprocess_yaml(pipeline_yaml)
        parsed_yaml = self._parse_yaml(preprocessed_yaml, correlation_id)

        if not parsed_yaml:
            return {"valid": False, "reason": "YAML parsing failed or empty document"}

        normalized_keys = self._normalize_keys(list(parsed_yaml.keys()))
        missing_keys = [k for k in self.REQUIRED_KEYS if k not in normalized_keys]

        if missing_keys:
            return {"valid": False, "reason": f"Missing required keys: {', '.join(missing_keys)}"}

        return {"valid": True}

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute validation step within the workflow.
        """
        correlation_id = state.get("correlation_id")

        try:
            result = self.run(
                pipeline_yaml=state["pipeline_yaml"],
                correlation_id=correlation_id
            )
        except Exception as e:
            result = {"valid": False, "reason": str(e)}

        state["validation_result"] = result

        if not result.get("valid"):
            logger.error("Validation failed: %s" % result.get("reason"), correlation_id=correlation_id)
            state["error"] = result.get("reason")
        else:
            logger.info("Validation complete: valid=True", correlation_id=correlation_id)

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """Validation result should be saved as artifact."""
        return "validation_result"

    def _preprocess_yaml(self, yaml_content: str) -> str:
        """Remove BOM and normalize encoding."""
        try:
            return yaml_content.encode("utf-8").decode("utf-8-sig").strip()
        except Exception:
            return yaml_content.strip()

    def _parse_yaml(self, yaml_content: str, correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Parse YAML and return first valid document dictionary."""
        try:
            for doc in yaml.safe_load_all(yaml_content):
                if isinstance(doc, dict) and doc:
                    return doc
        except yaml.YAMLError as e:
            logger.error("YAML parsing error: %s" % str(e), correlation_id=correlation_id)
            return None
        return None

    def _normalize_keys(self, keys: List[Any]) -> List[str]:
        """Normalize YAML top-level keys."""
        normalized = []
        for key in keys:
            if key is True:
                normalized.append("on")
            elif key is False:
                normalized.append("off")
            else:
                normalized.append(str(key))
        return normalized
