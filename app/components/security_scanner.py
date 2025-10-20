"""
Security Scanner Agent - Scans CI/CD pipelines for security vulnerabilities
"""

import re
import yaml
from typing import Dict, Any, Optional, List

from app.components.base_service import BaseService
from app.utils.logger import get_logger

logger = get_logger(__name__, "SecurityScanner")


class SecurityScanner(BaseService):
    """
    Scans CI/CD pipelines for security vulnerabilities.
    All security check logic is contained within this agent.
    """

    def __init__(self):
        super().__init__(agent_name="security_scan")
        
        self.checks = {
            "secrets_exposed": self._check_secrets_exposure,
            "unsafe_commands": self._check_unsafe_commands,
            "privilege_escalation": self._check_privilege_escalation,
            "insecure_defaults": self._check_insecure_defaults
        }
        
        logger.debug("Initialised SecurityScanner", correlation_id="INIT")

    def run(self, pipeline_yaml: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Scan pipeline YAML for security vulnerabilities

        Args:
            pipeline_yaml: YAML content to scan
            correlation_id: Request correlation ID

        Returns:
            Dict with passed status, vulnerabilities list, and details
        """
        security_checks = {
            name: check_fn(pipeline_yaml, correlation_id)
            for name, check_fn in self.checks.items()
        }

        vulnerabilities = [k for k, v in security_checks.items() if v]

        result = {
            "passed": len(vulnerabilities) == 0,
            "vulnerabilities": vulnerabilities,
            "checks_performed": list(security_checks.keys()),
            "details": security_checks
        }

        logger.info(
            "Security scan: %s | Vulnerabilities: %s" % (
                "passed" if result["passed"] else "failed",
                ", ".join(vulnerabilities) if vulnerabilities else "none"
            ),
            correlation_id=correlation_id
        )

        return result

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security scan within workflow"""
        correlation_id = state.get("correlation_id")
        yaml_content = state.get("pipeline_yaml", "")
        scan_result = self.run(yaml_content, correlation_id)

        state["security_scan"] = scan_result

        if scan_result["vulnerabilities"]:
            state["security_warnings"] = scan_result["vulnerabilities"]
            logger.warning("Security warnings: %s" % ", ".join(scan_result["vulnerabilities"]), correlation_id=correlation_id)

            if self._is_critical(scan_result["vulnerabilities"]):
                state["error"] = "Critical security issue detected"
                logger.error("Critical security vulnerability detected", correlation_id=correlation_id)
            else:
                logger.info("Non-critical warnings will be addressed in fix", correlation_id=correlation_id)
        else:
            logger.info("Security scan passed", correlation_id=correlation_id)

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """Security scan results should be saved as artifact"""
        return "security_scan"

    def _check_secrets_exposure(self, yaml_content: str, correlation_id: Optional[str] = None) -> bool:
        """Check if secrets might be exposed in logs"""
        risky_patterns = [
            r'echo\s+\$.*PASSWORD',
            r'echo\s+\$.*TOKEN',
            r'echo\s+\$.*SECRET',
            r'echo\s+\$.*KEY',
            r'set\s+-x.*\$.*PASSWORD',
            r'set\s+-x.*\$.*TOKEN',
            r'printenv',
            r'env\s*\|',
        ]

        for pattern in risky_patterns:
            if re.search(pattern, yaml_content, re.IGNORECASE):
                logger.debug("Secrets exposure pattern found: %s" % pattern, correlation_id=correlation_id)
                return True
        return False

    def _check_unsafe_commands(self, yaml_content: str, correlation_id: Optional[str] = None) -> bool:
        """Check for unsafe shell commands"""
        unsafe_patterns = [
            r'curl\s+.*\|\s*bash',
            r'wget\s+.*\|\s*sh',
            r'eval\s+\$',
            r'rm\s+-rf\s+/',
            r'chmod\s+777',
        ]

        for pattern in unsafe_patterns:
            if re.search(pattern, yaml_content, re.IGNORECASE):
                logger.debug("Unsafe command pattern found: %s" % pattern, correlation_id=correlation_id)
                return True
        return False

    def _check_privilege_escalation(self, yaml_content: str, correlation_id: Optional[str] = None) -> bool:
        """Check for privilege escalation risks"""
        try:
            config = yaml.safe_load(yaml_content)
            if not isinstance(config, dict):
                return False

            jobs = config.get("jobs", {})
            for job_config in jobs.values():
                steps = job_config.get("steps", [])
                for step in steps:
                    run_cmd = step.get("run", "") if isinstance(step, dict) else ""
                    if "sudo" in run_cmd.lower():
                        logger.debug("Privilege escalation detected: sudo usage", correlation_id=correlation_id)
                        return True

                container_opts = job_config.get("container", {}).get("options", "")
                if "--privileged" in container_opts:
                    logger.debug("Privilege escalation detected: privileged container", correlation_id=correlation_id)
                    return True

        except yaml.YAMLError as e:
            logger.warning("Failed to parse YAML for privilege escalation check: %s" % e, correlation_id=correlation_id)
            pass

        return False

    def _check_insecure_defaults(self, yaml_content: str, correlation_id: Optional[str] = None) -> bool:
        """Check for insecure default configurations"""
        try:
            config = yaml.safe_load(yaml_content)
            if not isinstance(config, dict):
                return False

            jobs = config.get("jobs", {})
            for job_id, job_config in jobs.items():
                if "timeout-minutes" not in job_config:
                    logger.debug("Insecure default: missing timeout for job %s" % job_id, correlation_id=correlation_id)
                    return True

        except yaml.YAMLError as e:
            logger.warning("Failed to parse YAML for insecure defaults check: %s" % e, correlation_id=correlation_id)
            pass

        return False

    def _is_critical(self, vulnerabilities: List[str]) -> bool:
        """Determine if vulnerabilities are critical and should block workflow"""
        critical_issues = ["secrets_exposed"]
        return any(vuln in critical_issues for vuln in vulnerabilities)