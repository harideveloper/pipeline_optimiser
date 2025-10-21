"""
Reviewer Agent - Validates optimized/fixed CI/CD pipeline YAML.
"""

import yaml
from typing import Dict, Any, Optional, List

from app.components.base_service import BaseService
from app.components.validator import Validator
from app.utils.logger import get_logger
from app.exceptions import ReviewError

logger = get_logger(__name__, "Reviewer")


class Reviewer(BaseService):
    """
    Reviews that applied fixes to CI/CD YAML are correct
    and follow CI/CD best practices.
    
    Performs multiple validation checks:
    - Basic YAML structure (via Validator)
    - Syntax validation
    - Job dependency validation
    - Best practices compliance
    """

    def __init__(self):
        """Initialize Reviewer with Validator instance."""
        super().__init__(agent_name="review")
        self.validator = Validator()
        logger.debug("Initialised Reviewer", correlation_id="INIT")

    def run(self, pipeline_yaml: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run post-fix verification checks.
        
        Args:
            pipeline_yaml: Optimised YAML to review
            correlation_id: Request correlation ID
            
        Returns:
            Dictionary with detailed verification results:
                - validations: Dict of check results
                - passed_count: Number of passed checks
                - total_count: Total number of checks
                - pass_rate: Percentage of passed checks
                - overall_status: "pass" or "fail"
                
        Raises:
            ReviewError: If input is invalid
        """
        # Validate input
        if not pipeline_yaml or not isinstance(pipeline_yaml, str):
            raise ReviewError("pipeline_yaml must be a non-empty string")
        
        logger.debug("Starting comprehensive review", correlation_id=correlation_id)
        
        validations = {}

        # Run all validation checks
        try:
            # Basic validation
            basic_result = self.validator.run(pipeline_yaml, correlation_id)
            validations["basic"] = {
                "passed": basic_result.get("valid", False),
                "reason": basic_result.get("reason", "OK")
            }
        except Exception as e:
            validations["basic"] = {
                "passed": False,
                "reason": f"Basic validation failed: {e}"
            }

        # Syntax check
        validations["syntax"] = self._check_syntax(pipeline_yaml, correlation_id)
        
        # Dependencies check
        validations["dependencies"] = self._check_dependencies(pipeline_yaml, correlation_id)
        
        # Best practices check
        validations["best_practices"] = self._check_best_practices(pipeline_yaml, correlation_id)

        # Calculate overall results
        passed_count = sum(1 for v in validations.values() if v.get("passed", False))
        total_count = len(validations)
        pass_rate = passed_count / total_count if total_count > 0 else 0
        overall_status = "pass" if passed_count == total_count else "fail"

        logger.info(
            f"Review complete: {passed_count}/{total_count} checks passed ({pass_rate:.1%})",
            correlation_id=correlation_id
        )

        return {
            "validations": validations,
            "passed_count": passed_count,
            "total_count": total_count,
            "pass_rate": pass_rate,
            "overall_status": overall_status
        }

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute review within workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with comprehensive_validation and fix_verified
        """
        correlation_id = state.get("correlation_id")
        
        try:
            # Run comprehensive review
            result = self.run(state.get("optimised_yaml", ""), correlation_id)
            state["comprehensive_validation"] = result
            
            # Update fix verification status
            if result.get("overall_status") == "pass":
                state["fix_verified"] = True
                logger.info("Fix review passed", correlation_id=correlation_id)
            else:
                state["fix_verified"] = False
                logger.warning(f"Fix review failed: {result}", correlation_id=correlation_id)
            
            # Log issues found
            issues = [i for v in result["validations"].values() for i in v.get("issues", [])]
            if issues:
                logger.info(
                    f"Review found {len(issues)} issues: {', '.join(issues)}",
                    correlation_id=correlation_id
                )
                
        except ReviewError as e:
            logger.error(f"Review failed: {e}", correlation_id=correlation_id)
            state["fix_verified"] = False
            state["comprehensive_validation"] = {
                "overall_status": "fail",
                "error": str(e)
            }
        except Exception as e:
            logger.exception(f"Unexpected review error: {e}", correlation_id=correlation_id)
            state["fix_verified"] = False
            state["comprehensive_validation"] = {
                "overall_status": "fail",
                "error": f"Unexpected error: {e}"
            }

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact saving.
        
        Returns:
            Key name for review results in state
        """
        return "comprehensive_validation"

    def _check_syntax(self, yaml_content: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate YAML syntax.
        
        Args:
            yaml_content: YAML content to validate
            correlation_id: Request correlation ID
            
        Returns:
            Validation result dictionary
        """
        if not yaml_content:
            return {"passed": False, "reason": "No YAML to validate"}
        
        try:
            yaml.safe_load(yaml_content)
            logger.debug("YAML syntax check passed", correlation_id=correlation_id)
            return {"passed": True, "reason": "Valid YAML syntax"}
        except yaml.YAMLError as e:
            logger.error(f"YAML syntax error: {e}", correlation_id=correlation_id)
            return {"passed": False, "reason": f"YAML syntax error: {e}"}

    def _check_dependencies(self, yaml_content: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate job dependencies.
        
        Checks for:
        - Circular dependencies (job depending on itself)
        - Missing dependencies (job depending on non-existent job)
        
        Args:
            yaml_content: YAML content to validate
            correlation_id: Request correlation ID
            
        Returns:
            Validation result dictionary
        """
        if not yaml_content:
            return {"passed": False, "reason": "No YAML to validate"}
        
        try:
            config = yaml.safe_load(yaml_content)
            jobs = config.get("jobs", {})
            
            for job_id, job_cfg in jobs.items():
                # Get job dependencies
                needs = job_cfg.get("needs", [])
                if isinstance(needs, str):
                    needs = [needs]
                
                # Check each dependency
                for dep in needs:
                    # Check for circular dependency
                    if dep == job_id:
                        logger.error(f"Job {job_id} depends on itself", correlation_id=correlation_id)
                        return {
                            "passed": False,
                            "reason": f"Job {job_id} depends on itself"
                        }
                    
                    # Check for missing dependency
                    if dep not in jobs:
                        logger.error(
                            f"Job {job_id} depends on non-existent job {dep}",
                            correlation_id=correlation_id
                        )
                        return {
                            "passed": False,
                            "reason": f"Job {job_id} depends on non-existent job {dep}"
                        }
            
            logger.debug("Job dependencies check passed", correlation_id=correlation_id)
            return {"passed": True, "reason": "Dependencies valid"}
            
        except yaml.YAMLError as e:
            logger.error(f"YAML error during dependency check: {e}", correlation_id=correlation_id)
            return {"passed": False, "reason": f"YAML error: {e}"}

    def _check_best_practices(self, yaml_content: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Check CI/CD best practices.
        
        Checks for:
        - Caching usage (improves performance)
        - Job timeouts (prevents hanging jobs)
        
        Args:
            yaml_content: YAML content to validate
            correlation_id: Request correlation ID
            
        Returns:
            Validation result dictionary with issues list
        """
        if not yaml_content:
            return {"passed": False, "reason": "No YAML to validate"}
        
        issues: List[str] = []
        
        try:
            config = yaml.safe_load(yaml_content)
            jobs = config.get("jobs", {})
            
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
            
            # Determine result
            if issues:
                logger.warning(
                    f"Best practices issues: {', '.join(issues)}",
                    correlation_id=correlation_id
                )
            else:
                logger.debug("Best practices check passed", correlation_id=correlation_id)
            
            return {
                "passed": len(issues) == 0,
                "reason": "All best practices followed" if not issues else "Issues found",
                "issues": issues
            }
            
        except yaml.YAMLError as e:
            logger.error(f"YAML error during best practices check: {e}", correlation_id=correlation_id)
            return {"passed": False, "reason": f"YAML error: {e}"}