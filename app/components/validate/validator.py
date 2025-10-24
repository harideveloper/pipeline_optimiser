"""
Validator Agent - Validates CI/CD pipeline YAML structure and syntax.
Supports two modes: input (pre-optimisation) and output (post-optimisation).
"""

import yaml
from typing import Dict, Any, Optional, List

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.exceptions import ValidationError

logger = get_logger(__name__, "Validator")


class Validator(BaseService):
    """
    Validator for CI/CD YAML
    
    Modes:
    - input: Pre-optimisation validation (syntax + structure + dependencies)
    - output: Post-optimisation validation (input checks + best practices)
    
    Performs deterministic validation without LLM calls:
    - YAML syntax checking
    - Required key validation
    - Job dependency validation
    - Best practices compliance (output mode only)
    """


    REQUIRED_KEYS = ["on", "jobs"]

    def __init__(self):
        """Initialize Validator."""
        super().__init__(agent_name="validate")
        logger.debug("Initialised Validator", correlation_id="INIT")

    def run(
        self, 
        pipeline_yaml: str, 
        mode: str = "input",
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate pipeline YAML content.
        
        Args:
            pipeline_yaml: YAML content to validate
            mode: "input" (pre-optimisation) or "output" (post-optimisation)
            correlation_id: Request correlation ID
            
        Returns:
            Dictionary with validation results:
                - valid: Boolean indicating if YAML is valid
                - reason: Error message if invalid, success message if valid
                - issues: List of non-blocking issues (output mode only)
                
        Raises:
            ValidationError: If input is invalid
        """
        # Input validation
        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            logger.error("Invalid or empty pipeline YAML", correlation_id=correlation_id)
            raise ValidationError("pipeline_yaml must be a non-empty string")

        if mode not in ["input", "output"]:
            raise ValidationError(f"Invalid mode: {mode}. Must be 'input' or 'output'")

        logger.debug(f"Starting YAML validation (mode={mode})", correlation_id=correlation_id)

        # Preprocess YAML
        preprocessed_yaml = self._preprocess_yaml(pipeline_yaml)
        
        # Parse YAML
        parsed_yaml = self._parse_yaml(preprocessed_yaml, correlation_id)
        if not parsed_yaml:
            return {
                "valid": False,
                "reason": "YAML parsing failed or empty document",
                "mode": mode
            }

        # Check 1: Required keys
        normalized_keys = self._normalize_keys(list(parsed_yaml.keys()))
        missing_keys = [k for k in self.REQUIRED_KEYS if k not in normalized_keys]
        
        if missing_keys:
            missing_str = ", ".join(missing_keys)
            logger.warning(f"Missing required keys: {missing_str}", correlation_id=correlation_id)
            return {
                "valid": False,
                "reason": f"Missing required keys: {missing_str}",
                "mode": mode
            }

        # Check 2: Job dependencies (both modes)
        dep_check = self._check_dependencies(parsed_yaml, correlation_id)
        if not dep_check["valid"]:
            return {
                "valid": False,
                "reason": dep_check["reason"],
                "mode": mode
            }

        # Check 3: Best practices (output mode only)
        issues = []
        if mode == "output":
            bp_check = self._check_best_practices(parsed_yaml, correlation_id)
            issues = bp_check.get("issues", [])
            
            if issues:
                logger.info(
                    f"Best practices issues found: {', '.join(issues)}",
                    correlation_id=correlation_id
                )

        # Success
        logger.info(
            f"Validation complete (mode={mode}): valid=True, issues={len(issues)}",
            correlation_id=correlation_id
        )
        
        result = {
            "valid": True,
            "reason": f"Validation passed ({mode} mode)",
            "mode": mode
        }
        
        if issues:
            result["issues"] = issues
            result["reason"] = f"Validation passed with {len(issues)} best practice issues"
        
        return result

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute validation step within the workflow.
        
        Determines mode based on workflow state:
        - "input" mode: Before optimisation (uses pipeline_yaml)
        - "output" mode: After optimisation (uses optimised_yaml)
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with validation_result
        """
        correlation_id = state.get("correlation_id")
        
        # Determine mode and YAML source
        if state.get("optimised_yaml"):
            mode = "output"
            yaml_content = state["optimised_yaml"]
            logger.debug("Running post-optimisation validation", correlation_id=correlation_id)
        else:
            mode = "input"
            yaml_content = state.get("pipeline_yaml", "")
            logger.debug("Running pre-optimisation validation", correlation_id=correlation_id)

        try:
            result = self.run(
                pipeline_yaml=yaml_content,
                mode=mode,
                correlation_id=correlation_id
            )
        except ValidationError as e:
            result = {"valid": False, "reason": str(e), "mode": mode}
            logger.error(f"Validation error: {e}", correlation_id=correlation_id)
        except Exception as e:
            result = {"valid": False, "reason": f"Unexpected error: {e}", "mode": mode}
            logger.exception(f"Unexpected validation error: {e}", correlation_id=correlation_id)

        # Store result with mode-specific key
        if mode == "input":
            state["validation_result"] = result
        else:
            state["post_validation_result"] = result

        # Stop workflow if validation fails
        if not result.get("valid"):
            state["error"] = result.get("reason")
            logger.error(
                f"Validation failed ({mode} mode): {result.get('reason')}",
                correlation_id=correlation_id
            )
        else:
            logger.debug(f"Validation passed ({mode} mode)", correlation_id=correlation_id)

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
        Pipeline YAML preprocessing.
        
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
        Pipeline YAML parsing.
        
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

    def _check_dependencies(
        self, 
        parsed_yaml: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate job dependencies.
        
        Checks for:
        - Circular dependencies (job depending on itself)
        - Missing dependencies (job depending on non-existent job)
        
        Args:
            parsed_yaml: Parsed YAML dictionary
            correlation_id: Request correlation ID
            
        Returns:
            Validation result: {"valid": True/False, "reason": "..."}
        """
        jobs = parsed_yaml.get("jobs", {})
        
        for job_id, job_cfg in jobs.items():
            # Get job dependencies
            needs = job_cfg.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            
            # Check each dependency
            for dep in needs:
                # Check for circular dependency
                if dep == job_id:
                    logger.error(
                        f"Circular dependency: Job {job_id} depends on itself",
                        correlation_id=correlation_id
                    )
                    return {
                        "valid": False,
                        "reason": f"Circular dependency: Job {job_id} depends on itself"
                    }
                
                # Check for missing dependency
                if dep not in jobs:
                    logger.error(
                        f"Missing dependency: Job {job_id} depends on non-existent job {dep}",
                        correlation_id=correlation_id
                    )
                    return {
                        "valid": False,
                        "reason": f"Missing dependency: Job {job_id} depends on non-existent job {dep}"
                    }
        
        logger.debug("Job dependencies check passed", correlation_id=correlation_id)
        return {"valid": True, "reason": "Dependencies valid"}

    def _check_best_practices(
        self,
        parsed_yaml: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check CI/CD best practices (non-blocking).
        
        Checks for:
        - Caching usage (improves performance)
        - Job timeouts (prevents hanging jobs)
        
        Args:
            parsed_yaml: Parsed YAML dictionary
            correlation_id: Request correlation ID
            
        Returns:
            Dictionary with issues list
        """
        issues: List[str] = []
        jobs = parsed_yaml.get("jobs", {})
        
        # Check for caching
        has_caching = False
        for job_cfg in jobs.values():
            steps = job_cfg.get("steps", [])
            for step in steps:
                if isinstance(step, dict) and "cache" in str(step).lower():
                    has_caching = True
                    break
            if has_caching:
                break
        
        if not has_caching:
            issues.append("No caching detected")
        
        # Check for job timeouts
        for job_id, job_cfg in jobs.items():
            if "timeout-minutes" not in job_cfg:
                issues.append(f"Job {job_id} missing timeout")
        
        logger.debug(
            f"Best practices check: {len(issues)} issues found",
            correlation_id=correlation_id
        )
        
        return {"issues": issues}