"""
Security Scanner Agent - Scans CI/CD pipelines for security vulnerabilities
"""

import re
import yaml
from typing import Dict, Any, Optional, List

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.exceptions import SecurityScanError

logger = get_logger(__name__, "SecurityScanner")


class SecurityScanner(BaseService):
    """
    Scans CI/CD pipelines for security vulnerabilities.
    
    Performs deterministic security checks:
    - Secrets exposure detection
    - Unsafe command identification
    - Privilege escalation risks
    - Insecure default configurations
    """

    # Critical vulnerabilities that should block workflow
    CRITICAL_VULNERABILITIES = ["secrets_exposed"]

    def __init__(self):
        """Initialise SecurityScanner with security check registry."""
        super().__init__(agent_name="security_scan")
        
        # Registry of security checks
        self.checks = {
            "secrets_exposed": self._check_secrets_exposure,
            "unsafe_commands": self._check_unsafe_commands,
            "privilege_escalation": self._check_privilege_escalation,
            "insecure_defaults": self._check_insecure_defaults
        }
        
        logger.debug("Initialised SecurityScanner", correlation_id="INIT")

    def run(self, pipeline_yaml: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Scan pipeline YAML for security vulnerabilities.
        
        Args:
            pipeline_yaml: YAML content to scan
            correlation_id: Request correlation ID
            
        Returns:
            Dictionary containing:
                - passed: Boolean indicating if all checks passed
                - vulnerabilities: List of vulnerability names found
                - checks_performed: List of all check names
                - details: Dict of check results
                
        Raises:
            SecurityScanError: If input is invalid
        """
        # Validate input
        if not pipeline_yaml or not isinstance(pipeline_yaml, str):
            raise SecurityScanError("pipeline_yaml must be a non-empty string")
        
        logger.debug("Starting security scan", correlation_id=correlation_id)
        
        # Run all security checks
        security_checks = {
            name: check_fn(pipeline_yaml, correlation_id)
            for name, check_fn in self.checks.items()
        }

        # Collect vulnerabilities
        vulnerabilities = [k for k, v in security_checks.items() if v]

        result = {
            "passed": len(vulnerabilities) == 0,
            "vulnerabilities": vulnerabilities,
            "checks_performed": list(security_checks.keys()),
            "details": security_checks
        }

        # Log results
        if vulnerabilities:
            logger.warning(
                f"Security scan failed: {len(vulnerabilities)} vulnerabilities found - {', '.join(vulnerabilities)}",
                correlation_id=correlation_id
            )
        else:
            logger.info("Security scan passed - no vulnerabilities detected", correlation_id=correlation_id)

        return result

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute security scan within workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with security_scan results
        """
        correlation_id = state.get("correlation_id")
        yaml_content = state.get("pipeline_yaml", "")
        
        try:
            scan_result = self.run(yaml_content, correlation_id)
            state["security_scan"] = scan_result

            # Handle vulnerabilities
            if scan_result["vulnerabilities"]:
                state["security_warnings"] = scan_result["vulnerabilities"]
                
                # Check for critical vulnerabilities
                if self._has_critical_vulnerabilities(scan_result["vulnerabilities"]):
                    state["error"] = "Critical security vulnerability detected"
                    logger.error(
                        f"Critical security issue: {', '.join(scan_result['vulnerabilities'])}",
                        correlation_id=correlation_id
                    )
                else:
                    logger.info(
                        "Non-critical security warnings will be addressed in fix phase",
                        correlation_id=correlation_id
                    )
            else:
                logger.info("Security scan passed", correlation_id=correlation_id)
                
        except SecurityScanError as e:
            logger.error(f"Security scan failed: {e}", correlation_id=correlation_id)
            # Don't block workflow on scan failure, but log it
            state["security_scan"] = {
                "passed": False,
                "error": str(e)
            }

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact saving.
        
        Returns:
            Key name for security scan results in state
        """
        return "security_scan"

    def _check_secrets_exposure(self, yaml_content: str, correlation_id: Optional[str] = None) -> bool:
        """
        Check if secrets might be exposed in logs.
        
        Detects patterns that could expose sensitive information:
        - Echo commands with secret variables
        - Debug mode with secret variables
        - Environment variable dumps
        
        Args:
            yaml_content: YAML content to check
            correlation_id: Request correlation ID
            
        Returns:
            True if potential secrets exposure detected
        """
        risky_patterns = [
            r'echo\s+\$.*PASSWORD',
            r'echo\s+\$.*TOKEN',
            r'echo\s+\$.*SECRET',
            r'echo\s+\$.*KEY',
            r'echo\s+\$.*API_KEY',
            r'set\s+-x.*\$.*PASSWORD',
            r'set\s+-x.*\$.*TOKEN',
            r'set\s+-x.*\$.*SECRET',
            r'printenv',
            r'env\s*\|',
        ]

        for pattern in risky_patterns:
            if re.search(pattern, yaml_content, re.IGNORECASE):
                logger.debug(f"Secrets exposure pattern found: {pattern}", correlation_id=correlation_id)
                return True
        
        return False

    def _check_unsafe_commands(self, yaml_content: str, correlation_id: Optional[str] = None) -> bool:
        """
        Check for unsafe shell commands.
        
        Detects dangerous command patterns:
        - Piping curl/wget to shell
        - Using eval with variables
        - Recursive file deletions
        - Overly permissive permissions
        
        Args:
            yaml_content: YAML content to check
            correlation_id: Request correlation ID
            
        Returns:
            True if unsafe commands detected
        """
        unsafe_patterns = [
            r'curl\s+.*\|\s*bash',
            r'wget\s+.*\|\s*sh',
            r'eval\s+\$',
            r'rm\s+-rf\s+/',
            r'chmod\s+777',
        ]

        for pattern in unsafe_patterns:
            if re.search(pattern, yaml_content, re.IGNORECASE):
                logger.debug(f"Unsafe command pattern found: {pattern}", correlation_id=correlation_id)
                return True
        
        return False

    def _check_privilege_escalation(self, yaml_content: str, correlation_id: Optional[str] = None) -> bool:
        """
        Check for privilege escalation risks.
        
        Detects:
        - Sudo usage in steps
        - Privileged container configurations
        
        Args:
            yaml_content: YAML content to check
            correlation_id: Request correlation ID
            
        Returns:
            True if privilege escalation risks detected
        """
        try:
            config = yaml.safe_load(yaml_content)
            if not isinstance(config, dict):
                return False

            jobs = config.get("jobs", {})
            
            for job_config in jobs.values():
                # Check steps for sudo usage
                steps = job_config.get("steps", [])
                for step in steps:
                    run_cmd = step.get("run", "") if isinstance(step, dict) else ""
                    if "sudo" in run_cmd.lower():
                        logger.debug("Privilege escalation detected: sudo usage", correlation_id=correlation_id)
                        return True

                # Check for privileged containers
                container_opts = job_config.get("container", {}).get("options", "")
                if "--privileged" in container_opts:
                    logger.debug("Privilege escalation detected: privileged container", correlation_id=correlation_id)
                    return True

        except yaml.YAMLError as e:
            logger.warning(
                f"Failed to parse YAML for privilege escalation check: {e}",
                correlation_id=correlation_id
            )

        return False

    def _check_insecure_defaults(self, yaml_content: str, correlation_id: Optional[str] = None) -> bool:
        """
        Check for insecure default configurations.
        
        Detects:
        - Missing job timeouts
        
        Args:
            yaml_content: YAML content to check
            correlation_id: Request correlation ID
            
        Returns:
            True if insecure defaults detected
        """
        try:
            config = yaml.safe_load(yaml_content)
            if not isinstance(config, dict):
                return False

            jobs = config.get("jobs", {})
            
            for job_id, job_config in jobs.items():
                if "timeout-minutes" not in job_config:
                    logger.debug(
                        f"Insecure default: missing timeout for job {job_id}",
                        correlation_id=correlation_id
                    )
                    return True

        except yaml.YAMLError as e:
            logger.warning(
                f"Failed to parse YAML for insecure defaults check: {e}",
                correlation_id=correlation_id
            )

        return False

    def _has_critical_vulnerabilities(self, vulnerabilities: List[str]) -> bool:
        """
        Determine if vulnerabilities are critical and should block workflow.
        
        Args:
            vulnerabilities: List of vulnerability names
            
        Returns:
            True if critical vulnerabilities present
        """
        return any(vuln in self.CRITICAL_VULNERABILITIES for vuln in vulnerabilities)