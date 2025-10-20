"""
Reviewer Agent - Validates optimized/fixed CI/CD pipeline YAML.
"""

import yaml
from typing import Dict, Any, Optional

from app.components.base_service import BaseService
from app.components.validator import Validator
from app.utils.logger import get_logger

logger = get_logger(__name__, "Reviewer")


class Reviewer(BaseService):
    """
    Reviews that applied fixes to CI/CD YAML are correct
    and follow CI/CD best practices.
    """

    def __init__(self):
        super().__init__(agent_name="review_fix")
        self.validator = Validator()

    def run(self, pipeline_yaml: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run post-fix verification checks
        
        Returns:
            Dictionary with detailed verification results
        """
        validations = {}

        basic_result = self.validator.run(pipeline_yaml, correlation_id)
        validations["basic"] = {
            "passed": basic_result.get("valid", False),
            "reason": basic_result.get("reason", "OK")
        }

        validations["syntax"] = self._check_syntax(pipeline_yaml, correlation_id)
        validations["dependencies"] = self._check_dependencies(pipeline_yaml, correlation_id)
        validations["best_practices"] = self._check_best_practices(pipeline_yaml, correlation_id)

        passed_count = sum(1 for v in validations.values() if v.get("passed", False))
        total_count = len(validations)

        return {
            "validations": validations,
            "passed_count": passed_count,
            "total_count": total_count,
            "pass_rate": passed_count / total_count if total_count > 0 else 0,
            "overall_status": "pass" if passed_count == total_count else "fail"
        }

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute review within workflow"""
        correlation_id = state.get("correlation_id")        
        result = self.run(state.get("optimised_yaml", ""), correlation_id)
        state["comprehensive_validation"] = result
        
        if result.get("overall_status") == "pass":
            state["fix_verified"] = True
            state["completed_steps"].append("review_fix")
        else:
            state["fix_verified"] = False
            logger.warning("Fix review failed: %s" % result, correlation_id=correlation_id)
        
        issues = [i for v in result["validations"].values() for i in v.get("issues", [])]
        logger.info(
            f"Review summary: passed={result['overall_status'] == 'pass'} | "
            f"rate={result['pass_rate']:.2f} | issues={issues}",
            correlation_id=correlation_id
        )
        return state

    def _check_syntax(self, yaml_content: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate YAML syntax"""
        if not yaml_content:
            return {"passed": False, "reason": "No YAML to validate"}
        try:
            yaml.safe_load(yaml_content)
            return {"passed": True, "reason": "Valid YAML syntax"}
        except yaml.YAMLError as e:
            logger.error("YAML syntax error: %s" % str(e), correlation_id=correlation_id)
            return {"passed": False, "reason": f"YAML syntax error: {str(e)}"}

    def _check_dependencies(self, yaml_content: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate job dependencies"""
        if not yaml_content:
            return {"passed": False, "reason": "No YAML to validate"}
        try:
            config = yaml.safe_load(yaml_content)
            jobs = config.get("jobs", {})
            for job_id, job_cfg in jobs.items():
                needs = job_cfg.get("needs", [])
                if isinstance(needs, str):
                    needs = [needs]
                for dep in needs:
                    if dep == job_id:
                        logger.error("Job %s depends on itself" % job_id, correlation_id=correlation_id)
                        return {"passed": False, "reason": f"Job {job_id} depends on itself"}
                    if dep not in jobs:
                        logger.error("Job %s depends on non-existent job %s" % (job_id, dep), correlation_id=correlation_id)
                        return {"passed": False, "reason": f"Job {job_id} depends on non-existent job {dep}"}
            return {"passed": True, "reason": "Dependencies valid"}
        except yaml.YAMLError as e:
            logger.error("YAML error: %s" % str(e), correlation_id=correlation_id)
            return {"passed": False, "reason": f"YAML error: {str(e)}"}

    def _check_best_practices(self, yaml_content: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Check CI/CD best practices (caching, timeouts, etc)"""
        if not yaml_content:
            return {"passed": False, "reason": "No YAML to validate"}
        issues = []
        try:
            config = yaml.safe_load(yaml_content)
            jobs = config.get("jobs", {})
            has_caching = False
            for job_cfg in jobs.values():
                steps = job_cfg.get("steps", [])
                for step in steps:
                    if isinstance(step, dict) and "cache" in str(step).lower():
                        has_caching = True
                        break
            if not has_caching:
                issues.append("No caching detected")
            for job_id, job_cfg in jobs.items():
                if "timeout-minutes" not in job_cfg:
                    issues.append(f"Job {job_id} missing timeout")
        except yaml.YAMLError as e:
            logger.error("YAML error: %s" % str(e), correlation_id=correlation_id)
            return {"passed": False, "reason": f"YAML error: {str(e)}"}
        
        if issues:
            logger.warning("Best practices issues: %s" % ", ".join(issues), correlation_id=correlation_id)
        
        return {
            "passed": len(issues) == 0,
            "reason": "All best practices followed" if not issues else "Issues found",
            "issues": issues
        }
    
    def _get_artifact_key(self) -> Optional[str]:
        """Review artifacts should be saved as artifact"""
        return "reviewer"