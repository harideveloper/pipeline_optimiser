"""
Validator Agent - Validates CI/CD pipeline YAML structure and syntax.
Refactored for clarity, maintainability, and coding standards.
"""

import yaml
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ValidatorAgent:
    """
    Validates CI/CD pipeline YAML for structure and syntax.
    Checks:
      - Valid YAML
      - Required top-level keys (e.g., 'on', 'jobs')
    """

    REQUIRED_KEYS = ["on", "jobs"]

    def run(self, pipeline_yaml: str) -> Dict[str, Any]:
        """
        Validate pipeline YAML.

        Args:
            pipeline_yaml: YAML content as string

        Returns:
            Dictionary with validation result:
              - valid (bool)
              - reason (str, optional)
        """
        if not pipeline_yaml or not isinstance(pipeline_yaml, str):
            return {"valid": False, "reason": "Invalid YAML input"}

        preprocessed_yaml = self._preprocess_yaml(pipeline_yaml)
        parsed = self._parse_yaml(preprocessed_yaml)

        if not parsed:
            return {"valid": False, "reason": "YAML parsing failed or no valid document found"}

        normalized_keys = self._normalize_keys(list(parsed.keys()))
        missing_keys = [k for k in self.REQUIRED_KEYS if k not in normalized_keys]

        if missing_keys:
            return {"valid": False, "reason": f"Missing required keys: {', '.join(missing_keys)}"}

        return {"valid": True}

    # ---------------------------
    # Internal helpers
    # ---------------------------
    def _preprocess_yaml(self, yaml_content: str) -> str:
        """Remove BOM and normalize encoding."""
        try:
            return yaml_content.encode("utf-8").decode("utf-8-sig").strip()
        except Exception:
            return yaml_content.strip()

    def _parse_yaml(self, yaml_content: str) -> Optional[Dict[str, Any]]:
        """Parse YAML and return first valid dictionary document."""
        try:
            for doc in yaml.safe_load_all(yaml_content):
                if isinstance(doc, dict) and doc:
                    return doc
        except yaml.YAMLError:
            return None
        return None

    def _normalize_keys(self, keys: List[Any]) -> List[str]:
        """Normalize YAML top-level keys to handle boolean quirks in YAML 1.1."""
        normalized = []
        for key in keys:
            if key is True:
                normalized.append("on")
            elif key is False:
                normalized.append("off")
            else:
                normalized.append(str(key))
        return normalized
