"""
Analyser Agent - Analyses CI/CD pipelines for optimisation opportunities using LLM.
"""

from typing import Optional, Dict, Any

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.utils.llm_client import LLMClient
from app.config import config
from app.constants import SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH
from app.exceptions import AnalysisError
from app.orchestrator.prompts import ANALYSER_SYSTEM_PROMPT, build_analyser_prompt

logger = get_logger(__name__, "Analyser")


class Analyser(BaseService):
    """
    Analyses CI/CD pipeline YAML to identify optimisation opportunities using LLM
    """

    def __init__(self, model: str = None, temperature: float = None):
        """
        Initialise Analyser with LLM configuration.
        
        Args:
            model: LLM model name (defaults to config.ANALYSER_MODEL)
            temperature: LLM temperature (defaults to config.MODEL_TEMPERATURE)
        """
        super().__init__(agent_name="analyse")
        
        self.model = model or config.ANALYSER_MODEL
        self.temperature = temperature if temperature is not None else config.MODEL_TEMPERATURE
        
        self.llm_client = LLMClient(
            model=self.model,
            temperature=self.temperature
        )
        
        logger.debug(
            f"Initialised Analyser: model={self.model}, temperature={self.temperature}",
            correlation_id="INIT"
        )

    def run(
        self,
        pipeline_yaml: str,
        build_log: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyse pipeline YAML for optimisation opportunities.
        
        Args:
            pipeline_yaml: Pipeline YAML content to analyse
            build_log: Optional build log for context
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Dictionary containing:
                - issues_detected: List of issues found
                - suggested_fixes: List of recommended fixes
                - expected_improvement: Expected performance gain
                - is_fixable: Whether issues can be automatically fixed
                
        Raises:
            AnalysisError: If analysis fails
        """
        # Input validation
        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            logger.error("Invalid or empty pipeline YAML", correlation_id=correlation_id)
            raise AnalysisError("pipeline_yaml must be a non-empty string")
        
        logger.debug("Starting pipeline analysis", correlation_id=correlation_id)
        
        try:
            # Build prompt using centralized prompt builder
            prompt = build_analyser_prompt(pipeline_yaml, build_log)
            
            # Call LLM with structured output
            raw_result = self._call_llm(prompt, correlation_id)
            
            # Parse and validate response
            analysis = self._parse_and_validate_result(raw_result, correlation_id)
            
            # Log summary
            logger.info(
                f"Analysis complete: {len(analysis.get('issues_detected', []))} issues found, "
                f"fixable={analysis.get('is_fixable', False)}",
                correlation_id=correlation_id
            )
            logger.debug(f"Full analysis result: {analysis}", correlation_id=correlation_id)
            
            return analysis
            
        except Exception as e:
            logger.exception(f"Analysis failed: {e}", correlation_id=correlation_id)
            raise AnalysisError(f"Failed to analyze pipeline: {e}") from e

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute analysis within workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with analysis results
        """
        correlation_id = state.get("correlation_id")
        
        try:
            # Run analysis
            analysis_result = self.run(
                pipeline_yaml=state["pipeline_yaml"],
                build_log=state.get("build_log", ""),
                correlation_id=correlation_id
            )
            
            # Ensure valid structure
            if not isinstance(analysis_result, dict):
                logger.warning("Analysis returned non-dict, using default structure", correlation_id=correlation_id)
                analysis_result = {
                    "issues_detected": [],
                    "suggested_fixes": [],
                    "expected_improvement": "",
                    "is_fixable": False
                }
            
            # Update state
            state["analysis_result"] = analysis_result
            
            # Save issues to database if found
            issues_detected = analysis_result.get("issues_detected", [])
            if issues_detected:
                self._save_issues_to_db(state, issues_detected, analysis_result, correlation_id)
            else:
                logger.info("No issues detected - pipeline is already optimal", correlation_id=correlation_id)
            
        except AnalysisError as e:
            # Set error in state to stop workflow
            state["error"] = f"Analysis failed: {e}"
            logger.error(f"Analysis failed: {e}", correlation_id=correlation_id)
        
        return state

    def _save_issues_to_db(
        self,
        state: Dict[str, Any],
        issues_detected: list,
        analysis_result: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Save detected issues to database.
        
        Args:
            state: Current workflow state
            issues_detected: List of issue descriptions
            analysis_result: Full analysis result
            correlation_id: Request correlation ID
        """
        suggested_fixes = analysis_result.get("suggested_fixes", [])
        
        issues = []
        for i, issue_text in enumerate(issues_detected):
            fix_text = suggested_fixes[i] if i < len(suggested_fixes) else "TBD"
            issues.append({
                "type": "optimization",
                "description": issue_text,
                "severity": self._determine_severity(issue_text),
                "suggested_fix": fix_text
            })
        
        try:
            self.repository.save_issues(
                run_id=state["run_id"],
                issues=issues,
                correlation_id=correlation_id
            )
            logger.debug(f"Stored {len(issues)} issues in database", correlation_id=correlation_id)
        except Exception as e:
            # Continue analysis even if DB save fails
            logger.warning(f"Failed to store issues in database: {e}", correlation_id=correlation_id)

    def _determine_severity(self, issue: str) -> str:
        """
        Determine issue severity based on content.
        
        Uses keyword matching to classify issues as high, medium, or low severity.
        
        Args:
            issue: Issue description
            
        Returns:
            Severity level: "high", "medium", or "low"
        """
        issue_lower = issue.lower()
        
        # High severity keywords
        high_severity_keywords = [
            "security", "vulnerability", "critical", "blocking",
            "fail", "error", "crash", "unsafe", "exposed"
        ]
        if any(word in issue_lower for word in high_severity_keywords):
            return SEVERITY_HIGH
        
        # Medium severity keywords
        medium_severity_keywords = [
            "performance", "slow", "inefficient", "optimize",
            "improve", "redundant", "duplicate", "bottleneck"
        ]
        if any(word in issue_lower for word in medium_severity_keywords):
            return SEVERITY_MEDIUM
        
        # Default to low
        return SEVERITY_LOW

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact saving.
        
        Returns:
            Key name for analysis results in state
        """
        return "analysis_result"

    def _call_llm(self, prompt: str, correlation_id: Optional[str] = None) -> str:
        """
        Call LLM and return raw text response.
        
        Args:
            prompt: Prompt to send to LLM
            correlation_id: Request correlation ID
            
        Returns:
            Raw response text from LLM
        """
        return self.llm_client.chat_completion(
            system_prompt=ANALYSER_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_format={"type": "json_object"},
            correlation_id=correlation_id
        )

    def _parse_and_validate_result(
        self,
        text_output: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse OpenAI output and validate JSON structure.
        
        Args:
            text_output: Raw text output from LLM
            correlation_id: Request correlation ID
            
        Returns:
            Validated analysis dictionary
            
        Raises:
            AnalysisError: If parsing or validation fails
        """
        try:
            # Parse JSON response (handles markdown code blocks)
            parsed = self.llm_client.parse_json_response(text_output, correlation_id)
            
            # Validate structure
            self._validate_structure(parsed, correlation_id)
            
            return parsed
            
        except ValueError as e:
            logger.error(f"Failed to parse analysis response: {e}", correlation_id=correlation_id)
            raise AnalysisError(f"Invalid JSON from model: {e}") from e

    def _validate_structure(
        self,
        analysis: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Ensure analysis dictionary has expected keys and types.
        
        Args:
            analysis: Analysis dictionary to validate
            correlation_id: Request correlation ID
            
        Raises:
            AnalysisError: If validation fails
        """
        required_keys = ["issues_detected", "suggested_fixes", "expected_improvement", "is_fixable"]
        missing = [k for k in required_keys if k not in analysis]
        
        if missing:
            logger.error(f"Analysis missing required keys: {missing}", correlation_id=correlation_id)
            raise AnalysisError(f"Analysis missing required keys: {missing}")
        
        # Type validation
        if not isinstance(analysis["issues_detected"], list):
            raise AnalysisError("issues_detected must be a list")
        
        if not isinstance(analysis["suggested_fixes"], list):
            raise AnalysisError("suggested_fixes must be a list")
        
        if not isinstance(analysis["expected_improvement"], str):
            raise AnalysisError("expected_improvement must be a string")
        
        if not isinstance(analysis["is_fixable"], bool):
            raise AnalysisError("is_fixable must be a boolean")
        
        # Validate list lengths match
        if len(analysis["issues_detected"]) != len(analysis["suggested_fixes"]):
            logger.warning(
                f"Mismatch: {len(analysis['issues_detected'])} issues but "
                f"{len(analysis['suggested_fixes'])} fixes",
                correlation_id=correlation_id
            )