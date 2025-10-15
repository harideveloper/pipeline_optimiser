# """
# Validator Agent - Validates CI/CD pipeline YAML structure and syntax.
# """

# import yaml
# import logging
# from typing import Dict, List, Any, Optional

# from app.agents.agent import Agent

# logger = logging.getLogger(__name__)


# class ValidatorAgent(Agent):
#     """
#     Validates CI/CD pipeline YAML for required structure and syntax.
    
#     Checks for:
#     - Valid YAML syntax
#     - Required top-level keys (e.g., 'on', 'jobs')
#     - Proper document structure
#     """
    
#     # Required top-level keys for a valid GitHub Actions workflow
#     REQUIRED_KEYS = ["on", "jobs"]
    
#     def run(self, pipeline_yaml: str) -> Dict[str, Any]:
#         """
#         Validate pipeline YAML structure and syntax.
        
#         Args:
#             pipeline_yaml: YAML content as string
            
#         Returns:
#             Dictionary with validation results:
#             - valid (bool): Whether validation passed
#             - reason (str, optional): Reason for validation failure
#         """
#         # Input validation
#         if pipeline_yaml is None:
#             logger.error("Validation failed: pipeline_yaml is None")
#             return {"valid": False, "reason": "No YAML content provided (None)"}
        
#         if not isinstance(pipeline_yaml, str):
#             logger.error(
#                 "Validation failed: pipeline_yaml is not a string (type: %s)",
#                 type(pipeline_yaml).__name__
#             )
#             return {
#                 "valid": False,
#                 "reason": f"Invalid input type: expected string, got {type(pipeline_yaml).__name__}"
#             }
        
#         if not pipeline_yaml.strip():
#             logger.error("Validation failed: pipeline_yaml is empty")
#             return {"valid": False, "reason": "YAML content is empty"}
        
#         logger.info("Starting pipeline YAML validation")
#         logger.debug("Pipeline YAML size: %d bytes", len(pipeline_yaml))
        
#         # Preprocess YAML (remove BOM, normalize whitespace)
#         preprocessed_yaml = self._preprocess_yaml(pipeline_yaml)
        
#         # Parse YAML
#         parsed = self._parse_yaml(preprocessed_yaml)
#         if parsed is None:
#             logger.error("Validation failed: No valid YAML mapping found")
#             return {"valid": False, "reason": "No valid YAML mapping found."}
        
#         # Extract and log top-level keys
#         top_keys = list(parsed.keys())
#         logger.debug("Top-level keys found: %s", top_keys)
        
#         # Normalize keys (handle YAML 1.1 boolean parsing quirks)
#         normalized_keys = self._normalize_keys(top_keys)
#         logger.debug("Normalized keys: %s", normalized_keys)
        
#         # Check for required keys
#         missing_keys = [k for k in self.REQUIRED_KEYS if k not in normalized_keys]
        
#         if missing_keys:
#             logger.warning(
#                 "Validation failed: Missing required keys: %s",
#                 ", ".join(missing_keys)
#             )
#             return {
#                 "valid": False,
#                 "reason": f"Missing required keys: {', '.join(missing_keys)}"
#             }
        
#         logger.info("Validation passed: All required keys present")
#         return {"valid": True}
    
#     def _preprocess_yaml(self, yaml_content: str) -> str:
#         """
#         Preprocess YAML content by removing BOM and normalizing encoding.
        
#         Args:
#             yaml_content: Raw YAML content
            
#         Returns:
#             Preprocessed YAML content
#         """
#         logger.debug("Preprocessing YAML: removing BOM and normalizing encoding")
        
#         try:
#             # Remove BOM (Byte Order Mark) if present and normalize encoding
#             preprocessed = yaml_content.encode("utf-8").decode("utf-8-sig").strip()
            
#             if len(preprocessed) != len(yaml_content.strip()):
#                 logger.debug("BOM removed from YAML content")
            
#             return preprocessed
            
#         except Exception as e:
#             logger.warning("Failed to preprocess YAML, using original: %s", str(e))
#             return yaml_content.strip()
    
#     def _parse_yaml(self, yaml_content: str) -> Optional[Dict[str, Any]]:
#         """
#         Parse YAML content and extract the first valid document.
        
#         Args:
#             yaml_content: YAML content as string
            
#         Returns:
#             Parsed YAML as dictionary, or None if parsing fails
#         """
#         logger.debug("Parsing YAML content")
        
#         try:
#             # Parse all YAML documents (handles multi-document YAML files)
#             parsed_docs = list(yaml.safe_load_all(yaml_content))
#             logger.debug("Parsed %d YAML document(s)", len(parsed_docs))
            
#             # Find first valid dictionary document
#             for idx, doc in enumerate(parsed_docs):
#                 if isinstance(doc, dict) and doc:
#                     logger.debug(
#                         "Using YAML document %d with %d top-level keys",
#                         idx,
#                         len(doc)
#                     )
#                     return doc
            
#             logger.warning("No valid YAML mapping found in any document")
#             return None
            
#         except yaml.YAMLError as e:
#             logger.error("YAML parsing error: %s", str(e), exc_info=True)
#             return None
            
#         except Exception as e:
#             logger.error("Unexpected error during YAML parsing: %s", str(e), exc_info=True)
#             return None
    
#     def _normalize_keys(self, keys: List[Any]) -> List[str]:
#         """
#         Normalize top-level keys to handle YAML 1.1 boolean parsing quirks.
        
#         YAML 1.1 interprets 'on', 'off', 'yes', 'no' as booleans.
#         GitHub Actions uses 'on' as a key, so we need to normalize.
        
#         Args:
#             keys: List of parsed keys (may include booleans)
            
#         Returns:
#             List of normalized string keys
#         """
#         normalized = []
        
#         for key in keys:
#             if key is True:
#                 # YAML 1.1 parsed 'on' or 'yes' as True
#                 logger.debug("Normalizing boolean True to 'on'")
#                 normalized.append('on')
#             elif key is False:
#                 # YAML 1.1 parsed 'off' or 'no' as False
#                 logger.debug("Normalizing boolean False to 'off'")
#                 normalized.append('off')
#             else:
#                 normalized.append(key)
        
#         return normalized


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
